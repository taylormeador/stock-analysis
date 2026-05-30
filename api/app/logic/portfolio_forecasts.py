import asyncio
import logging
import math
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import text

from app.db import get_connection

ANNUALIZE = math.sqrt(252) * 100

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


async def get_variations() -> list[dict]:
    """Active variations from the DB. Single source of truth."""
    sql = text("""
        SELECT name, rule, description
        FROM rule_variations
        WHERE is_active = TRUE
        ORDER BY name
    """)
    async with get_connection() as conn:
        result = await conn.execute(sql)
        return [
            {"name": row.name, "rule": row.rule, "description": row.description}
            for row in result
        ]


async def get_runs() -> list[str]:
    """All distinct run_ids present in portfolio_calculations."""
    sql = text("""
        SELECT DISTINCT run_id
        FROM portfolio_calculations
        ORDER BY run_id
    """)
    async with get_connection() as conn:
        result = await conn.execute(sql)
        return [row.run_id for row in result]


async def get_portfolio_forecasts(
    lookback_days: int,
    run_id: str,
) -> dict:
    since = date.today() - timedelta(days=lookback_days)

    instruments = await _fetch_active_instruments()
    if not instruments:
        return {"instruments": [], "calculations": []}

    symbols = [i["symbol"] for i in instruments]

    prices_by_symbol, forecasts_by_symbol, calculations = await asyncio.gather(
        _fetch_prices(instruments, since),
        _fetch_forecasts(symbols, since),
        _fetch_calculations(symbols, since, run_id),
    )

    result_instruments = [
        {
            "symbol": instrument["symbol"],
            "label": instrument["label"],
            "asset_class": instrument["asset_class"],
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
        SELECT symbol, label, price_source, asset_class
        FROM instruments
        WHERE is_active = TRUE
        ORDER BY asset_class, label
    """)
    async with get_connection() as conn:
        result = await conn.execute(sql)
        return [
            {
                "symbol": row.symbol,
                "label": row.label,
                "price_source": row.price_source,
                "asset_class": row.asset_class,
            }
            for row in result
        ]


async def _fetch_prices(
    instruments: list[dict[str, str]], since: date
) -> dict[str, list[dict]]:
    futures_symbols = [i["symbol"] for i in instruments if i["price_source"] == "futures_prices"]
    spot_symbols = [i["symbol"] for i in instruments if i["price_source"] == "stock_prices"]

    queries = []
    if futures_symbols:
        queries.append(_fetch_futures_prices(futures_symbols, since))
    if spot_symbols:
        queries.append(_fetch_spot_prices(spot_symbols, since))

    results = await asyncio.gather(*queries)
    combined: dict[str, list[dict]] = {}
    for r in results:
        combined.update(r)
    return combined


async def _fetch_futures_prices(symbols: list[str], since: date) -> dict[str, list[dict]]:
    sql = text("""
        SELECT fp.symbol, fp.date, fp.close,
               iv.blended_vol * :annualize AS blended_vol
        FROM futures_prices fp
        LEFT JOIN instrument_vol iv ON iv.symbol = fp.symbol AND iv.date = fp.date
        WHERE fp.symbol = ANY(:symbols)
          AND fp.date >= :since
        ORDER BY fp.symbol, fp.date ASC
    """)
    async with get_connection() as conn:
        result = await conn.execute(sql, {"symbols": symbols, "since": since, "annualize": ANNUALIZE})
        rows = result.fetchall()

    if not rows:
        return {}

    df = pd.DataFrame(rows, columns=["symbol", "date", "close", "blended_vol"])
    df["date"] = df["date"].astype(str)
    df["close"] = pd.to_numeric(df["close"]).fillna(0.0)
    df["blended_vol"] = pd.to_numeric(df["blended_vol"])
    return {symbol: group[["date", "close", "blended_vol"]].to_dict("records") for symbol, group in df.groupby("symbol")}


async def _fetch_spot_prices(symbols: list[str], since: date) -> dict[str, list[dict]]:
    sql = text("""
        SELECT sp.ticker AS symbol, sp.date, sp.close,
               iv.blended_vol * :annualize AS blended_vol
        FROM stock_prices sp
        LEFT JOIN instrument_vol iv ON iv.symbol = sp.ticker AND iv.date = sp.date
        WHERE sp.ticker = ANY(:symbols)
          AND sp.date >= :since
        ORDER BY sp.ticker, sp.date ASC
    """)
    async with get_connection() as conn:
        result = await conn.execute(sql, {"symbols": symbols, "since": since, "annualize": ANNUALIZE})
        rows = result.fetchall()

    if not rows:
        return {}

    df = pd.DataFrame(rows, columns=["symbol", "date", "close", "blended_vol"])
    df["date"] = df["date"].astype(str)
    df["close"] = pd.to_numeric(df["close"]).fillna(0.0)
    df["blended_vol"] = pd.to_numeric(df["blended_vol"])
    return {symbol: group[["date", "close", "blended_vol"]].to_dict("records") for symbol, group in df.groupby("symbol")}


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
    df["scaled_value"] = pd.to_numeric(df["scaled_value"]).fillna(0.0)

    return {
        symbol: group[["date", "rule_name", "scaled_value"]].to_dict("records")
        for symbol, group in df.groupby("symbol")
    }


async def _fetch_calculations(
    symbols: list[str],
    since: date,
    run_id: str,
) -> list[dict]:
    sql = text("""
        SELECT
            symbol, date,
            current_price, ewma_vol,
            combined_forecast, desired_position,
            subsystem_position, portfolio_position,
            instrument_value_volatility, vol_scalar,
            run_id
        FROM portfolio_calculations
        WHERE symbol = ANY(:symbols)
          AND date >= :since
          AND run_id = :run_id
        ORDER BY symbol, date ASC
    """)
    async with get_connection() as conn:
        result = await conn.execute(
            sql, {"symbols": symbols, "since": since, "run_id": run_id}
        )
        rows = result.fetchall()

    if not rows:
        return []

    cols = ["symbol", "date"] + CALC_NUMERIC_COLS + ["run_id"]
    df = pd.DataFrame(rows, columns=cols)
    df["date"] = df["date"].astype(str)
    for col in CALC_NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col]).fillna(0.0)

    return df.to_dict("records")
