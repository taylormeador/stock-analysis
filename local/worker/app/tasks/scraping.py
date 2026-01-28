import logging

from sqlalchemy import insert

from app.celery_app import app
import app.database.db as db
import app.database.models as models
import app.logic.reddit as reddit
from app.tasks.utils import SingleInstanceTask

logger = logging.getLogger(__name__)


@app.task(base=SingleInstanceTask)
def scrape_reddit_hot():
    """Scrape Reddit /hot for stock mentions"""

    logger.info("scraping Reddit /hot...")

    post_filter = "hot"
    post_limit = 10
    reddit.scrape(post_filter=post_filter, post_limit=post_limit)

    logger.info("Reddit /hot scraping complete")
    return


@app.task
def scrape_stocktwits():
    """Scrape StockTwits for stock mentions"""
    print("Scraping StockTwits...")
    # Your scraping logic here
    return "StockTwits scraping complete"
