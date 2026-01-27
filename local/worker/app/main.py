import logging

from celery_app import app
from tasks import scraping

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

# Celery Beat schedule
app.conf.beat_schedule = {
    "scrape-reddit-hot": {
        "task": "tasks.scraping.scrape_reddit_hot",
        "schedule": 300.0,
    },
}
