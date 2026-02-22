import logging

import app.logic.backtests.diagonal_spread as pmcc
from app.celery_app import app
from app.utils import TaskStatusTracker, SingleInstanceTask

logger = logging.getLogger(__name__)


@app.task(base=SingleInstanceTask, bind=True)
def run_pmcc_backtest(self, ticker: str, start_date: str, end_date: str):
    tracker = TaskStatusTracker(
        task_id=self.request.id,
        component_name="Backtest Worker",
        task_description="Backtest PMCC/Diagonal Call Spread strategy",
    )
    tracker.start_task()

    try:
        pmcc.run_backtest(ticker, start_date, end_date)
        tracker.complete_task()

    except Exception as e:
        logger.exception("Exception while running backtest: ")
        tracker.fail_task(str(e))
