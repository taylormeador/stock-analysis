import os
import logging

from celery import Celery, Task
from sqlalchemy import insert
import redis

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


class SingleInstanceTask(Task):
    def __call__(self, *args, **kwargs):
        lock_id = f"{self.name}-lock"
        redis_client = redis.Redis.from_url(os.environ["REDIS_URL"])
        lock_acquired = redis_client.set(lock_id, "locked", ex=300, nx=True)
        if not lock_acquired:
            logger.info(f"Task {self.name} already running, skipping")
            return None

        try:
            return super().__call__(*args, **kwargs)
        finally:
            redis_client.delete(lock_id)


@app.task(base=SingleInstanceTask)
def scrape_reddit_hot():
    """Scrape Reddit /hot for stock mentions"""

    logger.info("scraping Reddit /hot...")

    post_filter = "hot"
    post_limit = 10

    # TODO refactor to insert to db between posts/comments since rate limit is bottleneck
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
