import asyncio
import logging
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import text

from app.db import get_connection

logger = logging.getLogger(__name__)

CALC_NUMERIC_COLS = [
    "current_price",
    "ewma_vol",
    "combined_forecast",
    "desired_position",
    "subsystem_position",
    "portfolio_position",
    "instrument_value_volatility",
    "vol_scalar",
]


async def get_portfolio_forecasts(lookback_days: int = 180) -> dict:
    since = date.today() - timedelta(days=lookback_days)

    instruments = await _fetch_active_instruments()
    if not instruments:
        return {"instruments": [], "calculations": []}

    symbols = [i["symbol"] for i in instruments]

    prices_by_symbol, forecasts_by_symbol, calculations = await asyncio.gather(
        _fetch_prices(symbols, since),
        _fetch_forecasts(symbols, since),
        _fetch_calculations(symbols, since),
    )

    result_instruments = [
        {
            "symbol": instrument["symbol"],
            "label": instrument["label"],
            "prices": prices_by_symbol.get(instrument["symbol"], []),
            "forecasts": forecasts_by_symbol.get(instrument["symbol"], []),
        }
        for instrument in instruments
    ]

    return {
        "instruments": result_instruments,
        "calculations": calculations,
    }


async def _fetch_active_instruments() -> list[dict[str, str]]:
    sql = text("""
        SELECT symbol, label
        FROM = instruments
        WHERE is_active = TRUE
        ORDER BY label
    """)
    async with get_connection() as conn:
        result = await conn.execute(sql)
        return [{"symbol": row.symbol, "label": row.label} for row in result]


async def _fetch_prices(symbols: list[str], since: date) -> dict[str, list[dict]]:
    sql = text("""
        SELECT symbol, date, close
        FROM futures_prices
        WHERE symbol = ANY(:symbols)
          AND date >= :since
        ORDER BY symbol, date ASC
    """)
    async with get_connection() as conn:
        result = await conn.execute(sql, {"symbols": symbols, "since": since})
        rows = result.fetchall()

    if not rows:
        return {}

    df = pd.DataFrame(rows, columns=["symbol", "date", "close"])
    df["date"] = df["date"].astype(str)
    df["close"] = pd.to_numeric(df["close"])
    df["close"] = df["close"].fillna(0.0)

    return {
        symbol: group[["date", "close"]].to_dict("records")
        for symbol, group in df.groupby("symbol")
    }


async def _fetch_forecasts(symbols: list[str], since: date) -> dict[str, list[dict]]:
    sql = text("""
        SELECT symbol, date, rule_name, scaled_value
        FROM forecasts
        WHERE symbol = ANY(:symbols)
          AND date >= :since
        ORDER BY symbol, date ASC
    """)
    async with get_connection() as conn:
        result = await conn.execute(sql, {"symbols": symbols, "since": since})
        rows = result.fetchall()

    if not rows:
        return {}

    df = pd.DataFrame(rows, columns=["symbol", "date", "rule_name", "scaled_value"])
    df["date"] = df["date"].astype(str)
    df["scaled_value"] = pd.to_numeric(df["scaled_value"])
    df["scaled_value"] = df["scaled_value"].fillna(0.0)

    return {
        symbol: group[["date", "rule_name", "scaled_value"]].to_dict("records")
        for symbol, group in df.groupby("symbol")
    }


async def _fetch_calculations(symbols: list[str], since: date) -> list[dict]:
    sql = text("""
        SELECT
            symbol, date,
            current_price, ewma_vol,
            combined_forecast, desired_position,
            subsystem_position, portfolio_position,
            instrument_value_volatility, vol_scalar
        FROM portfolio_calculations
        WHERE symbol = ANY(:symbols)
          AND date >= :since
        ORDER BY symbol, date ASC
    """)
    async with get_connection() as conn:
        result = await conn.execute(sql, {"symbols": symbols, "since": since})
        rows = result.fetchall()

    if not rows:
        return []

    df = pd.DataFrame(rows, columns=["symbol", "date"] + CALC_NUMERIC_COLS)
    df["date"] = df["date"].astype(str)
    for col in CALC_NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col]).fillna(0.0)

    return df.to_dict("records")
