import logging
from datetime import date

import pandas as pd
from sqlalchemy import text

import app.database.db as db

logger = logging.getLogger(__name__)


def fetch_active_instruments() -> list[dict]:
    sql = text("""
        SELECT symbol, label, multiplier, super_asset_class, asset_class, sub_asset_class, region, price_source
        FROM instruments
        WHERE is_active = TRUE
    """)
    with db.get_connection() as conn:
        result = conn.execute(sql)
        return [
            {
                "symbol": row.symbol,
                "label": row.label,
                "multiplier": float(row.multiplier),
                "super_asset_class": row.super_asset_class,
                "asset_class": row.asset_class,
                "sub_asset_class": row.sub_asset_class,
                "region": row.region,
                "price_source": row.price_source,
            }
            for row in result
        ]


def fetch_instrument(symbol: str) -> dict | None:
    sql = text("""
        SELECT symbol, label, multiplier, super_asset_class, asset_class, sub_asset_class, region, price_source
        FROM instruments
        WHERE symbol = :symbol
    """)
    with db.get_connection() as conn:
        result = conn.execute(sql, {"symbol": symbol}).first()

    if result is None:
        return None

    return {
        "symbol": result.symbol,
        "label": result.label,
        "multiplier": float(result.multiplier),
        "super_asset_class": result.super_asset_class,
        "asset_class": result.asset_class,
        "sub_asset_class": result.sub_asset_class,
        "region": result.region,
        "price_source": result.price_source,
    }


def fetch_instruments(symbols: list[str]) -> list[dict]:
    sql = text("""
        SELECT symbol, label, multiplier, super_asset_class, asset_class, sub_asset_class, region, price_source
        FROM instruments
        WHERE symbol = ANY(:symbols)
    """)
    with db.get_connection() as conn:
        result = conn.execute(sql, {"symbols": symbols})
        return [
            {
                "symbol": row.symbol,
                "label": row.label,
                "multiplier": float(row.multiplier),
                "super_asset_class": row.super_asset_class,
                "asset_class": row.asset_class,
                "sub_asset_class": row.sub_asset_class,
                "region": row.region,
                "price_source": row.price_source,
            }
            for row in result
        ]


def fetch_prices(
    symbol: str, as_of: date, lookback_days: int, price_source: str = "futures_prices"
) -> pd.Series:
    if price_source == "stock_prices":
        sql = text("""
            SELECT date, close
            FROM stock_prices
            WHERE ticker = :symbol
              AND date >= CAST(:as_of AS date) - :lookback * INTERVAL '1 day'
              AND date <= :as_of
            ORDER BY date ASC
        """)
    else:
        sql = text("""
            SELECT date, close
            FROM futures_prices
            WHERE symbol = :symbol
              AND date >= CAST(:as_of AS date) - :lookback * INTERVAL '1 day'
              AND date <= :as_of
            ORDER BY date ASC
        """)
    with db.get_connection() as conn:
        df = pd.read_sql(
            sql,
            conn,
            params={"symbol": symbol, "lookback": lookback_days, "as_of": as_of},
        )

    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["close"].astype(float)


def fetch_current_price(symbol: str, as_of: date, price_source: str = "futures_prices") -> float | None:
    if price_source == "stock_prices":
        sql = text("""
            SELECT close
            FROM stock_prices
            WHERE ticker = :symbol
              AND date <= :as_of
              AND close IS NOT NULL
            ORDER BY date DESC
            LIMIT 1
        """)
    else:
        sql = text("""
            SELECT close
            FROM futures_prices
            WHERE symbol = :symbol
              AND date <= :as_of
              AND close IS NOT NULL
            ORDER BY date DESC
            LIMIT 1
        """)
    with db.get_connection() as conn:
        result = conn.execute(sql, {"symbol": symbol, "as_of": as_of}).scalar()

    return float(result) if result is not None else None
