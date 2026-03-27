import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import text

import app.database.db as db
from app.logic.portfolio.utils import (
    fetch_active_instruments,
    fetch_instruments,
    fetch_current_price,
)
from app.logic.portfolio.rules import (
    VariationRegistry,
    calc_variation_weights,
    calc_fdm,
    calc_idm,
)
from app.utils import TaskStatusTracker

logger = logging.getLogger(__name__)


def fetch_forecasts(symbol: str, as_of: date, variations: list[str]) -> pd.Series:
    sql = text("""
        SELECT rule_name, scaled_value
        FROM forecasts
        WHERE symbol = :symbol
          AND date = :as_of
          AND rule_name = ANY(:variations)
    """)
    with db.get_connection() as conn:
        df = pd.read_sql(
            sql,
            conn,
            params={"symbol": symbol, "as_of": as_of, "variations": variations},
        )
    if df.empty:
        return pd.Series(dtype=float)
    return df.set_index("rule_name")["scaled_value"]


def fetch_blended_vol(symbol: str, as_of: date) -> float | None:
    sql = text("""
        SELECT blended_vol
        FROM instrument_vol
        WHERE symbol = :symbol
          AND date <= :as_of
        ORDER BY date DESC
        LIMIT 1
    """)
    with db.get_connection() as conn:
        result = conn.execute(sql, {"symbol": symbol, "as_of": as_of}).scalar()
    return float(result) if result is not None else None


def upsert_calculations(rows: list[dict]) -> None:
    sql = text("""
        INSERT INTO portfolio_calculations (
            symbol, date,
            trading_capital, volatility_target_pct,
            current_price,
            ewma_vol, block_value, instrument_value_volatility,
            annualized_cash_vol_target, daily_cash_vol_target, vol_scalar,
            combined_forecast,
            subsystem_position, instrument_weight, idm,
            portfolio_position, desired_position,
            run_id, variations_used, weights_used, fdm
        ) VALUES (
            :symbol, :date,
            :trading_capital, :volatility_target_pct,
            :current_price,
            :ewma_vol, :block_value, :ivv,
            :annualized_cash_vol_target, :daily_cash_vol_target, :vol_scalar,
            :combined_forecast,
            :subsystem_position, :instrument_weight, :idm,
            :portfolio_position, :desired_position,
            :run_id, :variations_used, :weights_used, :fdm
        )
        ON CONFLICT (symbol, date, run_id) DO UPDATE SET
            trading_capital             = EXCLUDED.trading_capital,
            volatility_target_pct       = EXCLUDED.volatility_target_pct,
            current_price               = EXCLUDED.current_price,
            ewma_vol                    = EXCLUDED.ewma_vol,
            block_value                 = EXCLUDED.block_value,
            instrument_value_volatility = EXCLUDED.instrument_value_volatility,
            annualized_cash_vol_target  = EXCLUDED.annualized_cash_vol_target,
            daily_cash_vol_target       = EXCLUDED.daily_cash_vol_target,
            vol_scalar                  = EXCLUDED.vol_scalar,
            combined_forecast           = EXCLUDED.combined_forecast,
            subsystem_position          = EXCLUDED.subsystem_position,
            instrument_weight           = EXCLUDED.instrument_weight,
            idm                         = EXCLUDED.idm,
            portfolio_position          = EXCLUDED.portfolio_position,
            desired_position            = EXCLUDED.desired_position,
            variations_used             = EXCLUDED.variations_used,
            weights_used                = EXCLUDED.weights_used,
            fdm                         = EXCLUDED.fdm
    """)
    with db.get_connection() as conn:
        conn.execute(sql, rows)
        conn.commit()


def run_portfolio_calculations(
    tracker: TaskStatusTracker,
    start_date: date,
    end_date: date,
    run_id: str,
    capital: float,
    variations: list[str] | None = None,
    symbols: list[str] | None = None,
    vol_target_pct: float = 0.20,
) -> None:
    """
    Run portfolio calculations for a date range, writing all rows under
    the same run_id.

    Args:
        tracker:        Task status tracker.
        start_date:     First date to calculate (inclusive).
        end_date:       Last date to calculate (inclusive).
        run_id:         Human-readable label for this batch, e.g. 'full_universe_2026'.
                        All rows across the date range share this run_id.
                        Upserts on (symbol, date, run_id) so re-running safely overwrites.
        capital:        Trading capital in dollars. Always required — callers must
                        supply this explicitly so runs are fully reproducible.
        variations:     Variation names to combine. Defaults to all active in DB.
        symbols:        Symbols to run. Defaults to all active instruments.
        vol_target_pct: Annualized vol target as a fraction.
    """
    with db.get_connection() as conn:
        registry = VariationRegistry.load(conn)

    if variations is not None:
        for name in variations:
            registry.get(name)  # raises ValueError if not found
        variation_names = variations
    else:
        variation_names = registry.names()

    dates = [
        start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)
    ]
    logger.info(
        f"Running portfolio calculations: {start_date} → {end_date} "
        f"({len(dates)} days), run_id='{run_id}', capital={capital}, "
        f"variations={variation_names}"
    )

    if symbols is not None:
        instruments = fetch_instruments(symbols)
    else:
        instruments = fetch_active_instruments()

    if not instruments:
        logger.warning("No instruments found")
        tracker.update_status_message("No instruments found")
        return

    annualized_cash_vol_target = capital * vol_target_pct
    daily_cash_vol_target = annualized_cash_vol_target / 16

    idm = calc_idm(instruments)
    logger.info(f"IDM: {idm:.4f}")

    num_instruments = len(instruments)
    instrument_weight = 1.0 / num_instruments
    total_steps = len(dates) * num_instruments
    step = 0
    all_rows = []

    for as_of in dates:
        logger.info(f"Processing date {as_of}")
        tracker.update_status_message(
            f"Processing {as_of} ({dates.index(as_of) + 1}/{len(dates)})"
        )

        for instrument in instruments:
            symbol = instrument["symbol"]
            label = instrument["label"]
            multiplier = instrument["multiplier"]

            try:
                forecasts = fetch_forecasts(symbol, as_of, variation_names)
                if forecasts.empty:
                    logger.warning(f"No forecasts for {symbol} on {as_of}, skipping")
                    continue

                current_price = fetch_current_price(symbol, as_of)
                if current_price is None:
                    logger.warning(f"No price data for {symbol} on {as_of}, skipping")
                    continue

                ewma_vol = fetch_blended_vol(symbol, as_of)
                if ewma_vol is None:
                    logger.warning(f"No vol data for {symbol} on {as_of}, skipping")
                    continue

                block_value = current_price * 0.01 * multiplier
                ivv = block_value * ewma_vol * 100

                valid_variations = [v for v in variation_names if v in forecasts.index]
                if not valid_variations:
                    logger.warning(
                        f"No matching forecasts for {symbol} on {as_of}, skipping"
                    )
                    continue

                weights = calc_variation_weights(valid_variations, registry)
                raw_combined = float(
                    np.dot(weights, forecasts[valid_variations].values)
                )
                fdm = calc_fdm(valid_variations, registry)
                combined_forecast = min(raw_combined * fdm, 20.0)

                vol_scalar = daily_cash_vol_target / ivv
                subsystem_position = combined_forecast * vol_scalar / 10
                portfolio_position = subsystem_position * instrument_weight * idm
                desired_position = round(portfolio_position)

                logger.info(
                    f"  [{as_of}] {label}: "
                    f"forecast={combined_forecast:.2f} pos={desired_position}"
                )

                all_rows.append(
                    {
                        "symbol": symbol,
                        "date": as_of,
                        "trading_capital": capital,
                        "volatility_target_pct": vol_target_pct,
                        "current_price": current_price,
                        "ewma_vol": ewma_vol,
                        "block_value": block_value,
                        "ivv": ivv,
                        "annualized_cash_vol_target": annualized_cash_vol_target,
                        "daily_cash_vol_target": daily_cash_vol_target,
                        "vol_scalar": vol_scalar,
                        "combined_forecast": combined_forecast,
                        "subsystem_position": subsystem_position,
                        "instrument_weight": instrument_weight,
                        "idm": idm,
                        "portfolio_position": portfolio_position,
                        "desired_position": desired_position,
                        "run_id": run_id,
                        "variations_used": valid_variations,
                        "weights_used": weights.tolist(),
                        "fdm": fdm,
                    }
                )

            except Exception as e:
                logger.error(f"Failed to process {symbol} on {as_of}: {e}")
                continue

            step += 1
            tracker.update_progress(step / total_steps)

    if all_rows:
        upsert_calculations(all_rows)
        logger.info(
            f"Wrote {len(all_rows)} portfolio calculation rows "
            f"for run_id='{run_id}' ({start_date} → {end_date})"
        )
        tracker.update_status_message(
            f"Wrote {len(all_rows)} rows for run_id='{run_id}'"
        )
    else:
        logger.warning("No portfolio calculation rows generated")
        tracker.update_status_message("No rows generated")
