import logging

from app.celery_app import app
from app.utils import TaskStatusTracker
import app.logic.portfolio as logic

logger = logging.getLogger(__name__)


@app.task(bind=True)
def generate_ewmac_forecasts(self):
    """Generate EWMAC forecasts for all futures instruments and write to forecasts table."""
    tracker = TaskStatusTracker(
        task_id=self.request.id,
        component_name="EWMAC Forecast Generation",
        task_description="Generates trend following forecasts for futures instruments",
    )
    tracker.start_task()

    try:
        logic.run_ewmac_forecasts(tracker)
        tracker.complete_task()
        return True

    except Exception as e:
        logger.exception("error while generating EWMAC forecasts: ")
        tracker.fail_task(str(e))
        raise