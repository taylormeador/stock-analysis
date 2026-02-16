import logging
import os

from app.celery_app import app
import app.logic.sentiment_analysis as logic
from app.utils import (
    TaskStatusTracker,
    track_task_metrics,
)

logger = logging.getLogger(__name__)

# Configuration
SENTIMENT_BATCH_SIZE = int(os.getenv("SENTIMENT_BATCH_SIZE", "10000"))
SENTIMENT_NUM_BATCHES = int(os.getenv("SENTIMENT_NUM_BATCHES", "10"))


@app.task(bind=True)
@track_task_metrics
def generate_vader_sentiment(self):
    """
    Generate VADER sentiment scores for historical Reddit comments.
    Processes in batches.
    """
    tracker = TaskStatusTracker(
        task_id=self.request.id,
        component_name="VADER Sentiment Analysis",
        task_description="Generates VADER sentiment scores for historical comments",
    )
    tracker.start_task()

    try:
        logic.run_vader_analysis(tracker)
        tracker.complete_task()
        return True

    except Exception as e:
        logger.exception("Error generating VADER sentiment")
        tracker.fail_task(str(e))
        raise


@app.task(bind=True, queue="gpu")
@track_task_metrics
def generate_finbert_sentiment(self):
    """
    Generate FinBERT sentiment scores for historical Reddit comments.
    Processes in batches.
    """
    tracker = TaskStatusTracker(
        task_id=self.request.id,
        component_name="FinBERT Sentiment Analysis",
        task_description="Generates FinBERT sentiment scores for historical comments",
    )
    tracker.start_task()

    try:
        logic.run_finbert_analysis(tracker)
        tracker.complete_task()
        return True

    except Exception as e:
        logger.exception("Error generating FinBERT sentiment")
        tracker.fail_task(str(e))
        raise
