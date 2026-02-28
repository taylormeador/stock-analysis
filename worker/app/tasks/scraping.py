import logging

import app.logic.cboe as cboe
import app.logic.reddit as reddit
from app.celery_app import app
from app.utils import (
    TaskStatusTracker,
    SingleInstanceTask,
    track_task_metrics,
)

logger = logging.getLogger(__name__)


@app.task(base=SingleInstanceTask, bind=True)
@track_task_metrics
def scrape_reddit_wsb_daily_thread(
    self,
    filter: str,
    limit: int,
):
    """Scrape Reddit WSB daily thread for ticker mentions."""
    tracker = TaskStatusTracker(
        task_id=self.request.id,
        component_name="WSB Daily Thread Scraper",
        task_description=f"Scrapes r/wallstreetbets daily discussion {filter} comments",
    )
    tracker.start_task()

    try:
        reddit.scrape_reddit_wsb_daily_thread(filter, limit, tracker)
        tracker.complete_task()
        return True

    except Exception as e:
        logger.exception("reddit scraping task failure: ")
        tracker.fail_task(str(e))
        raise


@app.task(bind=True, queue="long-running")
@track_task_metrics
def scrape_reddit_historical_data(self):
    tracker = TaskStatusTracker(
        task_id=self.request.id,
        component_name="Reddit Historical Data Scraper",
        task_description="Scrapes downloaded Reddit historical data",
    )
    tracker.start_task()

    try:
        reddit.scrape_historical_data(tracker)
        tracker.complete_task()
        return True

    except Exception as e:
        logger.exception("error in historical scraping task: ")
        tracker.fail_task(str(e))
        raise


@app.task(base=SingleInstanceTask, bind=True)
def scrape_cboe_daily_stats(
    self,
    start_date_str: str | None = None,
    end_date_str: str | None = None,
):
    """Scrape CBOE website for daily options statistics."""
    tracker = TaskStatusTracker(
        task_id=self.request.id,
        component_name="CBOE Options Data",
        task_description="Put/call ratios, volume, and open interest",
    )
    tracker.start_task()

    try:
        cboe.scrape_daily_market_stats(tracker, start_date_str, end_date_str)
        tracker.complete_task()
        return True

    except Exception as e:
        logger.exception("error while scraping CBOE data")
        tracker.fail_task(str(e))
        raise


@app.task
def scrape_stocktwits():
    """Scrape StockTwits for stock mentions"""
    print("Scraping StockTwits...")
    # Your scraping logic here
    return "StockTwits scraping complete"
