import logging

from app.celery_app import app
from app.utils import TaskStatusTracker, SingleInstanceTask
import app.logic.tasty as tastytrade

logger = logging.getLogger(__name__)


@app.task(base=SingleInstanceTask, bind=True)
def fetch_tastytrade_data(self):
    """
    Fetch account balances and positions from Tastytrade and cache in Redis.
    Runs every 2 minutes. Cache TTL is 10 minutes so stale data persists
    through brief worker downtime.
    """
    tracker = TaskStatusTracker(
        task_id=self.request.id,
        component_name="Tastytrade",
        task_description="Account balances and positions",
    )
    tracker.start_task()

    try:
        tastytrade.fetch_and_cache(tracker)
        tracker.complete_task()
        return True

    except Exception as e:
        logger.exception("Failed to fetch Tastytrade data")
        tracker.fail_task(str(e))
        raise
