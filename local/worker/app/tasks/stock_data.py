import logging
import time
from datetime import datetime, timedelta, timezone

from app.celery_app import app
import app.database.db as db
from app.logic.tickers import TICKERS
from app.logic.stock_data import fetch_historical_data, batch_insert
from app.tasks.utils import SingleInstanceTask

logger = logging.getLogger(__name__)


# @app.task(base=SingleInstanceTask)
def fetch_stock_data(start_date: str | None = None, end_date: str | None = None):
    """
    Fetch stock prices for all tracked tickers.

    Date args should be in form "%Y-%m-%d" and they will default to yesterday/today.
    """
    logger.info("Starting stock price fetch")

    # Default to yesterday/today for start/end date.
    if start_date is None:
        start_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
    if end_date is None:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info(f"Fetching data for dates: {start_date} to {end_date}")

    total_records = 0
    failed_tickers = []

    for idx, ticker in enumerate(sorted(TICKERS), 1):
        try:
            # Add small delay between tickers to avoid rate limiting
            if idx > 1:
                time.sleep(1.5)

            records = fetch_historical_data(ticker, start_date, end_date)

            if records:
                with db.get_connection() as conn:
                    inserted = batch_insert(conn, records)
                    conn.commit()
                    total_records += inserted
                    logger.info(f"✓ {ticker}: Inserted {inserted} records")
            else:
                logger.warning(f"✗ {ticker}: No records to insert")
                failed_tickers.append(ticker)

        except Exception as e:
            logger.error(f"Failed to process {ticker}: {str(e)}")
            failed_tickers.append(ticker)

    logger.info(f"Stock price fetch complete. Total records: {total_records}")

    if failed_tickers:
        logger.warning(f"Failed tickers: {', '.join(failed_tickers)}")


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    fetch_stock_data()
