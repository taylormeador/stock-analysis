import logging
from datetime import datetime, timezone, timedelta
import os
import json

import time
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from sqlalchemy.dialects.postgresql import insert
import redis

import app.database.db as db
import app.database.models as models
from app.utils import TaskStatusTracker, get_tickers

logger = logging.getLogger(__name__)


redis_client = redis.Redis.from_url(os.environ["REDIS_URL"])


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


def fetch_stock_data(
    tracker: TaskStatusTracker,
    start_date: str | None = None,
    end_date: str | None = None,
):
    # Default to yesterday/today for start/end date.
    if start_date is None:
        start_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
    if end_date is None:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info(f"Fetching data for dates: {start_date} to {end_date}")
    tracker.update_status_message(
        f"Fetching data for dates: {start_date} to {end_date}"
    )

    tickers = get_tickers()
    num_tickers = len(tickers)

    total_records = 0
    failed_tickers = []
    for idx, ticker in enumerate(sorted(tickers)):
        try:
            df = fetch_historical_data(ticker, start_date, end_date)
            if df.empty:
                logger.warning(f"{ticker}: No records to insert")
                failed_tickers.append(ticker)
                continue

            df = calculate_indicators(df)
            load_price_data(df, ticker, start_date, end_date)

            # Update progress and add small delay between tickers to avoid rate limiting
            tracker.update_progress(idx / num_tickers, persist=True)
            tracker.update_status_message(f"Fetched data for {ticker}")
            total_records += 1
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Failed to process {ticker}: {str(e)}")
            failed_tickers.append(ticker)
            continue

    logger.info(f"Stock price fetch complete. Total records: {total_records}")
    tracker.update_status_message(f"Fetched data for {total_records} tickers")

    if failed_tickers:
        logger.warning(f"Failed tickers: {', '.join(failed_tickers)}")


def update_cache(tracker: TaskStatusTracker):
    logger.info("Updating current prices cache")

    # Create ticker objects
    tickers = get_tickers(yf_tickers=True)
    ticker_objects = yf.Tickers(" ".join(sorted(tickers)))

    price_data = {}
    for ticker_symbol in tickers:
        try:
            ticker = ticker_objects.tickers[ticker_symbol]
            fast_info = ticker.fast_info
            last_price = fast_info.get("lastPrice") or fast_info.get(
                "regularMarketPrice"
            )
            year_change = fast_info.get("yearChange")
            last_close = fast_info.get("previousClose")
            day_change = last_price / last_close - 1
            year_change = fast_info.get("yearChange")

            ticker_data = {
                "price": last_price,
                "day_change": day_change,
                "year_change": year_change,
            }
            price_data[ticker_symbol] = ticker_data
            tracker.update_progress(len(price_data) / len(tickers), persist=True)

        except Exception as e:
            logger.warning(f"Could not get price for {ticker_symbol}: {e}")
            continue

    redis_client.set(
        name="current_prices",
        value=json.dumps(price_data),
    )
    tracker.update_status_message("Cache refreshed")
    logger.info(f"Updated prices for {len(price_data)} tickers")
