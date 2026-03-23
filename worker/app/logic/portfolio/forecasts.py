import logging
from datetime import date

from sqlalchemy import text

import app.database.db as db
from app.logic.portfolio.utils import fetch_active_instruments, fetch_instruments
from app.logic.portfolio.ewmac import LOOKBACK_DAYS
from app.logic.portfolio.utils import fetch_prices
from app.logic.portfolio import rules
from app.utils import TaskStatusTracker

logger = logging.getLogger(__name__)


def upsert_forecasts(rows: list[dict]) -> None:
    sql = text("""
        INSERT INTO forecasts (symbol, rule_name, date, raw_value, scaled_value)
        VALUES (:symbol, :rule_name, :date, :raw_value, :scaled_value)
        ON CONFLICT (symbol, rule_name, date) DO UPDATE SET
            raw_value    = EXCLUDED.raw_value,
            scaled_value = EXCLUDED.scaled_value
    """)
    with db.get_connection() as conn:
        conn.execute(sql, rows)
        conn.commit()


def generate_forecasts(
    tracker: TaskStatusTracker,
    as_of: date,
    variations: list[str] | None = None,
    symbols: list[str] | None = None,
) -> None:
    """
    Generate forecasts for all variations on a given date.

    Args:
        tracker:    Task status tracker.
        as_of:      Date to generate forecasts for.
        variations: Variation names to run. Defaults to all registered variations.
        symbols:    Restrict to a subset of symbols. Defaults to all active instruments.
    """
    if variations is None:
        variations = list(rules.VARIATION_REGISTRY.keys())

    if symbols is not None:
        instruments = fetch_instruments(symbols)
    else:
        instruments = fetch_active_instruments()

    if not instruments:
        logger.warning("No instruments found")
        tracker.update_status_message("No instruments found")
        return

    if not variations:
        logger.warning("No variations provided")
        tracker.update_status_message("No variations provided")
        return

    rows = []
    num_instruments = len(instruments)

    for i, instrument in enumerate(instruments):
        symbol = instrument["symbol"]
        label = instrument["label"]

        logger.info(f"Processing {label} ({symbol})")
        tracker.update_status_message(f"Processing {label} ({i + 1}/{num_instruments})")

        try:
            prices = fetch_prices(symbol, as_of, LOOKBACK_DAYS)
        except Exception as e:
            logger.error(f"Failed to fetch prices for {symbol}: {e}")
            continue

        if len(prices) < 130:
            logger.warning(f"Insufficient price history for {symbol}, skipping")
            continue

        for variation_name in variations:
            try:
                variation = rules.get_variation(variation_name)
                result = variation.forecaster(variation_name, prices, as_of)
                if result is None:
                    logger.warning(
                        f"No result for {symbol} {variation_name} on {as_of}"
                    )
                    continue

                rows.append(
                    {
                        "symbol": symbol,
                        "rule_name": result["rule_name"],
                        "date": as_of,
                        "raw_value": result["raw_value"],
                        "scaled_value": result["scaled_value"],
                    }
                )

                logger.info(
                    f"  {result['rule_name']}: "
                    f"raw={result['raw_value']:.4f} "
                    f"scaled={result['scaled_value']:.2f}"
                )

            except Exception as e:
                logger.error(f"Failed {variation_name} for {symbol}: {e}")
                continue

        tracker.update_progress((i + 1) / num_instruments)

    if rows:
        upsert_forecasts(rows)
        logger.info(f"Wrote {len(rows)} forecast rows for {as_of}")
        tracker.update_status_message(f"Wrote {len(rows)} forecast rows for {as_of}")
    else:
        logger.warning("No forecast rows generated")
        tracker.update_status_message("No forecast rows generated")
