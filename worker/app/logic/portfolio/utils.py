import logging
from datetime import date

import pandas as pd
from sqlalchemy import text

import app.database.db as db

logger = logging.getLogger(__name__)


def fetch_active_instruments() -> list[dict]:
    sql = text("""
        SELECT symbol, label, multiplier
        FROM candidate_instruments
        WHERE is_active = TRUE
    """)
    with db.get_connection() as conn:
        result = conn.execute(sql)
        return [
            {
                "symbol":     row.symbol,
                "label":      row.label,
                "multiplier": float(row.multiplier),
            }
            for row in result
        ]


def fetch_active_strategies() -> list[dict]:
    sql = text("""
        SELECT id, strategy_type, parameters
        FROM strategies
        WHERE is_active = TRUE
    """)
    with db.get_connection() as conn:
        result = conn.execute(sql)
        return [
            {
                "id":            row.id,
                "strategy_type": row.strategy_type,
                "parameters":    row.parameters,
            }
            for row in result
        ]


def fetch_prices(symbol: str, as_of: date, lookback_days: int) -> pd.Series:
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