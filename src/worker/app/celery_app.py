import os

from celery import Celery

# Celery configuration
app = Celery("stock_analysis")
app.conf.broker_url = os.getenv("CELERY_BROKER_URL")  # type: ignore
app.conf.result_backend = os.getenv("CELERY_RESULT_BACKEND")  # type: ignore
