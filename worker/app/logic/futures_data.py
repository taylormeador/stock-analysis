import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import yfinance as yf
from sqlalchemy import text

import app.database.db as db
from app.utils import TaskStatusTracker

logger = logging.getLogger(__name__)

EWMA_VOL_SPAN = 36
LONG_TERM_VOL_WEIGHT = 0.3
SHORT_TERM_VOL_WEIGHT = 0.7


def fetch_active_instruments() -> list[dict]:
    sql = text("""
        SELECT symbol, label, price_source
        FROM instruments
        WHERE is_active = TRUE
    """)
    with db.get_connection() as conn:
        result = conn.execute(sql)
        return [{"symbol": row.symbol, "label": row.label, "price_source": row.price_source} for row in result]


def fetch_trading_instruments() -> list[dict]:
    sql = text("""
        SELECT symbol, label, multiplier
        FROM instruments
        WHERE is_trading = TRUE
    """)
    with db.get_connection() as conn:
        result = conn.execute(sql)
        return [
            {
                "symbol": row.symbol,
                "label": row.label,
                "multiplier": float(row.multiplier),
            }
            for row in result
        ]


def fetch_all_prices_from_db(symbol: str, price_source: str = "futures_prices") -> pd.Series:
    """Fetch full price history for vol calculation."""
    if price_source == "stock_prices":
        sql = text("""
            SELECT date, close
            FROM stock_prices
            WHERE ticker = :symbol
              AND close IS NOT NULL
            ORDER BY date ASC
        """)
    else:
        sql = text("""
            SELECT date, close
            FROM futures_prices
            WHERE symbol = :symbol
              AND close IS NOT NULL
            ORDER BY date ASC
        """)
    with db.get_connection() as conn:
        df = pd.read_sql(sql, conn, params={"symbol": symbol})

    if df.empty:
        return pd.Series(dtype=float)

    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["close"].astype(float)


def fetch_prices_from_yfinance(
    symbol: str, start_date: str, end_date: str
) -> pd.DataFrame:
    df = yf.download(
        symbol,
        start=start_date,
        end=end_date,
        progress=False,
        auto_adjust=True,
    )
    if df is None or df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index.name = "date"
    df.reset_index(inplace=True)
    df["symbol"] = symbol
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def calc_vol_series(prices: pd.Series) -> pd.DataFrame:
    """
    Calculate short term, long term, and blended vol for each date in the series.

    Short term: 36-day EWMA vol
    Long term: expanding window standard deviation using all available history
    Blended: 70% short term + 30% long term, unless short term > long term
             in which case short term is used directly (always respond to vol increases)
    """
    returns = prices.pct_change().dropna()

    short_term_vol = (
        returns.pow(2).ewm(span=EWMA_VOL_SPAN, adjust=False).mean().pow(0.5)
    )
    long_term_vol = returns.expanding().std()

    blended_vol = pd.Series(index=short_term_vol.index, dtype=float)
    for dt in short_term_vol.index:
        st = short_term_vol[dt]
        lt = long_term_vol[dt]
        if pd.isna(st) or pd.isna(lt):
            blended_vol[dt] = np.nan
        elif st >= lt:
            blended_vol[dt] = st
        else:
            blended_vol[dt] = SHORT_TERM_VOL_WEIGHT * st + LONG_TERM_VOL_WEIGHT * lt

    return pd.DataFrame(
        {
            "short_term_vol": short_term_vol,
            "long_term_vol": long_term_vol,
            "blended_vol": blended_vol,
        }
    )


def upsert_prices(rows: list[dict]) -> None:
    sql = text("""
        INSERT INTO futures_prices (symbol, date, open, high, low, close, volume)
        VALUES (:symbol, :date, :open, :high, :low, :close, :volume)
        ON CONFLICT (symbol, date) DO UPDATE SET
            open   = EXCLUDED.open,
            high   = EXCLUDED.high,
            low    = EXCLUDED.low,
            close  = EXCLUDED.close,
            volume = EXCLUDED.volume
    """)
    with db.get_connection() as conn:
        conn.execute(sql, rows)
        conn.commit()


def upsert_instrument_vol(symbol: str, vol_df: pd.DataFrame) -> None:
    sql = text("""
        INSERT INTO instrument_vol (symbol, date, short_term_vol, long_term_vol, blended_vol)
        VALUES (:symbol, :date, :short_term_vol, :long_term_vol, :blended_vol)
        ON CONFLICT (symbol, date) DO UPDATE SET
            short_term_vol = EXCLUDED.short_term_vol,
            long_term_vol  = EXCLUDED.long_term_vol,
            blended_vol    = EXCLUDED.blended_vol
    """)
    rows = []
    for dt, row in vol_df.iterrows():
        if pd.isna(row["blended_vol"]):
            continue
        rows.append(
            {
                "symbol": symbol,
                "date": pd.Timestamp(dt).date(),
                "short_term_vol": float(row["short_term_vol"]),
                "long_term_vol": float(row["long_term_vol"]),
                "blended_vol": float(row["blended_vol"]),
            }
        )

    if rows:
        with db.get_connection() as conn:
            conn.execute(sql, rows)
            conn.commit()


def ingest_futures_prices(
    tracker: TaskStatusTracker,
    start_date: str | None = None,
    end_date: str | None = None,
):
    if start_date is None:
        start_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
    if end_date is None:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info(f"Ingesting futures prices from {start_date} to {end_date}")
    tracker.update_status_message(f"Fetching prices from {start_date} to {end_date}")

    all_instruments = fetch_active_instruments()
    instruments = [i for i in all_instruments if i["price_source"] == "futures_prices"]
    num_instruments = len(instruments)

    if not instruments:
        logger.warning("No active futures instruments found")
        tracker.update_status_message("No active futures instruments found")
        return

    total_rows = 0
    failed = []

    for i, instrument in enumerate(instruments):
        symbol = instrument["symbol"]
        label = instrument["label"]
        logger.info(f"Fetching {label} ({symbol})")
        tracker.update_status_message(f"Fetching {label} ({i + 1}/{num_instruments})")

        try:
            df = fetch_prices_from_yfinance(symbol, start_date, end_date)
            if df.empty:
                logger.warning(f"  No data returned for {symbol}")
                failed.append(symbol)
                continue

            rows = []
            for row in df.itertuples():
                if pd.isna(row.close):
                    continue

                rows.append(
                    {
                        "symbol": row.symbol,
                        "date": row.date,
                        "open": float(row.open) if pd.notna(row.open) else None,
                        "high": float(row.high) if pd.notna(row.high) else None,
                        "low": float(row.low) if pd.notna(row.low) else None,
                        "close": float(row.close) if pd.notna(row.close) else None,
                        "volume": int(row.volume) if pd.notna(row.volume) else None,
                    }
                )

            upsert_prices(rows)
            total_rows += len(rows)
            logger.info(f"  Upserted {len(rows)} price rows")

            # Recalculate vol over full history and upsert
            all_prices = fetch_all_prices_from_db(symbol, "futures_prices")
            if len(all_prices) >= EWMA_VOL_SPAN:
                vol_df = calc_vol_series(all_prices)
                upsert_instrument_vol(symbol, vol_df)
                logger.info(f"  Upserted {len(vol_df)} vol rows")
            else:
                logger.warning(
                    f"  Insufficient history for vol calculation on {symbol}"
                )

        except Exception as e:
            logger.error(f"Failed to ingest {symbol}: {e}")
            failed.append(symbol)

        tracker.update_progress((i + 1) / num_instruments)

    message = (
        f"Ingested {total_rows} rows for {num_instruments - len(failed)} instruments"
    )
    if failed:
        message += f" — failed: {', '.join(failed)}"

    logger.info(message)
    tracker.update_status_message(message)


def ingest_spot_vol(tracker: TaskStatusTracker):
    """
    Compute and store vol for active spot instruments.
    Prices are already in stock_prices via fetch_stock_data; this task
    derives instrument_vol from that history.
    """
    all_instruments = fetch_active_instruments()
    instruments = [i for i in all_instruments if i["price_source"] == "stock_prices"]

    if not instruments:
        logger.warning("No active spot instruments found")
        tracker.update_status_message("No active spot instruments found")
        return

    num_instruments = len(instruments)
    failed = []

    for i, instrument in enumerate(instruments):
        symbol = instrument["symbol"]
        label = instrument["label"]
        logger.info(f"Computing vol for {label} ({symbol})")
        tracker.update_status_message(f"Computing vol for {label} ({i + 1}/{num_instruments})")

        try:
            all_prices = fetch_all_prices_from_db(symbol, "stock_prices")
            if len(all_prices) < EWMA_VOL_SPAN:
                logger.warning(f"  Insufficient history for vol calculation on {symbol}")
                failed.append(symbol)
                continue

            vol_df = calc_vol_series(all_prices)
            upsert_instrument_vol(symbol, vol_df)
            logger.info(f"  Upserted {len(vol_df)} vol rows for {symbol}")

        except Exception as e:
            logger.error(f"Failed to compute vol for {symbol}: {e}")
            failed.append(symbol)

        tracker.update_progress((i + 1) / num_instruments)

    message = f"Computed vol for {num_instruments - len(failed)} spot instruments"
    if failed:
        message += f" — failed: {', '.join(failed)}"
    logger.info(message)
    tracker.update_status_message(message)


if __name__ == "__main__":
    tracker = TaskStatusTracker("test", "test", "test")
    ingest_futures_prices(tracker)
