import logging

import app.logic.fred as fred
import app.logic.stock_data as stocks
from app.celery_app import app
from app.utils import ETLStatusTracker, SingleInstanceTask

logger = logging.getLogger(__name__)


@app.task(base=SingleInstanceTask, bind=True)
def fetch_stock_data(self, start_date: str | None = None, end_date: str | None = None):
    """
    Fetch stock prices for all tracked tickers.

    Date args should be in form "%Y-%m-%d" and they will default to yesterday/today.
    """
    logger.info("Starting stock price fetch")
    tracker = ETLStatusTracker(
        task_id=self.request.id,
        component_name="Stock Price Data",
        task_description="Daily OHLCV data with technical indicators",
    )
    tracker.start_task()

    try:
        stocks.fetch_stock_data(tracker, start_date, end_date)
        tracker.complete_task()
        return True

    except Exception as e:
        logger.exception("failure while fetching stock data: ")
        tracker.fail_task(str(e))
        raise


@app.task(base=SingleInstanceTask, bind=True)
def update_current_prices_cache(self):
    """
    Fetch current prices for tracked tickers and cache in Redis.
    Runs every 1-2 minutes to keep prices fresh during market hours.
    """
    tracker = ETLStatusTracker(
        task_id=self.request.id,
        component_name="Stock Price Data",
        task_description="Real-time price data for cache",
    )
    tracker.start_task()

    try:
        stocks.update_cache(tracker)
        tracker.complete_task()
        return True

    except Exception as e:
        logger.exception("exception while updating stock price cache: ")
        tracker.fail_task(str(e))
        raise


@app.task(bind=True)
def get_fred_data(self):
    """Get macro data from FRED API."""
    tracker = ETLStatusTracker(
        task_id=self.request.id,
        component_name="FRED Macro Indicators",
        task_description="Treasury yields, Fed funds rate, dollar index, unemployment",
    )
    tracker.start_task()

    try:
        fred.get_fred_data(tracker)
        tracker.complete_task()
        return True

    except Exception as e:
        logger.exception("exception while getting FRED data: ")
        tracker.fail_task(str(e))
        raise


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
