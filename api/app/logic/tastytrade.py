"""
Read Tastytrade data from Redis, merge stop annotations from DB,
and compute per-account risk metrics per the dashboard spec.
"""
import json
import logging
import math
import os
import re
from datetime import date

import redis
from sqlalchemy import text

from app.db import get_connection

ANNUALIZE = math.sqrt(252)

logger = logging.getLogger(__name__)

_rc = redis.Redis.from_url(os.environ["REDIS_URL"])
REDIS_KEY = "tastytrade:dashboard"

# Maps futures underlying symbols (as reported by TT) to our instrument_vol symbols.
# TT reports the underlying of /MES as "SPX" or "/ES" depending on position type.
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


# ── OCC symbol parser ─────────────────────────────────────────────────────────

_OCC_RE = re.compile(
    r"^(?P<underlying>[A-Z0-9./]+)\s*"
    r"(?P<exp>\d{6})"
    r"(?P<otype>[CP])"
    r"(?P<strike>\d{8})$"
)


def _parse_occ(symbol: str) -> dict | None:
    m = _OCC_RE.match(symbol.strip())
    if not m:
        return None
    return {
        "underlying": m.group("underlying"),
        "expiry": m.group("exp"),
        "option_type": m.group("otype"),
        "strike": int(m.group("strike")) / 1000,
    }


# ── Auto-compute capital at risk for a position ───────────────────────────────

def _auto_cap_risk(pos: dict) -> float:
    """
    Default capital at risk when no user stop is defined.
    Short put:  full assignment = strike × multiplier × qty
    Short call: full notional  = underlying_price × multiplier × qty  (or close_price-based)
    Future:     full notional  = close_price × multiplier × qty
    Long option: premium paid  = avg_open_price × multiplier × qty
    """
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
                underlying_px = pos["underlying_price"] or pos["close_price"] or 0.0
                return underlying_px * mult * qty
        else:
            # Long option: risk is premium paid
            avg = pos["average_open_price"] or pos["close_price"] or 0.0
            return avg * mult * qty

    if "Future" in itype:
        px = pos["close_price"] or 0.0
        return px * mult * qty

    # Equity (shouldn't reach here for active positions)
    px = pos["close_price"] or pos["underlying_price"] or 0.0
    return px * mult * qty


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _fetch_instrument_vols(symbols: list[str]) -> dict[str, float]:
    """Return latest annualized blended_vol for each symbol from instrument_vol."""
    if not symbols:
        return {}
    sql = text("""
        SELECT DISTINCT ON (symbol) symbol, blended_vol
        FROM instrument_vol
        WHERE symbol = ANY(:symbols)
        ORDER BY symbol, date DESC
    """)
    async with get_connection() as conn:
        result = await conn.execute(sql, {"symbols": symbols})
        return {
            row.symbol: float(row.blended_vol) * ANNUALIZE
            for row in result
        }


async def _fetch_stops(account_number: str) -> dict[str, dict]:
    """Return {symbol: {stop_amount, stop_mode, stop_defined}} for one account."""
    sql = text("""
        SELECT symbol, stop_amount, stop_mode
        FROM tastytrade_position_stops
        WHERE account_number = :acct
    """)
    async with get_connection() as conn:
        result = await conn.execute(sql, {"acct": account_number})
        return {
            row.symbol: {
                "stop_amount": float(row.stop_amount) if row.stop_amount is not None else None,
                "stop_mode": row.stop_mode,
                "stop_defined": row.stop_amount is not None,
            }
            for row in result
        }


async def _fetch_excluded(account_number: str) -> set[str]:
    """Return set of equity symbols excluded from active-position metrics."""
    sql = text("""
        SELECT symbol FROM tastytrade_excluded_symbols
        WHERE account_number = :acct
    """)
    async with get_connection() as conn:
        result = await conn.execute(sql, {"acct": account_number})
        return {row.symbol for row in result}


async def _upsert_stop(
    account_number: str,
    symbol: str,
    stop_amount: float | None,
    stop_mode: str,
    notes: str | None,
) -> None:
    sql = text("""
        INSERT INTO tastytrade_position_stops (account_number, symbol, stop_amount, stop_mode, notes, updated_at)
        VALUES (:acct, :sym, :amount, :mode, :notes, NOW())
        ON CONFLICT (account_number, symbol) DO UPDATE SET
            stop_amount = EXCLUDED.stop_amount,
            stop_mode   = EXCLUDED.stop_mode,
            notes       = EXCLUDED.notes,
            updated_at  = NOW()
    """)
    async with get_connection() as conn:
        await conn.execute(sql, {
            "acct": account_number,
            "sym": symbol,
            "amount": stop_amount,
            "mode": stop_mode,
            "notes": notes,
        })
        await conn.commit()


# ── Metric computation ────────────────────────────────────────────────────────

def _compute_position_metrics(
    pos: dict,
    stop_info: dict | None,
    instrument_vols: dict[str, float],
) -> dict:
    """Enrich one position dict with capital_at_risk and vol_contribution."""
    qty = pos["quantity"]
    mult = pos["multiplier"]
    delta = pos.get("delta")
    underlying_px = pos.get("underlying_price")
    underlying = pos.get("underlying_symbol", "")

    # Capital at risk
    if stop_info and stop_info["stop_defined"]:
        cap_risk = stop_info["stop_amount"]
        stop_mode = stop_info["stop_mode"]
        stop_defined = True
    else:
        cap_risk = _auto_cap_risk(pos)
        stop_mode = stop_info["stop_mode"] if stop_info else "stop_loss"
        stop_defined = False

    # Delta-adjusted notional (absolute value — magnitude of exposure)
    notional_delta = None
    if delta is not None and underlying_px is not None:
        notional_delta = abs(delta) * underlying_px * mult * qty

    # Annualized vol: prefer TT-provided IV for options; fall back to instrument_vol
    # for futures and any position where the broker doesn't supply IV.
    iv = pos.get("implied_volatility")
    if iv is None:
        iv_sym = _FUTURES_VOL_MAP.get(underlying) or instrument_vols.get(underlying)
        if isinstance(iv_sym, str):
            iv = instrument_vols.get(iv_sym)
        elif isinstance(iv_sym, float):
            iv = iv_sym

    vol_contribution = None
    if notional_delta is not None and iv is not None:
        vol_contribution = notional_delta * iv

    return {
        **pos,
        "stop_mode": stop_mode,
        "stop_defined": stop_defined,
        "capital_at_risk": round(cap_risk, 2) if cap_risk is not None else None,
        "notional_delta": round(notional_delta, 2) if notional_delta is not None else None,
        "vol_contribution": round(vol_contribution, 2) if vol_contribution is not None else None,
    }


def _compute_account_metrics(acct: dict, positions_enriched: list[dict]) -> dict:
    active = [p for p in positions_enriched if p.get("is_active")]

    net_liq = acct["net_liq"]
    cash = acct["cash_balance"]

    # Cushion ratio (margin only)
    cushion_ratio = None
    if acct["account_type"] == "margin" and acct.get("maintenance_excess") is not None:
        cushion_ratio = round(acct["maintenance_excess"] / net_liq, 4) if net_liq else None

    # Capital at risk
    total_car = sum(p["capital_at_risk"] for p in active if p.get("capital_at_risk") is not None)
    denominator = cash if acct["account_type"] == "margin" else net_liq
    car_ratio = round(total_car / denominator, 4) if denominator else None

    # Leverage ratio (margin only)
    leverage_ratio = None
    if acct["account_type"] == "margin":
        total_notional = sum(p["notional_delta"] for p in active if p.get("notional_delta") is not None)
        leverage_ratio = round(total_notional / net_liq, 4) if net_liq and total_notional else None

    # Vol targeting
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


# ── Public API ────────────────────────────────────────────────────────────────

async def get_dashboard() -> dict:
    raw = _rc.get(REDIS_KEY)
    if not raw:
        return {"accounts": [], "fetched_at": None}

    data = json.loads(raw)

    # Collect all underlying symbols across all accounts to batch the vol lookup.
    all_underlyings: set[str] = set()
    for acct in data.get("accounts", []):
        for pos in acct.get("positions", []):
            u = pos.get("underlying_symbol", "")
            mapped = _FUTURES_VOL_MAP.get(u, u)
            all_underlyings.add(mapped)

    instrument_vols = await _fetch_instrument_vols(list(all_underlyings))

    enriched_accounts = []
    for acct in data.get("accounts", []):
        account_number = acct["account_number"]
        stops = await _fetch_stops(account_number)
        excluded = await _fetch_excluded(account_number)

        enriched_positions = []
        for pos in acct.get("positions", []):
            itype = pos["instrument_type"]
            sym = pos["symbol"]

            # Equities are active only if not in the excluded list
            if itype == "Equity":
                is_active = sym not in excluded
            else:
                is_active = True

            stop_info = stops.get(sym)
            enriched = _compute_position_metrics(pos, stop_info, instrument_vols)
            enriched["is_active"] = is_active
            enriched_positions.append(enriched)

        enriched_accounts.append(
            _compute_account_metrics(acct, enriched_positions)
        )

    return {
        "accounts": enriched_accounts,
        "fetched_at": data.get("fetched_at"),
    }


async def update_stop(
    account_number: str,
    symbol: str,
    stop_amount: float | None,
    stop_mode: str = "stop_loss",
    notes: str | None = None,
) -> None:
    await _upsert_stop(account_number, symbol, stop_amount, stop_mode, notes)
