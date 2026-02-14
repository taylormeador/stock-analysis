import os

from celery import Celery

# Celery configuration
app = Celery("stock_analysis")
app.conf.broker_url = os.getenv("REDIS_URL")  # type: ignore
app.conf.result_backend = os.getenv("REDIS_URL")  # type: ignore
