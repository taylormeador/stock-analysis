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
    as_of: str | None = None,
    variations: list[str] | None = None,
    symbols: list[str] | None = None,
):
    """
    Generate EWMAC forecasts for a given date.

    Args:
        as_of:      Date string YYYY-MM-DD. Defaults to today.
        variations: Rule variation names to run. Defaults to all active in DB.
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
        logger.exception("error while generating forecasts: ")
        tracker.fail_task(str(e))
        raise


@app.task(bind=True)
def run_portfolio_calculations(
    self,
    start_date: str,
    end_date: str,
    run_id: str,
    capital: float,
    variations: list[str] | None = None,
    symbols: list[str] | None = None,
    vol_target_pct: float = 0.20,
):
    """
    Run portfolio calculations for a date range.

    Args:
        start_date:     ISO date string YYYY-MM-DD.
        end_date:       ISO date string YYYY-MM-DD.
        run_id:         Human-readable label for this batch, e.g. 'full_universe_2026'.
        capital:        Trading capital in dollars. Always required.
        variations:     Rule variation names to combine. Defaults to all active in DB.
        symbols:        Restrict to a subset of symbols. Defaults to all active instruments.
        vol_target_pct: Annualized vol target as a fraction.
    """
    tracker = TaskStatusTracker(
        task_id=self.request.id,
        component_name="Portfolio Calculations",
        task_description=f"Portfolio calcs [{run_id}]",
    )
    tracker.start_task()

    parsed_start = datetime.strptime(start_date, "%Y-%m-%d").date()
    parsed_end = datetime.strptime(end_date, "%Y-%m-%d").date()

    try:
        portfolio.run_portfolio_calculations(
            tracker=tracker,
            start_date=parsed_start,
            end_date=parsed_end,
            run_id=run_id,
            capital=capital,
            variations=variations,
            symbols=symbols,
            vol_target_pct=vol_target_pct,
        )
        tracker.complete_task()
        return True

    except Exception as e:
        logger.exception("error while running portfolio calculations: ")
        tracker.fail_task(str(e))
        raise
