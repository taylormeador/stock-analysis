import logging
from datetime import date

import pandas as pd
from sqlalchemy import text

import app.database.db as db
from app.logic.portfolio.utils import fetch_active_instruments, fetch_active_strategies, fetch_prices
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


def run_strategy(strategy: dict, prices: pd.Series, as_of: date) -> dict | None:
    strategy_type = strategy["strategy_type"]
    params = strategy["parameters"]

    if strategy_type == "ewmac":
        fast = params["fast"]
        slow = params["slow"]
        rule_name = f"ewmac_{fast}_{slow}"

        raw = calc_ewmac_raw(prices, fast, slow)
        scalar = calc_forecast_scalar(raw)
        scaled = scale_and_cap(raw, scalar)

        as_of_mask = scaled.index.date == as_of
        if not as_of_mask.any():
            return None

        return {
            "rule_name":    rule_name,
            "raw_value":    float(raw[as_of_mask].iloc[-1]),
            "scaled_value": float(scaled[as_of_mask].iloc[-1]),
        }

    else:
        logger.warning(f"Unknown strategy_type: {strategy_type}")
        return None


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


def run_ewmac_forecasts(tracker: TaskStatusTracker, as_of: date = None):
    if as_of is None:
        as_of = date.today()

    logger.info(f"Generating forecasts as of {as_of}")

    instruments = fetch_active_instruments()
    strategies = fetch_active_strategies()

    if not instruments:
        logger.warning("No active instruments found")
        tracker.update_status_message("No active instruments found")
        return

    if not strategies:
        logger.warning("No active strategies found")
        tracker.update_status_message("No active strategies found")
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

        for strategy in strategies:
            try:
                result = run_strategy(strategy, prices, as_of)
                if result is None:
                    logger.warning(f"No result for {symbol} {strategy['strategy_type']} on {as_of}")
                    continue

                rows.append({
                    "symbol":       symbol,
                    "rule_name":    result["rule_name"],
                    "date":         as_of,
                    "raw_value":    result["raw_value"],
                    "scaled_value": result["scaled_value"],
                })

                logger.info(
                    f"  {result['rule_name']}: "
                    f"raw={result['raw_value']:.4f} "
                    f"scaled={result['scaled_value']:.2f}"
                )

            except Exception as e:
                logger.error(f"Failed {strategy['strategy_type']} for {symbol}: {e}")
                continue

        tracker.update_progress((i + 1) / num_instruments)

    if rows:
        upsert_forecasts(rows)
        logger.info(f"Wrote {len(rows)} forecast rows for {as_of}")
        tracker.update_status_message(f"Wrote {len(rows)} forecast rows for {as_of}")
    else:
        logger.warning("No forecast rows generated")
        tracker.update_status_message("No forecast rows generated")