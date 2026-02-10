import logging

from app.celery_app import app
from app.logic import backtest
from app.utils import TaskStatusTracker

logger = logging.getLogger(__name__)


@app.task(bind=True)
def run_backtest(self, backtest_params):
    tracker = TaskStatusTracker(
        task_id=self.request.id,
        component_name="Backtest Runner",
        task_description="Runs backtests and stores results",
    )
    tracker.start_task()

    try:
        backtest.run(backtest_params)
        tracker.complete_task()

    except Exception as e:
        logger.exception("Error while running backtest: ")
        tracker.fail_task(str(e))
