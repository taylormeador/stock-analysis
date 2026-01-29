import logging
from datetime import datetime, timedelta, timezone
from typing import List

import yfinance as yf
from sqlalchemy import insert, text

from app.celery_app import app
from app.database.db import get_connection
from app.database import models
from app.logic.tickers import TICKERS
from app.tasks.utils import SingleInstanceTask

logger = logging.getLogger(__name__)


def fetch_stock_data(ticker: str, start_date: str, end_date: str) -> List[dict]:
    """
    Fetch stock data from yfinance for a given ticker and date range.

    Args:
        ticker: Stock ticker symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        List of dictionaries with OHLCV data
    """
    try:
        logger.info(f"Fetching data for {ticker} from {start_date} to {end_date}")

        # Download data from yfinance
        stock = yf.Ticker(ticker)
        df = stock.history(start=start_date, end=end_date)

        if df.empty:
            logger.warning(f"No data returned for {ticker}")
            return []

        # Convert DataFrame to list of dicts
        records = []
        for date, row in df.iterrows():
            records.append(
                {
                    "ticker": ticker,
                    "date": date.date(),
                    "open": round(float(row["Open"]), 2) if row["Open"] else None,
                    "high": round(float(row["High"]), 2) if row["High"] else None,
                    "low": round(float(row["Low"]), 2) if row["Low"] else None,
                    "close": round(float(row["Close"]), 2) if row["Close"] else None,
                    "volume": int(row["Volume"]) if row["Volume"] else None,
                }
            )

        logger.info(f"Fetched {len(records)} records for {ticker}")
        return records

    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {str(e)}")
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

    for ticker in TICKERS:
        try:
            records = fetch_stock_data(ticker, yesterday, today)

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
