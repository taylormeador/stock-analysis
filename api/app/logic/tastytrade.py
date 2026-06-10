"""
Read Tastytrade data from Redis, join excluded-symbols from DB,
and compute per-account risk metrics per the dashboard spec.
"""
import json
import logging
import math
import os

import redis
from sqlalchemy import text

from app.db import get_connection

ANNUALIZE = math.sqrt(252)

logger = logging.getLogger(__name__)

_rc = redis.Redis.from_url(os.environ["REDIS_URL"])
REDIS_KEY = "tastytrade:dashboard"

_VOL_MAP: dict[str, str] = {
    # Futures underlyings → instrument_vol symbol
    "SPX": "^GSPC", "/ES": "^GSPC", "/MES": "^GSPC",
    "NDX": "QQQ",   "/NQ": "QQQ",   "/MNQ": "QQQ",
    "RUT": "IWM",   "/RTY": "IWM",  "/M2K": "IWM",
    "/ZN": "IEF",   "/ZB": "TLT",
    "/MGC": "GLD",  "/GC": "GLD",
    "/SI": "SLV",
    "/MBT": "BTC-USD", "/BTC": "BTC-USD",
    "/MET": "ETH-USD", "/ETH": "ETH-USD",
    "/6E": "EURUSD=X", "/6B": "GBPUSD=X", "/6J": "JPYUSD=X",
    # Equity ETFs that map directly to tracked instrument_vol symbols
    "VOO": "^GSPC", "SPY": "^GSPC", "VT": "^GSPC",
    "QQQ": "QQQ",   "IWM": "IWM",
    "TLT": "TLT",   "IEF": "IEF",
    "GLD": "GLD",   "SLV": "SLV",
}


async def _fetch_instrument_vols(symbols: list[str]) -> dict[str, float]:
    if not symbols:
        return {}
    try:
        sql = text("""
            SELECT DISTINCT ON (symbol) symbol, blended_vol
            FROM instrument_vol
            WHERE symbol = ANY(:symbols)
            ORDER BY symbol, date DESC
        """)
        async with get_connection() as conn:
            result = await conn.execute(sql, {"symbols": symbols})
            return {row.symbol: float(row.blended_vol) * ANNUALIZE for row in result}
    except Exception:
        logger.exception("Failed to fetch instrument_vol from DB")
        return {}


async def _fetch_excluded(account_number: str) -> set[str]:
    try:
        sql = text("""
            SELECT symbol FROM tastytrade_excluded_symbols
            WHERE account_number = :acct
        """)
        async with get_connection() as conn:
            result = await conn.execute(sql, {"acct": account_number})
            return {row.symbol for row in result}
    except Exception:
        logger.exception(f"Failed to fetch excluded symbols for {account_number}")
        return set()


def _compute_position_metrics(pos: dict, instrument_vols: dict[str, float]) -> dict:
    qty = pos["quantity"]
    mult = pos["multiplier"]
    delta = pos.get("delta")
    underlying_px = pos.get("underlying_price")
    underlying = pos.get("underlying_symbol", "")
    itype = pos.get("instrument_type", "")

    # Notional dollar value of the position
    if "Option" in itype:
        notional_px = underlying_px
    else:
        notional_px = pos.get("close_price") or underlying_px
    notional_value = round(notional_px * qty * mult, 2) if notional_px is not None else None

    # Delta-weighted notional (for vol targeting)
    notional_delta = None
    if delta is not None and underlying_px is not None:
        notional_delta = abs(delta) * underlying_px * mult * qty

    # Vol lookup: use IV if available (never is via REST), else instrument_vol
    iv = pos.get("implied_volatility")
    if iv is None:
        vol_sym = _VOL_MAP.get(underlying)
        if vol_sym:
            iv = instrument_vols.get(vol_sym)

    vol_contribution = None
    if notional_delta is not None and iv is not None:
        vol_contribution = notional_delta * iv

    return {
        **pos,
        "notional_value": notional_value,
        "notional_delta": round(notional_delta, 2) if notional_delta is not None else None,
        "vol_pct_used": round(iv, 4) if iv is not None else None,
        "vol_contribution": round(vol_contribution, 2) if vol_contribution is not None else None,
    }


def _compute_account_metrics(acct: dict, positions_enriched: list[dict]) -> dict:
    active = [p for p in positions_enriched if p.get("is_active")]
    net_liq = acct["net_liq"]

    cushion_ratio = None
    if acct["account_type"] == "margin" and acct.get("maintenance_excess") is not None:
        cushion_ratio = round(acct["maintenance_excess"] / net_liq, 4) if net_liq else None

    leverage_ratio = None
    if acct["account_type"] == "margin":
        total_notional = sum(p["notional_delta"] for p in active if p.get("notional_delta") is not None)
        leverage_ratio = round(total_notional / net_liq, 4) if net_liq and total_notional else None

    # Vol contribution is computed over ALL positions (including B&H shares) for portfolio-level view
    total_vol = sum(p["vol_contribution"] for p in positions_enriched if p.get("vol_contribution") is not None)
    vol_as_pct = round(total_vol / net_liq, 4) if net_liq and total_vol else None

    return {
        **acct,
        "positions": positions_enriched,
        "cushion_ratio": cushion_ratio,
        "leverage_ratio": leverage_ratio,
        "total_vol_contribution": round(total_vol, 2) if total_vol else None,
        "vol_as_pct_of_account": vol_as_pct,
    }


async def get_dashboard() -> dict:
    try:
        raw = _rc.get(REDIS_KEY)
    except Exception:
        logger.exception("Failed to read tastytrade data from Redis")
        return {"accounts": [], "fetched_at": None}

    if not raw:
        return {"accounts": [], "fetched_at": None}

    data = json.loads(raw)

    all_underlyings: set[str] = set()
    for acct in data.get("accounts", []):
        for pos in acct.get("positions", []):
            mapped = _VOL_MAP.get(pos.get("underlying_symbol", ""), pos.get("underlying_symbol", ""))
            if mapped:
                all_underlyings.add(mapped)

    instrument_vols = await _fetch_instrument_vols(list(all_underlyings))

    enriched_accounts = []
    for acct in data.get("accounts", []):
        excluded = await _fetch_excluded(acct["account_number"])

        enriched_positions = []
        for pos in acct.get("positions", []):
            is_active = pos["symbol"] not in excluded if pos["instrument_type"] == "Equity" else True
            enriched = _compute_position_metrics(pos, instrument_vols)
            enriched["is_active"] = is_active
            enriched_positions.append(enriched)

        enriched_accounts.append(_compute_account_metrics(acct, enriched_positions))

    return {
        "accounts": enriched_accounts,
        "fetched_at": data.get("fetched_at"),
    }
