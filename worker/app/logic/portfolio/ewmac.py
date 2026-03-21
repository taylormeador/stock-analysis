import logging
from datetime import date

import pandas as pd
from sqlalchemy import text

import app.database.db as db
from app.logic.portfolio.utils import fetch_active_instruments, fetch_prices
from app.utils import TaskStatusTracker

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 250
FORECAST_CAP = 20.0


def calc_ewmac_raw(prices: pd.Series, fast: int, slow: int) -> pd.Series:
    fast_ema = prices.ewm(span=fast, adjust=False).mean()
    slow_ema = prices.ewm(span=slow, adjust=False).mean()
    returns = prices.pct_change()
    price_vol = returns.ewm(span=36, adjust=False).std() * prices
    return (fast_ema - slow_ema) / price_vol


def calc_forecast_scalar(raw: pd.Series) -> float:
    avg_abs = raw.abs().mean()
    if avg_abs == 0:
        return 1.0
    return 10.0 / avg_abs


def scale_and_cap(raw: pd.Series, scalar: float) -> pd.Series:
    return (raw * scalar).clip(-FORECAST_CAP, FORECAST_CAP)


def _parse_ewmac_params(variation_name: str) -> tuple[int, int]:
    """Parse 'ewmac_8_32' into (8, 32)."""
    parts = variation_name.split("_")
    if len(parts) != 3 or parts[0] != "ewmac":
        raise ValueError(f"Cannot parse ewmac variation name: {variation_name!r}")
    return int(parts[1]), int(parts[2])


def run_variation(variation_name: str, prices: pd.Series, as_of: date) -> dict | None:
    """
    Run a single named variation against a price series.
    Returns a result dict or None if no data exists for as_of.
    """
    fast, slow = _parse_ewmac_params(variation_name)

    raw = calc_ewmac_raw(prices, fast, slow)
    scalar = calc_forecast_scalar(raw)
    scaled = scale_and_cap(raw, scalar)

    as_of_mask = scaled.index.date == as_of
    if not as_of_mask.any():
        return None

    return {
        "rule_name": variation_name,
        "raw_value": float(raw[as_of_mask].iloc[-1]),
        "scaled_value": float(scaled[as_of_mask].iloc[-1]),
    }


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


def run_ewmac_forecasts(
    tracker: TaskStatusTracker,
    as_of: date,
    variations: list[str],
    symbols: list[str] | None = None,
) -> None:
    """
    Generate EWMAC forecasts for a given date.

    Args:
        tracker:    Task status tracker.
        as_of:      Date to generate forecasts for.
        variations: List of variation names to run, e.g. ['ewmac_8_32', 'ewmac_16_64'].
                    Caller owns this — not read from DB.
        symbols:    Optional list of symbols to restrict to.
                    If None, runs all active instruments.
    """
    logger.info(f"Generating forecasts as of {as_of} for variations {variations}")

    if symbols is not None:
        from app.logic.portfolio.utils import fetch_instruments

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
                result = run_variation(variation_name, prices, as_of)
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
