import logging

import pandas as pd
import pandas_ta as ta
import yfinance as yf
from sqlalchemy.dialects.postgresql import insert

import app.database.db as db
import app.database.models as models

logger = logging.getLogger(__name__)


def fetch_historical_data(
    ticker: str,
    start_date: str,
    end_date: str,
    max_retries: int = 3,
) -> pd.DataFrame:
    """
    Fetch historical stock data from yfinance with retry logic.

    Args:
        ticker: Stock ticker symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        max_retries: Maximum number of retry attempts

    Returns:
        List of dictionaries with OHLCV data
    """
    import time

    for attempt in range(max_retries):
        try:
            logger.info(
                f"Fetching historical data for {ticker} from {start_date} to {end_date} (attempt {attempt + 1}/{max_retries})"
            )

            # Add delay to avoid rate limiting
            if attempt > 0:
                wait_time = 2**attempt
                logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)

            df = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                progress=False,
            )

            if df is None or df.empty:
                logger.warning(f"No data returned for {ticker}")
                return pd.DataFrame()

            df["ticker"] = ticker
            df.columns = df.columns.get_level_values(0)

            logger.info(f"Fetched {len(df.index)} historical records for {ticker}")
            return df

        except Exception as e:
            logger.error(
                f"Error fetching historical data for {ticker} (attempt {attempt + 1}/{max_retries}): {str(e)}"
            )
            if attempt == max_retries - 1:
                return pd.DataFrame()

    return pd.DataFrame()


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # EMA and SMA
    lengths = (9, 10, 12, 26, 50, 100, 200)
    for length in lengths:
        column_name = f"ema_{length}"
        df[column_name] = ta.ema(df.Close, length=length)

        column_name = f"sma_{length}"
        df[column_name] = ta.sma(df.Close, length=length)

    # RSI
    df["rsi_14"] = ta.rsi(df.Close, length=14)

    # MACD
    df[["macd_12_26_9", "macdh_12_26_9", "macds_12_26_9"]] = ta.macd(
        df.Close,
        fast=12,
        slow=26,
        signal=9,
    )

    # Bollinger Bands
    df[["bbl_20", "bbm_20", "bbu_20", "bbb_20", "bbp_20"]] = ta.bbands(
        df.Close,
        length=2,
    )

    return df


def load_price_data(df: pd.DataFrame, ticker: str, start_date: str, end_date: str):
    """
    Load price data into the database using upsert to handle duplicates.
    Updates existing records if ticker+date already exists.
    """
    # Rename columns to match database schema
    columns = {
        "Open": "open",
        "Close": "close",
        "High": "high",
        "Low": "low",
        "Volume": "volume",
    }
    df = df.rename(columns=columns)
    df["date"] = df.index

    # Convert DataFrame to list of dicts for upsert
    records = df.to_dict("records")

    if not records:
        logger.warning(f"No records to upsert for {ticker}")
        return

    with db.get_connection() as conn:
        # Create upsert statement
        stmt = insert(models.stock_prices).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "date"],  # The unique constraint columns
            set_={
                # Price data
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                # SMA indicators
                "sma_9": stmt.excluded.sma_9,
                "sma_10": stmt.excluded.sma_10,
                "sma_12": stmt.excluded.sma_12,
                "sma_26": stmt.excluded.sma_26,
                "sma_50": stmt.excluded.sma_50,
                "sma_100": stmt.excluded.sma_100,
                "sma_200": stmt.excluded.sma_200,
                # EMA indicators
                "ema_9": stmt.excluded.ema_9,
                "ema_10": stmt.excluded.ema_10,
                "ema_12": stmt.excluded.ema_12,
                "ema_26": stmt.excluded.ema_26,
                "ema_50": stmt.excluded.ema_50,
                "ema_100": stmt.excluded.ema_100,
                "ema_200": stmt.excluded.ema_200,
                # Other indicators
                "rsi_14": stmt.excluded.rsi_14,
                "macd_12_26_9": stmt.excluded.macd_12_26_9,
                "macdh_12_26_9": stmt.excluded.macdh_12_26_9,
                "macds_12_26_9": stmt.excluded.macds_12_26_9,
                # Bollinger Bands
                "bbl_20": stmt.excluded.bbl_20,
                "bbm_20": stmt.excluded.bbm_20,
                "bbu_20": stmt.excluded.bbu_20,
                "bbb_20": stmt.excluded.bbb_20,
                "bbp_20": stmt.excluded.bbp_20,
                # created_at is NOT updated - keeps original timestamp
            },
        )

        conn.execute(stmt)
        conn.commit()

    logger.info(f"Upserted {len(records)} records for {ticker}")
