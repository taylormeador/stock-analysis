import logging
from celery.schedules import crontab

from app.celery_app import app
from app.tasks import scraping
from app.tasks import inference
from app.tasks import stock_data
from app.tasks import data_prep
from app.tasks import model_training

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

# Celery Beat schedule
app.conf.beat_schedule = {
    "scrape-reddit-hot": {
        "task": "app.tasks.scraping.scrape_reddit_hot",
        "schedule": 900.0,
    },
    "run-reddit-comment-inference": {
        "task": "app.tasks.inference.run_sentiment_analysis",
        "schedule": 30.0,
    },
    "fetch-daily-stock-data": {
        "task": "app.tasks.stock_data.fetch_stock_data",
        "schedule": crontab(hour="1", minute="0"),  # Run at 1:00 AM
    },
}
