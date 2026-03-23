import logging
from datetime import date, datetime

from app.celery_app import app
from app.utils import TaskStatusTracker
import app.logic.portfolio.portfolio as portfolio
import app.logic.portfolio.forecasts as forecasts

logger = logging.getLogger(__name__)


@app.task(bind=True)
def generate_forecasts(
    self,
    variations: list[str] | None = None,
    as_of: str | None = None,
    symbols: list[str] | None = None,
):
    """
    Generate EWMAC forecasts for a given date.

    Args:
        variations: Rule variation names to run, e.g. ['ewmac_8_32', 'ewmac_16_64'].
        as_of:      Date string YYYY-MM-DD. Defaults to today.
        symbols:    Restrict to a subset of symbols. Defaults to all active instruments.
    """
    tracker = TaskStatusTracker(
        task_id=self.request.id,
        component_name="Forecast Generation",
        task_description="Generates forecasts for trading strategy variations",
    )
    tracker.start_task()

    parsed_date = datetime.strptime(as_of, "%Y-%m-%d").date() if as_of else date.today()

    try:
        forecasts.generate_forecasts(
            tracker=tracker,
            as_of=parsed_date,
            variations=variations,
            symbols=symbols,
        )
        tracker.complete_task()
        return True

    except Exception as e:
        logger.exception("error while generating EWMAC forecasts: ")
        tracker.fail_task(str(e))
        raise


@app.task(bind=True)
def run_portfolio_calculations(
    self,
    variations: list[str] | None = None,
    as_of: str | None = None,
    symbols: list[str] | None = None,
    capital: float | None = None,
):
    """
    Run portfolio calculations for a given date.

    Args:
        variations: Rule variation names to combine, e.g. ['ewmac_8_32', 'ewmac_16_64'].
        as_of:      Date string YYYY-MM-DD. Defaults to today.
        symbols:    Restrict to a subset of symbols. Defaults to all active instruments.
        capital:    Trading capital in dollars. If None, reads from portfolio table.
    """
    tracker = TaskStatusTracker(
        task_id=self.request.id,
        component_name="Portfolio Calculations",
        task_description="Computes target positions for all active instruments",
    )
    tracker.start_task()

    parsed_date = datetime.strptime(as_of, "%Y-%m-%d").date() if as_of else date.today()

    try:
        portfolio.run_portfolio_calculations(
            tracker=tracker,
            as_of=parsed_date,
            variations=variations,
            symbols=symbols,
            capital=capital,
        )
        tracker.complete_task()
        return True

    except Exception as e:
        logger.exception("error while running portfolio calculations: ")
        tracker.fail_task(str(e))
        raise
