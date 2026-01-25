from celery import Celery
from celery.schedules import crontab
import os

# Celery configuration
app = Celery("tasks")
app.conf.broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
app.conf.result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Celery Beat schedule
app.conf.beat_schedule = {
    "scrape-reddit-every-5-minutes": {
        "task": "tasks.scrape_reddit",
        "schedule": 300.0,  # 5 minutes in seconds
    },
}


@app.task
def scrape_reddit():
    """Scrape Reddit for stock mentions"""
    print("Scraping Reddit...")
    # Your scraping logic here
    return "Reddit scraping complete"


@app.task
def scrape_stocktwits():
    """Scrape StockTwits for stock mentions"""
    print("Scraping StockTwits...")
    # Your scraping logic here
    return "StockTwits scraping complete"
