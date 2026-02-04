import logging

import app.logic.cboe as cboe
import app.logic.reddit as reddit
from app.celery_app import app
from app.utils import (
    ETLStatusTracker,
    SingleInstanceTask,
    Status,
    track_task_metrics,
)

logger = logging.getLogger(__name__)


@app.task(base=SingleInstanceTask)
def scrape_reddit_hot():
    """Scrape Reddit /hot for stock mentions"""
    logger.info("scraping Reddit /hot...")

    post_filter = "hot"
    post_limit = 10
    reddit.scrape(post_filter, post_limit)

    logger.info("Reddit /hot scraping complete")
    return


@app.task(base=SingleInstanceTask, bind=True)
@track_task_metrics
def scrape_reddit_wsb_daily_thread(
    self,
    filter: str,
    limit: int,
):
    """Scrape Reddit WSB daily thread for ticker mentions."""
    tracker = ETLStatusTracker(
        task_id=self.request.id,
        component_name="WSB Daily Thread Scraper",
        task_description=f"Scrapes r/wallstreetbets daily discussion {filter} comments",
    )

    reddit.scrape_reddit_wsb_daily_thread(filter, limit, tracker)

    return


@app.task(bind=True, queue="historical")
@track_task_metrics
def scrape_reddit_historical_data(self):
    tracker = ETLStatusTracker(
        task_id=self.request.id,
        component_name="Reddit Historical Data Scraper",
        task_description="Scrapes downloaded Reddit historical data",
    )
    tracker.start_task()

    try:
        reddit.scrape_historical_data(tracker)
        tracker.complete_task()

    except Exception:
        logger.exception("error in historical scraping task: ")
        tracker.fail_task()


@app.task(base=SingleInstanceTask, bind=True)
def scrape_cboe_daily_stats(
    self,
    start_date_str: str | None = None,
    end_date_str: str | None = None,
):
    """Scrape CBOE website for daily options statistics."""

    tracker = ETLStatusTracker(
        task_id=self.request.id,
        component_name="CBOE Options Data",
        task_description="Put/call ratios, volume, and open interest",
    )
    try:
        cboe.scrape_daily_market_stats(tracker, start_date_str, end_date_str)
    except:
        tracker.update_status(Status.FAILED)
        raise

    return


@app.task
def scrape_stocktwits():
    """Scrape StockTwits for stock mentions"""
    print("Scraping StockTwits...")
    # Your scraping logic here
    return "StockTwits scraping complete"
