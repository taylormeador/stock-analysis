"""
Fetch Tastytrade account + position data and publish to Redis.

Auth: OAuth via provider_secret + refresh_token (SDK v12+).
Session is persisted to Redis after each run so the refresh token stays current.

Caches to Redis key: tastytrade:dashboard
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import redis
import yfinance as yf
from tastytrade import Session
from tastytrade.account import Account

logger = logging.getLogger(__name__)

_rc = redis.Redis.from_url(os.environ["REDIS_URL"])

REDIS_KEY = "tastytrade:dashboard"
REDIS_SESSION_KEY = "tastytrade:session"
REDIS_TTL = 600
REDIS_SESSION_TTL = 30 * 24 * 3600


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
        tickers = yf.download(symbols, period="2d", progress=False, auto_adjust=True)
        close = tickers["Close"] if "Close" in tickers else tickers
        if close.empty:
            return {}
        latest = close.iloc[-1]
        if len(symbols) == 1:
            val = latest.iloc[0] if hasattr(latest, "iloc") else latest
            prices[symbols[0]] = float(val)
        else:
            for sym in symbols:
                if sym in latest.index and latest[sym] == latest[sym]:  # NaN guard
                    prices[sym] = float(latest[sym])
    except Exception:
        logger.exception("Failed to fetch underlying prices via yfinance")
    return prices


async def _build_session() -> Session:
    cached = _rc.get(REDIS_SESSION_KEY)
    if cached:
        try:
            return Session.deserialize(cached.decode())
        except Exception:
            logger.warning("Cached session invalid, creating new one from env")

    return Session(
        provider_secret=os.environ["TT_PROVIDER_SECRET"],
        refresh_token=os.environ["TT_REFRESH_TOKEN"],
    )


async def _fetch_async(tracker=None) -> None:
    session = await _build_session()

    accounts_raw = await Account.get(session)
    if not accounts_raw:
        logger.warning("No Tastytrade accounts found")
        return

    all_underlying: set[str] = set()
    account_dicts = []

    for acct in accounts_raw:
        try:
            balances = await acct.get_balances(session)
            positions_raw = await acct.get_positions(session)
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
                underlying = getattr(pos, "underlying_symbol", None) or str(pos.symbol)
                all_underlying.add(underlying)

                # Futures and equities have known delta; options need DXLink.
                delta = None
                if "Future" in instrument_type or instrument_type == "Equity":
                    delta = 1.0 if direction == "Long" else -1.0

                # Prefer close_price; fall back to mark_price or mark when absent
                raw_price = (
                    getattr(pos, "close_price", None)
                    or getattr(pos, "mark_price", None)
                    or getattr(pos, "mark", None)
                )

                positions.append(
                    {
                        "symbol": str(pos.symbol),
                        "underlying_symbol": underlying,
                        "instrument_type": instrument_type,
                        "quantity": float(abs(pos.quantity)),
                        "direction": direction,
                        "close_price": float(raw_price) if raw_price is not None else None,
                        "average_open_price": float(pos.average_open_price)
                        if getattr(pos, "average_open_price", None) is not None
                        else None,
                        "multiplier": float(pos.multiplier),
                        "delta": delta,
                        "implied_volatility": None,  # not available via REST
                        "underlying_price": None,  # filled below
                    }
                )
            except Exception:
                logger.exception(
                    f"Failed to parse position {getattr(pos, 'symbol', '?')}"
                )
                continue

        account_dicts.append(
            {
                "account_number": str(acct.account_number),
                "account_type": _account_type(getattr(acct, "account_type_name", "")),
                "net_liq": float(balances.net_liquidating_value),
                "cash_balance": float(balances.cash_balance),
                "maintenance_excess": float(balances.maintenance_excess)
                if getattr(balances, "maintenance_excess", None) is not None
                else None,
                "equity_buying_power": float(balances.equity_buying_power)
                if getattr(balances, "equity_buying_power", None) is not None
                else None,
                "positions": positions,
            }
        )

        if tracker:
            tracker.update_status_message(f"Fetched {acct.account_number}")

    # Futures underlying symbols (starting with "/" or index names like "SPX")
    # aren't valid yfinance tickers. For futures, the position close_price IS
    # the futures price — close enough for our calculations. Only fetch yfinance
    # prices for equity/ETF underlyings (options positions).
    equity_underlyings = [
        sym for sym in all_underlying
        if not sym.startswith("/") and sym not in ("SPX", "NDX", "RUT", "VIX")
    ]
    prices = _fetch_underlying_prices(equity_underlyings)

    for acct_dict in account_dicts:
        for pos in acct_dict["positions"]:
            underlying = pos["underlying_symbol"]
            if underlying in prices:
                pos["underlying_price"] = prices[underlying]
            elif "Future" in pos["instrument_type"]:
                pos["underlying_price"] = pos["close_price"]

    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "accounts": account_dicts,
    }
    _rc.set(REDIS_KEY, json.dumps(payload), ex=REDIS_TTL)

    try:
        _rc.set(REDIS_SESSION_KEY, session.serialize(), ex=REDIS_SESSION_TTL)
    except Exception:
        logger.warning("Could not serialize session to Redis")

    logger.info(
        f"Cached Tastytrade data: {len(account_dicts)} accounts, "
        f"{sum(len(a['positions']) for a in account_dicts)} positions"
    )


def fetch_and_cache(tracker=None) -> None:
    asyncio.run(_fetch_async(tracker))


if __name__ == "__main__":
    fetch_and_cache()
