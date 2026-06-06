"""
Read Tastytrade data from Redis, join excluded-symbols from DB,
and compute per-account risk metrics per the dashboard spec.
"""
import json
import logging
import math
import os
import re

import redis
from sqlalchemy import text

from app.db import get_connection

ANNUALIZE = math.sqrt(252)

logger = logging.getLogger(__name__)

_rc = redis.Redis.from_url(os.environ["REDIS_URL"])
REDIS_KEY = "tastytrade:dashboard"

_FUTURES_VOL_MAP: dict[str, str] = {
    "SPX": "^GSPC", "/ES": "^GSPC", "/MES": "^GSPC",
    "NDX": "QQQ",   "/NQ": "QQQ",   "/MNQ": "QQQ",
    "RUT": "IWM",   "/RTY": "IWM",  "/M2K": "IWM",
    "/ZN": "IEF",   "/ZB": "TLT",
    "/MGC": "GLD",  "/GC": "GLD",
    "/SI": "SLV",
    "/MBT": "BTC-USD", "/BTC": "BTC-USD",
    "/MET": "ETH-USD", "/ETH": "ETH-USD",
    "/6E": "EURUSD=X", "/6B": "GBPUSD=X", "/6J": "JPYUSD=X",
}

_OCC_RE = re.compile(
    r"^(?P<underlying>[A-Z0-9./]+)\s*(?P<exp>\d{6})(?P<otype>[CP])(?P<strike>\d{8})$"
)


def _parse_occ(symbol: str) -> dict | None:
    m = _OCC_RE.match(symbol.strip())
    if not m:
        return None
    return {
        "option_type": m.group("otype"),
        "strike": int(m.group("strike")) / 1000,
    }


def _auto_cap_risk(pos: dict) -> float | None:
    qty = pos["quantity"]
    mult = pos["multiplier"]
    direction = pos["direction"]
    itype = pos["instrument_type"]

    if "Option" in itype:
        parsed = _parse_occ(pos["symbol"])
        if parsed and direction == "Short":
            if parsed["option_type"] == "P":
                return parsed["strike"] * mult * qty
            else:
                px = pos.get("underlying_price") or pos.get("close_price") or 0.0
                return px * mult * qty
        else:
            avg = pos.get("average_open_price") or pos.get("close_price") or 0.0
            return avg * mult * qty

    if "Future" in itype:
        px = pos.get("close_price") or pos.get("underlying_price")
        return px * mult * qty if px else None

    px = pos.get("close_price") or pos.get("underlying_price")
    return px * mult * qty if px else None


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

    cap_risk = _auto_cap_risk(pos)

    notional_delta = None
    if delta is not None and underlying_px is not None:
        notional_delta = abs(delta) * underlying_px * mult * qty

    iv = pos.get("implied_volatility")
    if iv is None:
        vol_sym = _FUTURES_VOL_MAP.get(underlying)
        if vol_sym:
            iv = instrument_vols.get(vol_sym)

    vol_contribution = None
    if notional_delta is not None and iv is not None:
        vol_contribution = notional_delta * iv

    return {
        **pos,
        "capital_at_risk": round(cap_risk, 2) if cap_risk is not None else None,
        "notional_delta": round(notional_delta, 2) if notional_delta is not None else None,
        "vol_contribution": round(vol_contribution, 2) if vol_contribution is not None else None,
    }


def _compute_account_metrics(acct: dict, positions_enriched: list[dict]) -> dict:
    active = [p for p in positions_enriched if p.get("is_active")]
    net_liq = acct["net_liq"]
    cash = acct["cash_balance"]

    cushion_ratio = None
    if acct["account_type"] == "margin" and acct.get("maintenance_excess") is not None:
        cushion_ratio = round(acct["maintenance_excess"] / net_liq, 4) if net_liq else None

    total_car = sum(p["capital_at_risk"] for p in active if p.get("capital_at_risk") is not None)
    denominator = cash if acct["account_type"] == "margin" else net_liq
    car_ratio = round(total_car / denominator, 4) if denominator else None

    leverage_ratio = None
    if acct["account_type"] == "margin":
        total_notional = sum(p["notional_delta"] for p in active if p.get("notional_delta") is not None)
        leverage_ratio = round(total_notional / net_liq, 4) if net_liq and total_notional else None

    total_vol = sum(p["vol_contribution"] for p in active if p.get("vol_contribution") is not None)
    vol_as_pct = round(total_vol / net_liq, 4) if net_liq and total_vol else None

    return {
        **acct,
        "positions": positions_enriched,
        "cushion_ratio": cushion_ratio,
        "total_capital_at_risk": round(total_car, 2),
        "capital_at_risk_ratio": car_ratio,
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
            mapped = _FUTURES_VOL_MAP.get(pos.get("underlying_symbol", ""), pos.get("underlying_symbol", ""))
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
