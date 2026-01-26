import os
import logging

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import insert

import database.db as db
import database.models as models
import reddit

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

# Celery configuration
app = Celery("tasks")
app.conf.broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
app.conf.result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Celery Beat schedule
app.conf.beat_schedule = {
    "scrape-reddit-hot": {
        "task": "tasks.scrape_reddit_hot",
        "schedule": 300.0,
    },
}


@app.task
def scrape_reddit_new():
    """Scrape Reddit /new for stock mentions"""

    logger.info("scraping Reddit /new...")

    post_filter = "new"
    post_limit = 10
    posts, comments = reddit.scrape(post_filter=post_filter, post_limit=post_limit)

    posts_statement = insert(models.reddit_posts)
    comments_statement = insert(models.reddit_comments)
    with db.get_connection() as conn:
        logger.info(f"inserting {len(posts)} posts and {len(comments)} comments")
        conn.execute(posts_statement, posts)
        conn.execute(comments_statement, comments)
        conn.commit()

    logger.info("Reddit /new scraping complete")
    return


@app.task
def scrape_reddit_hot():
    """Scrape Reddit /hot for stock mentions"""

    logger.info("scraping Reddit /hot...")

    post_filter = "hot"
    post_limit = 10
    posts, comments = reddit.scrape(post_filter=post_filter, post_limit=post_limit)

    posts_statement = insert(models.reddit_posts)
    comments_statement = insert(models.reddit_comments)
    with db.get_connection() as conn:
        logger.info(f"inserting {len(posts)} posts and {len(comments)} comments")
        conn.execute(posts_statement, posts)
        conn.execute(comments_statement, comments)
        conn.commit()

    logger.info("Reddit /hot scraping complete")
    return


@app.task
def scrape_stocktwits():
    """Scrape StockTwits for stock mentions"""
    print("Scraping StockTwits...")
    # Your scraping logic here
    return "StockTwits scraping complete"
