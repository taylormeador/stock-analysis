import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
import pandas as pd

import redis
import yfinance as yf

import app.logic.fred as fred
import app.logic.stock_data as stocks
from app.celery_app import app
from app.utils import TICKERS, ETLStatusTracker, SingleInstanceTask, Status

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

    # Default to yesterday/today for start/end date.
    if start_date is None:
        start_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
    if end_date is None:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info(f"Fetching data for dates: {start_date} to {end_date}")

    num_tickers = len(TICKERS)

    total_records = 0
    failed_tickers = []
    for idx, ticker in enumerate(sorted(TICKERS)):
        try:
            df = stocks.fetch_historical_data(ticker, start_date, end_date)
            if df.empty:
                logger.warning(f"{ticker}: No records to insert")
                failed_tickers.append(ticker)
                continue

            df = stocks.calculate_indicators(df)
            stocks.load_price_data(df, ticker, start_date, end_date)

            # Update progress and add small delay between tickers to avoid rate limiting
            tracker.update_progress(idx / num_tickers, persist=True)
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Failed to process {ticker}: {str(e)}")
            failed_tickers.append(ticker)
            continue

    logger.info(f"Stock price fetch complete. Total records: {total_records}")
    tracker.complete_task()

    if failed_tickers:
        logger.warning(f"Failed tickers: {', '.join(failed_tickers)}")


@app.task(base=SingleInstanceTask)
def update_current_prices_cache():
    """
    Fetch current prices for tracked tickers and cache in Redis.
    Runs every 1-2 minutes to keep prices fresh during market hours.
    """
    logger.info("Updating current prices cache")

    redis_client = redis.Redis.from_url(os.environ["REDIS_URL"])

    # Create ticker objects
    tickers = yf.Tickers(" ".join(sorted(TICKERS)))

    price_data = []
    for ticker_symbol in TICKERS:  # TODO get tickers from db
        try:
            ticker = tickers.tickers[ticker_symbol]
            fast_info = ticker.fast_info
            last_price = fast_info.get("lastPrice") or fast_info.get(
                "regularMarketPrice"
            )
            year_change = fast_info.get("yearChange")
            last_close = fast_info.get("previousClose")
            day_change = last_price / last_close - 1
            year_change = fast_info.get("yearChange")

            ticker_data = {
                "ticker": ticker_symbol,
                "price": last_price,
                "day_change": day_change,
                "year_change": year_change,
            }
            price_data.append(ticker_data)

        except Exception as e:
            logger.warning(f"Could not get price for {ticker_symbol}: {e}")
            continue

    redis_client.set(
        name="current_prices",
        value=json.dumps(price_data),
    )

    logger.info(f"Updated prices for {len(price_data)} tickers")


@app.task(bind=True)
def get_fred_data(self):
    """Get macro data from FRED API."""
    tracker = ETLStatusTracker(
        task_id=self.request.id,
        component_name="FRED Macro Indicators",
        task_description="Treasury yields, Fed funds rate, dollar index, unemployment",
    )
    try:
        fred.get_fred_data(tracker)
    except Exception:
        tracker.update_status(Status.FAILED)
        raise


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    update_current_prices_cache()
