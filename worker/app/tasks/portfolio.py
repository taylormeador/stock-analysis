import logging
from datetime import date, datetime

from app.celery_app import app
from app.utils import TaskStatusTracker
import app.logic.portfolio as logic

logger = logging.getLogger(__name__)


@app.task(bind=True)
def generate_ewmac_forecasts(self, as_of: str | None = None):
    """
    Generate EWMAC forecasts for all active instruments and strategies.

    Args:
        as_of: Date string in YYYY-MM-DD format. Defaults to today.
               Pass a date to backfill historical forecasts.
    """
    tracker = TaskStatusTracker(
        task_id=self.request.id,
        component_name="EWMAC Forecast Generation",
        task_description="Generates trend following forecasts for futures instruments",
    )
    tracker.start_task()

    parsed_date = datetime.strptime(as_of, "%Y-%m-%d").date() if as_of else date.today()

    try:
        logic.run_ewmac_forecasts(tracker, as_of=parsed_date)
        tracker.complete_task()
        return True

    except Exception as e:
        logger.exception("error while generating EWMAC forecasts: ")
        tracker.fail_task(str(e))
        raise