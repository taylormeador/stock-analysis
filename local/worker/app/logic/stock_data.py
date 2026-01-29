import logging
from typing import List

import pandas as pd
import yfinance as yf
from sqlalchemy import text


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


def calculate_indicators():
    pass


def batch_insert(conn, records: List[dict], batch_size: int = 1000):
    """
    Insert records in batches for better performance.

    Args:
        conn: Database connection
        records: List of records to insert
        batch_size: Number of records per batch
    """
    stmt = text(
        """
        INSERT INTO stock_prices (ticker, date, open, high, low, close, volume)
        VALUES (:ticker, :date, :open, :high, :low, :close, :volume)
        ON CONFLICT (ticker, date) DO NOTHING
    """
    )

    total_inserted = 0
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        conn.execute(stmt, batch)
        total_inserted += len(batch)

        if total_inserted % 5000 == 0:
            logger.info(f"Inserted {total_inserted}/{len(records)} records")

    return total_inserted
