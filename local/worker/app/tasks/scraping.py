import logging

import app.logic.cboe as cboe
import app.logic.reddit as reddit
from app.celery_app import app
from app.utils import SingleInstanceTask

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


@app.task
def scrape_reddit_wsb_daily_thread(filter: str, limit: int):
    """Scrape Reddit WSB daily thread for ticker mentions."""

    reddit.scrape_reddit_wsb_daily_thread(filter, limit)

    return


@app.task(base=SingleInstanceTask)
def scrape_cboe_daily_stats():
    """Scrape CBOE website for daily options statistics."""

    cboe.scrape_daily_market_stats()

    return


@app.task
def scrape_stocktwits():
    """Scrape StockTwits for stock mentions"""
    print("Scraping StockTwits...")
    # Your scraping logic here
    return "StockTwits scraping complete"
