import logging
from celery.schedules import crontab
from datetime import timedelta, date

from app.celery_app import app
from app.tasks import scraping  # noqa: F401
from app.tasks import apis  # noqa: F401
from app.tasks import data_prep  # noqa: F401
from app.tasks import model_training  # noqa: F401

from celery import signals
from app.utils import start_metrics_server


# Add this at the bottom, after all your existing config
@signals.worker_ready.connect
def start_prometheus_server(**kwargs):
    """Start Prometheus metrics server when worker is ready."""
    start_metrics_server()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

date_format = "%Y-%m-%d"
two_days_ago = date.today() - timedelta(days=2)
two_days_ago_str = two_days_ago.strftime(date_format)
today = date.today()
today_str = today.strftime(date_format)

# Celery Beat schedule
app.conf.beat_schedule = {
    "scrape-reddit-wsb-daily-thread-new": {
        "task": "app.tasks.scraping.scrape_reddit_wsb_daily_thread",
        "kwargs": {"filter": "new", "limit": 250},
        "schedule": 120.0,
    },
    "scrape-reddit-wsb-daily-thread-top": {
        "task": "app.tasks.scraping.scrape_reddit_wsb_daily_thread",
        "kwargs": {"filter": "top", "limit": 25},
        "schedule": 600.0,
    },
    "scrape-reddit-historical-data": {
        "task": "app.tasks.scraping.scrape_reddit_historical_data",
        "schedule": 3600.0,
    },
    "fetch-daily-stock-data": {
        "task": "app.tasks.apis.fetch_stock_data",
        "schedule": crontab(hour="1", minute="0"),
    },
    "update-current-prices": {
        "task": "app.tasks.apis.update_current_prices_cache",
        "schedule": 120.0,
    },
    # I don't know when the data is updated so we look back a couple days
    # Run at 23:00 UTC = 17:00/18:00 CST/CDT
    "fetch-daily-cboe-stats": {
        "task": "app.tasks.scraping.scrape_cboe_daily_stats",
        "kwargs": {"start_date_str": two_days_ago_str, "end_date_str": today_str},
        "schedule": crontab(hour="23", minute="0"),
    },
    "get-fred-data": {
        "task": "app.tasks.apis.get_fred_data",
        "schedule": crontab(hour="23", minute="0"),
    },
}
