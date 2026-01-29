#!/usr/bin/env python3
"""
Backfill script to populate historical stock price data.

This script fetches historical OHLCV data for all tracked tickers
and populates the stock_prices table. Run this once to initialize
the database with historical data.

Usage:
    python backfill_stock_prices.py --years 5
    python backfill_stock_prices.py --start-date 2020-01-01
"""

import argparse
import logging
import time
import warnings
from datetime import datetime, timedelta
from typing import List

import app.database.db as db
import pandas as pd
import yfinance as yf
from app.logic.tickers import TICKERS
from sqlalchemy import text

warnings.simplefilter(action="ignore", category=FutureWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
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
                wait_time = 2**attempt  # Exponential backoff: 2, 4, 8 seconds
                logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)

            # Use download instead of Ticker.history for better reliability
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
                    records.append(
                        {
                            "ticker": ticker,
                            "date": date.date(),
                            "open": (
                                round(float(row.Open.iloc[0]), 2)
                                if not pd.isna(row.Open).any()
                                else None
                            ),
                            "high": (
                                round(float(row.High.iloc[0]), 2)
                                if not pd.isna(row.High).bool()
                                else None
                            ),
                            "low": (
                                round(float(row.Low.iloc[0]), 2)
                                if not pd.isna(row.Low).bool()
                                else None
                            ),
                            "close": (
                                round(float(row.Close.iloc[0]), 2)
                                if not pd.isna(row.Close).bool()
                                else None
                            ),
                            "volume": (
                                int(row.Volume.iloc[0])
                                if not pd.isna(row.Volume).bool()
                                else None
                            ),
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Error processing row for {ticker} on {date}: {str(e)}"
                    )
                    breakpoint()
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


def backfill_all_tickers(start_date: str, end_date: str):
    """
    Backfill historical data for all tracked tickers.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    """
    logger.info(f"Starting backfill from {start_date} to {end_date}")
    logger.info(f"Processing {len(TICKERS)} tickers")

    total_records = 0
    failed_tickers = []
    successful_tickers = []

    for idx, ticker in enumerate(sorted(TICKERS), 1):
        try:
            logger.info(f"Processing {idx}/{len(TICKERS)}: {ticker}")

            # Add small delay between tickers to avoid rate limiting
            if idx > 1:
                time.sleep(0.5)

            records = fetch_historical_data(ticker, start_date, end_date)

            if records:
                with db.get_connection() as conn:
                    inserted = batch_insert(conn, records)
                    conn.commit()
                    total_records += inserted
                    successful_tickers.append(ticker)
                    logger.info(f"✓ {ticker}: Inserted {inserted} records")
            else:
                logger.warning(f"✗ {ticker}: No records to insert")
                failed_tickers.append(ticker)

        except Exception as e:
            logger.error(f"✗ {ticker}: Failed - {str(e)}")
            failed_tickers.append(ticker)

    logger.info("=" * 80)
    logger.info("BACKFILL COMPLETE")
    logger.info(f"Total records inserted: {total_records}")
    logger.info(f"Successful tickers: {len(successful_tickers)}/{len(TICKERS)}")

    if failed_tickers:
        logger.warning(
            f"Failed tickers ({len(failed_tickers)}): {', '.join(failed_tickers)}"
        )

    logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Backfill historical stock price data")
    parser.add_argument(
        "--years",
        type=int,
        default=5,
        help="Number of years of historical data to fetch (default: 5)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date in YYYY-MM-DD format (overrides --years)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date in YYYY-MM-DD format (default: today)",
    )

    args = parser.parse_args()

    # Determine start date
    if args.start_date:
        start_date = args.start_date
    else:
        start_date = (datetime.now() - timedelta(days=args.years * 365)).strftime(
            "%Y-%m-%d"
        )

    end_date = args.end_date

    logger.info("Backfill parameters:")
    logger.info(f"  Start date: {start_date}")
    logger.info(f"  End date: {end_date}")
    logger.info(f"  Tickers: {len(TICKERS)}")

    # Ask for confirmation
    response = input("\nProceed with backfill? [y/N]: ")
    if response.lower() != "y":
        logger.info("Backfill cancelled")
        return

    backfill_all_tickers(start_date, end_date)


if __name__ == "__main__":
    main()
