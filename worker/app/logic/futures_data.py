import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf
from sqlalchemy import text

import app.database.db as db
from app.utils import TaskStatusTracker

logger = logging.getLogger(__name__)


def fetch_active_instruments() -> list[dict]:
    sql = text("""
        SELECT symbol, label
        FROM candidate_instruments
        WHERE is_active = TRUE
    """)
    with db.get_connection() as conn:
        result = conn.execute(sql)
        return [{"symbol": row.symbol, "label": row.label} for row in result]


def fetch_prices(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    df = yf.download(
        symbol,
        start=start_date,
        end=end_date,
        progress=False,
        auto_adjust=True,
    )
    if df.empty:
        return pd.DataFrame()

    # yfinance returns MultiIndex columns when downloading a single ticker
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index.name = "date"
    df.reset_index(inplace=True)
    df["symbol"] = symbol
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def upsert_prices(rows: list[tuple]) -> None:
    sql = """
        INSERT INTO futures_prices (symbol, date, open, high, low, close, volume)
        VALUES (:symbol, :date, :open, :high, :low, :close, :volume)
        ON CONFLICT (symbol, date) DO UPDATE SET
            open   = EXCLUDED.open,
            high   = EXCLUDED.high,
            low    = EXCLUDED.low,
            close  = EXCLUDED.close,
            volume = EXCLUDED.volume
    """
    with db.get_connection() as conn:
        conn.execute(text(sql), rows)
        conn.commit()


def ingest_futures_prices(
    tracker: TaskStatusTracker,
    start_date: str | None = None,
    end_date: str | None = None,
):
    if start_date is None:
        start_date = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
    if end_date is None:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info(f"Ingesting futures prices from {start_date} to {end_date}")
    tracker.update_status_message(f"Fetching prices from {start_date} to {end_date}")

    instruments = fetch_active_instruments()
    num_instruments = len(instruments)

    if not instruments:
        logger.warning("No active instruments found in candidate_instruments")
        tracker.update_status_message("No active instruments found")
        return

    total_rows = 0
    failed = []

    for i, instrument in enumerate(instruments):
        symbol = instrument["symbol"]
        label = instrument["label"]
        logger.info(f"Fetching {label} ({symbol})")
        tracker.update_status_message(f"Fetching {label} ({i + 1}/{num_instruments})")

        try:
            df = fetch_prices(symbol, start_date, end_date)
            if df.empty:
                logger.warning(f"  No data returned for {symbol}")
                failed.append(symbol)
                continue

            rows = [
                {
                    "symbol": row.symbol,
                    "date":   row.date,
                    "open":   float(row.open)   if pd.notna(row.open)   else None,
                    "high":   float(row.high)   if pd.notna(row.high)   else None,
                    "low":    float(row.low)    if pd.notna(row.low)    else None,
                    "close":  float(row.close),
                    "volume": int(row.volume)   if pd.notna(row.volume) else None,
                }
                for row in df.itertuples()
            ]

            upsert_prices(rows)
            total_rows += len(rows)
            logger.info(f"  Upserted {len(rows)} rows")

        except Exception as e:
            logger.error(f"Failed to ingest {symbol}: {e}")
            failed.append(symbol)

        tracker.update_progress((i + 1) / num_instruments)

    message = f"Ingested {total_rows} rows for {num_instruments - len(failed)} instruments"
    if failed:
        message += f" — failed: {', '.join(failed)}"

    logger.info(message)
    tracker.update_status_message(message)