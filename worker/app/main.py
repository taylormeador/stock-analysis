import logging
from celery.schedules import crontab
from datetime import timedelta, date

from app.celery_app import app
from app.tasks import scraping  # noqa: F401
from app.tasks import apis  # noqa: F401
from app.tasks import embeddings  # noqa: F401
from app.tasks import sentiment  # noqa: F401
from app.tasks import backtests  # noqa: F401
from app.tasks import portfolio  # noqa: F401

from celery import signals
from app.utils import start_metrics_server


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
    "generate-real-time-embeddings": {
        "task": "app.tasks.embeddings.generate_real_time_embeddings",
        "schedule": 600.0,
    },
    # We want to generate summaries at premarket, mid day, close, and evening.
    # This is not exact due to daylight savings, but it's close enough for my purposes.
    "generate-real-time-llm-summary-premarket": {
        "task": "app.tasks.embeddings.summarize_real_time_topics",
        "schedule": crontab(hour="14", minute="0"),
    },
    "generate-real-time-llm-summary-midday": {
        "task": "app.tasks.embeddings.summarize_real_time_topics",
        "schedule": crontab(hour="17", minute="0"),
    },
    "generate-real-time-llm-summary-close": {
        "task": "app.tasks.embeddings.summarize_real_time_topics",
        "schedule": crontab(hour="21", minute="0"),
    },
    "generate-real-time-llm-summary-evening": {
        "task": "app.tasks.embeddings.summarize_real_time_topics",
        "schedule": crontab(hour="2", minute="0"),
    },
    "fetch-daily-stock-data": {
        "task": "app.tasks.apis.fetch_stock_data",
        "schedule": crontab(hour="8", minute="0"),
    },
    "update-current-prices": {
        "task": "app.tasks.apis.update_current_prices_cache",
        "schedule": 120.0,
    },
    # I don't know when the data is updated so we look back a couple days
    "fetch-daily-cboe-stats": {
        "task": "app.tasks.scraping.scrape_cboe_daily_stats",
        "kwargs": {"start_date_str": two_days_ago_str, "end_date_str": today_str},
        "schedule": crontab(hour="8", minute="0"),
    },
    "get-fred-data": {
        "task": "app.tasks.apis.get_fred_data",
        "schedule": crontab(hour="8", minute="0"),
    },
    "get-td-eod-options-data": {
        "task": "app.tasks.apis.get_eod_options_data",
        "schedule": crontab(hour="8", minute="0"),
    },
    "get-futures-data": {
        "task": "app.tasks.apis.ingest_futures_prices",
        "schedule": crontab(hour="*", minute="0"),
    },
    # Daily portfolio pipeline — forecasts first, then calculations
    "generate-daily-forecasts": {
        "task": "app.tasks.portfolio.generate_forecasts",
        "kwargs": {"as_of": today_str},
        "schedule": crontab(hour="8", minute="30"),
    },
    "run-daily-portfolio-calculations": {
        "task": "app.tasks.portfolio.run_portfolio_calculations",
        "kwargs": {
            "start_date": today_str,
            "end_date": today_str,
            "run_id": "daily",
        },
        "schedule": crontab(hour="8", minute="45"),
    },
}


@signals.worker_ready.connect
def start_prometheus_server(**kwargs):
    """Start Prometheus metrics server when worker is ready."""
    start_metrics_server()
