import subprocess
import os
import logging
from app.main import app

logger = logging.getLogger(__name__)


@app.task(bind=True, queue="long-running")
def run_backtest(self, ticker: str, start_date: str, end_date: str):
    process = subprocess.Popen(
        [
            "/usr/local/bin/backtester",
            self.request.task_id,
            ticker,
            start_date,
            end_date,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ},
    )

    for line in process.stdout:
        logger.info(line.rstrip())

    process.wait()

    if process.returncode != 0:
        raise Exception(f"Backtester failed with return code {process.returncode}")
