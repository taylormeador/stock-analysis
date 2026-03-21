import logging
from datetime import date

import pandas as pd
from sqlalchemy import text

import app.database.db as db
from app.logic.portfolio.utils import fetch_trading_instruments, fetch_prices
from app.utils import TaskStatusTracker

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 120
VOLATILITY_TARGET_PCT = 0.20
IDM = 1.7  # TODO derive from correlation table per Carver's lookup


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


def fetch_forecasts(symbol: str, as_of: date) -> pd.Series:
    sql = text("""
        SELECT rule_name, scaled_value
        FROM forecasts
        WHERE symbol = :symbol
          AND date = :as_of
    """)
    with db.get_connection() as conn:
        df = pd.read_sql(sql, conn, params={"symbol": symbol, "as_of": as_of})
    if df.empty:
        return pd.Series(dtype=float)
    return df.set_index("rule_name")["scaled_value"]


def calc_ewma_vol(prices: pd.Series) -> float:
    returns = prices.pct_change()
    variance = returns.pow(2).ewm(span=36, adjust=False).mean()
    return float(variance.pow(0.5).iloc[-1])


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
            portfolio_position, desired_position
        ) VALUES (
            :symbol, :date,
            :trading_capital, :volatility_target_pct,
            :current_price,
            :ewma_vol, :block_value, :ivv,
            :annualized_cash_vol_target, :daily_cash_vol_target, :vol_scalar,
            :combined_forecast,
            :subsystem_position, :instrument_weight, :idm,
            :portfolio_position, :desired_position
        )
        ON CONFLICT (symbol, date) DO UPDATE SET
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
            desired_position            = EXCLUDED.desired_position
    """)
    with db.get_connection() as conn:
        conn.execute(sql, rows)
        conn.commit()


def run_portfolio_calculations(tracker: TaskStatusTracker, as_of: date = None):
    if as_of is None:
        as_of = date.today()

    logger.info(f"Running portfolio calculations for {as_of}")

    trading_capital = fetch_trading_capital()
    annualized_cash_vol_target = trading_capital * VOLATILITY_TARGET_PCT
    daily_cash_vol_target = annualized_cash_vol_target / 16

    instruments = fetch_trading_instruments()
    if not instruments:
        logger.warning("No instruments found")
        tracker.update_status_message("No instruments found")
        return

    num_instruments = len(instruments)
    instrument_weight = 1 / num_instruments
    rows = []

    for i, instrument in enumerate(instruments):
        symbol = instrument["symbol"]
        label = instrument["label"]
        multiplier = instrument["multiplier"]

        logger.info(f"Processing {label} ({symbol})")
        tracker.update_status_message(f"Processing {label} ({i + 1}/{num_instruments})")

        try:
            prices = fetch_prices(symbol, as_of, LOOKBACK_DAYS)
            if prices.empty:
                logger.warning(f"No price data for {symbol}, skipping")
                continue

            forecasts = fetch_forecasts(symbol, as_of)
            if forecasts.empty:
                logger.warning(f"No forecasts for {symbol} on {as_of}, skipping")
                continue

            current_price = float(prices.iloc[-1])
            ewma_vol = calc_ewma_vol(prices)
            block_value = current_price * 0.01 * multiplier
            ivv = block_value * ewma_vol * 100
            combined_forecast = float(
                forecasts.mean()
            )  # TODO add FDM lookup and multiply
            vol_scalar = daily_cash_vol_target / ivv
            subsystem_position = combined_forecast * vol_scalar / 10
            portfolio_position = subsystem_position * instrument_weight * IDM
            desired_position = round(portfolio_position)

            logger.info(f"  Price:             {current_price:.2f}")
            logger.info(f"  EWMA vol:          {ewma_vol:.4f}")
            logger.info(f"  IVV:               {ivv:.2f}")
            logger.info(f"  Combined forecast: {combined_forecast:.2f}")
            logger.info(f"  Subsystem pos:     {subsystem_position:.2f}")
            logger.info(f"  Target position:   {desired_position} contracts")

            rows.append(
                {
                    "symbol": symbol,
                    "date": as_of,
                    "trading_capital": trading_capital,
                    "volatility_target_pct": VOLATILITY_TARGET_PCT,
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
                    "idm": IDM,
                    "portfolio_position": portfolio_position,
                    "desired_position": desired_position,
                }
            )

        except Exception as e:
            logger.error(f"Failed to process {symbol}: {e}")
            continue

        tracker.update_progress((i + 1) / num_instruments)

    if rows:
        upsert_calculations(rows)
        logger.info(f"Wrote {len(rows)} portfolio calculation rows for {as_of}")
        tracker.update_status_message(f"Wrote {len(rows)} rows for {as_of}")
    else:
        logger.warning("No portfolio calculation rows generated")
        tracker.update_status_message("No rows generated")
