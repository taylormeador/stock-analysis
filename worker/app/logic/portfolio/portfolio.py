import logging
import uuid
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import text

import app.database.db as db
from app.logic.portfolio.utils import (
    fetch_active_instruments,
    fetch_instruments,
    fetch_current_price,
)
from app.utils import TaskStatusTracker
from app.logic.portfolio import rules

logger = logging.getLogger(__name__)


def fetch_trading_capital() -> float:
    sql = text("""
        SELECT current_balance
        FROM portfolio
        ORDER BY updated_at DESC
        LIMIT 1
    """)
    with db.get_connection() as conn:
        result = conn.execute(sql).scalar()

    if result is None:
        raise RuntimeError("No portfolio balance found in portfolio table")

    return float(result)


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
            run_id                      = EXCLUDED.run_id,
            variations_used             = EXCLUDED.variations_used,
            weights_used                = EXCLUDED.weights_used,
            fdm                         = EXCLUDED.fdm
    """)
    with db.get_connection() as conn:
        conn.execute(sql, rows)
        conn.commit()


def run_portfolio_calculations(
    tracker: TaskStatusTracker,
    as_of: date,
    variations: list[str] | None = None,
    symbols: list[str] | None = None,
    capital: float | None = None,
    vol_target_pct: float = 0.20,
) -> None:
    """
    Run portfolio calculations for a given date.

    Args:
        tracker:        Task status tracker.
        as_of:          Date to calculate for.
        variations:     List of variation names whose forecasts to combine,
                        e.g. ['ewmac_8_32', 'ewmac_16_64', 'ewmac_32_128'].
                        Defaults to all variations in registry.
        symbols:        Optional list of symbols to restrict to.
                        If None, runs all active instruments.
        capital:        Trading capital in dollars. If None, reads from portfolio table.
        vol_target_pct: Desired annualized standard deviation of daily portfolio returns.
    """
    logger.info(f"Running portfolio calculations for {as_of}")

    # Handle default args
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

    if capital is None:
        capital = fetch_trading_capital()

    # Target vol
    annualized_cash_vol_target = capital * vol_target_pct
    daily_cash_vol_target = annualized_cash_vol_target / 16

    # Get the IDM based on asset classes
    asset_classes = [i["asset_class"] for i in instruments]
    idm = rules.calc_idm(asset_classes)

    # Set up portfolio run
    run_id = str(uuid.uuid4())
    num_instruments = len(instruments)
    instrument_weight = 1.0 / num_instruments
    rows = []

    for i, instrument in enumerate(instruments):
        symbol = instrument["symbol"]
        label = instrument["label"]
        multiplier = instrument["multiplier"]

        logger.info(f"Processing {label} ({symbol})")
        tracker.update_status_message(f"Processing {label} ({i + 1}/{num_instruments})")

        try:
            forecasts = fetch_forecasts(symbol, as_of, variations)
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

            # block_value is the dollar value of a 1% move
            # Instrument value volatility is the how many dollars one contract moves in a typical day
            block_value = current_price * 0.01 * multiplier
            ivv = block_value * ewma_vol * 100

            # Only look at variations we actually have forecasts for
            valid_variations = [v for v in variations if v in forecasts.index]
            if not valid_variations:
                logger.warning(f"No matching forecasts for {symbol}, skipping")
                continue

            # Combine forecasts by averaging and then using correlation based multiplier
            weights = rules.calc_variation_weights(valid_variations)
            raw_combined = float(np.dot(weights, forecasts[valid_variations].values))
            fdm = rules.calc_fdm(valid_variations)
            combined_forecast = min(raw_combined * fdm, 20.0)

            # Scale position based on vol
            vol_scalar = daily_cash_vol_target / ivv
            subsystem_position = combined_forecast * vol_scalar / 10
            portfolio_position = subsystem_position * instrument_weight * idm
            desired_position = round(portfolio_position)

            logger.info(f"  Price:             {current_price:.2f}")
            logger.info(f"  EWMA vol:          {ewma_vol:.4f}")
            logger.info(f"  IVV:               {ivv:.2f}")
            logger.info(f"  Combined forecast: {combined_forecast:.2f}")
            logger.info(f"  FDM:               {fdm:.4f}")
            logger.info(f"  Target position:   {desired_position} contracts")

            rows.append(
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
            logger.error(f"Failed to process {symbol}: {e}")
            continue

        tracker.update_progress((i + 1) / num_instruments)

    if rows:
        upsert_calculations(rows)
        logger.info(
            f"Wrote {len(rows)} portfolio calculation rows for {as_of} (run_id={run_id})"
        )
        tracker.update_status_message(f"Wrote {len(rows)} rows for {as_of}")
    else:
        logger.warning("No portfolio calculation rows generated")
        tracker.update_status_message("No rows generated")
