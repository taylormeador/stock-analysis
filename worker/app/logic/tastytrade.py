"""
Fetch Tastytrade account + position data and publish to Redis.

Caches to Redis key: tastytrade:dashboard
Schema:
  {
    "fetched_at": "ISO8601",
    "accounts": [
      {
        "account_number": str,
        "account_type": "margin" | "ira",
        "net_liq": float,
        "cash_balance": float,
        "maintenance_excess": float | null,   # margin only
        "equity_buying_power": float,
        "positions": [
          {
            "symbol": str,            # full broker symbol (OCC for options)
            "underlying_symbol": str,
            "instrument_type": str,   # "Equity" | "Equity Option" | "Future" | "Future Option"
            "quantity": float,        # always positive
            "direction": str,         # "Long" | "Short"
            "close_price": float,
            "average_open_price": float | null,
            "multiplier": int,
            "delta": float | null,    # live from market data if available
            "implied_volatility": float | null,
            "underlying_price": float | null,
          }
        ]
      }
    ]
  }
"""
import json
import logging
import os
from datetime import datetime, timezone

import redis
import yfinance as yf

logger = logging.getLogger(__name__)

_rc = redis.Redis.from_url(os.environ["REDIS_URL"])

REDIS_KEY = "tastytrade:dashboard"
REDIS_TTL = 600  # 10 minutes — stale if worker stops


def _account_type(account_type_name: str) -> str:
    name = (account_type_name or "").lower()
    if "ira" in name or "roth" in name:
        return "ira"
    return "margin"


def _fetch_underlying_prices(symbols: list[str]) -> dict[str, float]:
    if not symbols:
        return {}
    prices = {}
    try:
        tickers = yf.download(
            symbols,
            period="2d",
            progress=False,
            auto_adjust=True,
        )
        close = tickers["Close"] if "Close" in tickers else tickers
        if close.empty:
            return {}
        latest = close.iloc[-1]
        if len(symbols) == 1:
            prices[symbols[0]] = float(latest.iloc[0]) if hasattr(latest, "iloc") else float(latest)
        else:
            for sym in symbols:
                if sym in latest.index and not latest[sym] != latest[sym]:  # NaN check
                    prices[sym] = float(latest[sym])
    except Exception:
        logger.exception("Failed to fetch underlying prices via yfinance")
    return prices


def fetch_and_cache(tracker=None) -> None:
    username = os.environ["TASTYTRADE_USERNAME"]
    password = os.environ["TASTYTRADE_PASSWORD"]
    # TT_SECRET: TOTP seed if 2FA is enabled; any non-empty string otherwise.
    # TT_REFRESH: the SDK requires this field but we create a fresh session each
    # run, so it is never actually used for token refresh. Set to any non-empty
    # string (e.g. "none") in your .env.
    secret = os.environ["TT_SECRET"]
    refresh = os.environ.get("TT_REFRESH", "none") or "none"

    # Import here so the worker won't crash if tastytrade isn't installed
    from tastytrade import Session
    from tastytrade.account import Account

    session = Session(
        login=username,
        password=password,
        provider_secret=secret,
        refresh_token=refresh,
    )

    accounts_raw = Account.get_accounts(session)
    if not accounts_raw:
        logger.warning("No Tastytrade accounts found")
        return

    all_underlying: set[str] = set()
    account_dicts = []

    for acct in accounts_raw:
        try:
            balances = acct.get_balances(session)
            positions_raw = acct.get_positions(session)
        except Exception:
            logger.exception(f"Failed to fetch data for account {acct.account_number}")
            continue

        positions = []
        for pos in positions_raw:
            try:
                instrument_type = (
                    pos.instrument_type.value
                    if hasattr(pos.instrument_type, "value")
                    else str(pos.instrument_type)
                )
                direction = (
                    pos.quantity_direction
                    if isinstance(pos.quantity_direction, str)
                    else pos.quantity_direction.value
                )
                underlying = getattr(pos, "underlying_symbol", None) or getattr(pos, "symbol", "")
                all_underlying.add(underlying)

                positions.append({
                    "symbol": str(pos.symbol),
                    "underlying_symbol": underlying,
                    "instrument_type": instrument_type,
                    "quantity": float(abs(pos.quantity)),
                    "direction": direction,
                    "close_price": float(pos.close_price) if pos.close_price is not None else None,
                    "average_open_price": float(pos.average_open_price) if getattr(pos, "average_open_price", None) is not None else None,
                    "multiplier": int(pos.multiplier),
                    # Greeks: present on some SDK versions / market data enriched positions
                    "delta": float(pos.delta) if getattr(pos, "delta", None) is not None else None,
                    "implied_volatility": float(pos.implied_volatility) if getattr(pos, "implied_volatility", None) is not None else None,
                    "underlying_price": None,  # filled in below
                })
            except Exception:
                logger.exception(f"Failed to parse position {getattr(pos, 'symbol', '?')}")
                continue

        account_dicts.append({
            "account_number": str(acct.account_number),
            "account_type": _account_type(getattr(acct, "account_type_name", "")),
            "net_liq": float(balances.net_liquidating_value),
            "cash_balance": float(balances.cash_balance),
            "maintenance_excess": float(balances.maintenance_excess) if getattr(balances, "maintenance_excess", None) is not None else None,
            "equity_buying_power": float(balances.equity_buying_power) if getattr(balances, "equity_buying_power", None) is not None else None,
            "positions": positions,
        })

        if tracker:
            tracker.update_status_message(f"Fetched {acct.account_number}")

    # Enrich with underlying prices
    prices = _fetch_underlying_prices(list(all_underlying))
    for acct_dict in account_dicts:
        for pos in acct_dict["positions"]:
            pos["underlying_price"] = prices.get(pos["underlying_symbol"])

    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "accounts": account_dicts,
    }

    _rc.set(REDIS_KEY, json.dumps(payload), ex=REDIS_TTL)
    logger.info(
        f"Cached Tastytrade data: {len(account_dicts)} accounts, "
        f"{sum(len(a['positions']) for a in account_dicts)} positions"
    )
