import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List

import pandas as pd
import yfinance as yf
from sqlalchemy import text

from app.celery_app import app
from app.database.db import get_connection
from app.logic.tickers import TICKERS
from app.tasks.utils import SingleInstanceTask

logger = logging.getLogger(__name__)


def fetch_historical_data(
    ticker: str,
    start_date: str,
    end_date: str,
    max_retries: int = 3,
) -> List[dict]:
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

            if df.empty:
                logger.warning(f"No data returned for {ticker}")
                return []

            records = []
            for date, row in df.iterrows():
                try:
                    logger.info(ticker)
                    records.append(
                        {
                            "ticker": ticker,
                            "date": date.date(),
                            "open": (
                                round(float(row.Open.iloc[0]), 2)
                                if not pd.isna(row.Open).all()
                                else None
                            ),
                            "high": (
                                round(float(row.High.iloc[0]), 2)
                                if not pd.isna(row.High).all()
                                else None
                            ),
                            "low": (
                                round(float(row.Low.iloc[0]), 2)
                                if not pd.isna(row.Low).all()
                                else None
                            ),
                            "close": (
                                round(float(row.Close.iloc[0]), 2)
                                if not pd.isna(row.Close).all()
                                else None
                            ),
                            "volume": (
                                int(row.Volume.iloc[0])
                                if not pd.isna(row.Volume).all()
                                else None
                            ),
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Error processing row for {ticker} on {date}: {str(e)}"
                    )
                    continue

            logger.info(f"Fetched {len(records)} historical records for {ticker}")
            return records

        except Exception as e:
            logger.error(
                f"Error fetching historical data for {ticker} (attempt {attempt + 1}/{max_retries}): {str(e)}"
            )
            if attempt == max_retries - 1:
                return []

    return []


@app.task(base=SingleInstanceTask)
def fetch_daily_stock_prices():
    """
    Fetch yesterday's stock prices for all tracked tickers.
    Runs daily to keep the database up to date.
    """
    logger.info("Starting daily stock price fetch")

    # Get yesterday's date (market data is available after market close)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info(f"Fetching data for date: {yesterday}")

    total_records = 0
    failed_tickers = []

    for idx, ticker in enumerate(sorted(TICKERS), 1):
        try:
            # Add small delay between tickers to avoid rate limiting
            if idx > 1:
                time.sleep(1.5)

            records = fetch_historical_data(ticker, yesterday, today)

            if records:
                # Insert records into database
                with get_connection() as conn:
                    # Use INSERT ... ON CONFLICT DO NOTHING to handle duplicates
                    stmt = text(
                        """
                        INSERT INTO stock_prices (ticker, date, open, high, low, close, volume)
                        VALUES (:ticker, :date, :open, :high, :low, :close, :volume)
                        ON CONFLICT (ticker, date) DO NOTHING
                    """
                    )

                    for record in records:
                        conn.execute(stmt, record)

                    conn.commit()
                    total_records += len(records)
                    logger.info(f"Inserted {len(records)} records for {ticker}")
            else:
                logger.warning(f"No records to insert for {ticker}")

        except Exception as e:
            logger.error(f"Failed to process {ticker}: {str(e)}")
            failed_tickers.append(ticker)

    logger.info(f"Daily stock price fetch complete. Total records: {total_records}")

    if failed_tickers:
        logger.warning(f"Failed tickers: {', '.join(failed_tickers)}")

    return {
        "total_records": total_records,
        "failed_tickers": failed_tickers,
        "date": yesterday,
    }


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    fetch_daily_stock_prices()
