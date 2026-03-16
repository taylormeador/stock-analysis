import logging
from datetime import date

import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

import app.database.db as db
from app.utils import TaskStatusTracker

logger = logging.getLogger(__name__)

INSTRUMENTS = {
    "ES=F":  {"multiplier": 0.5, "label": "/MES"},
    "GC=F":  {"multiplier": 1.0, "label": "/MGC"},
    "CL=F":  {"multiplier": 100, "label": "/MCL"},
    "MBT=F": {"multiplier": 0.1, "label": "/MBT"},
}

EWMAC_PAIRS = [
    (8, 32),
    (32, 128),
]

LOOKBACK_DAYS = 250
FORECAST_CAP = 20.0


def fetch_prices(symbol: str) -> pd.Series:
    sql = text("""
        SELECT date, close
        FROM futures_prices
        WHERE symbol = :symbol
          AND date >= CURRENT_DATE - :lookback * INTERVAL '1 day'
        ORDER BY date ASC
    """)
    with db.get_connection() as conn:
        df = pd.read_sql(sql, conn, params={"symbol": symbol, "lookback": LOOKBACK_DAYS})
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["close"].astype(float)


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


def upsert_forecasts(rows: list[dict]) -> None:
    with db.get_connection() as conn:
        for row in rows:
            sql = text("""
                INSERT INTO forecasts (symbol, rule_name, date, raw_value, scaled_value)
                VALUES (:symbol, :rule_name, :date, :raw_value, :scaled_value)
                ON CONFLICT (symbol, rule_name, date) DO UPDATE SET
                    raw_value    = EXCLUDED.raw_value,
                    scaled_value = EXCLUDED.scaled_value
            """)
            conn.execute(sql, row)
        conn.commit()


def run_ewmac_forecasts(tracker: TaskStatusTracker):
    today = date.today()
    rows = []
    num_instruments = len(INSTRUMENTS)

    for i, (symbol, config) in enumerate(INSTRUMENTS.items()):
        logger.info(f"Generating forecasts for {config['label']} ({symbol})")
        tracker.update_status_message(f"Processing {config['label']} ({i + 1}/{num_instruments})")

        try:
            prices = fetch_prices(symbol)
        except Exception as e:
            logger.error(f"Failed to fetch prices for {symbol}: {e}")
            continue

        if len(prices) < 130:
            logger.warning(f"Insufficient price history for {symbol}, skipping")
            continue

        for fast, slow in EWMAC_PAIRS:
            rule_name = f"ewmac_{fast}_{slow}"
            try:
                raw = calc_ewmac_raw(prices, fast, slow)
                scalar = calc_forecast_scalar(raw)
                scaled = scale_and_cap(raw, scalar)

                today_mask = scaled.index.date == today
                if not today_mask.any():
                    logger.warning(f"No data for {today} on {symbol} {rule_name}")
                    continue

                raw_today = float(raw[today_mask].iloc[-1])
                scaled_today = float(scaled[today_mask].iloc[-1])

                rows.append({
                    "symbol":       symbol,
                    "rule_name":    rule_name,
                    "date":         today,
                    "raw_value":    raw_today,
                    "scaled_value": scaled_today,
                })

                logger.info(f"  {rule_name}: raw={raw_today:.4f} scalar={scalar:.1f} scaled={scaled_today:.2f}")

            except Exception as e:
                logger.error(f"Failed {rule_name} for {symbol}: {e}")
                continue

        tracker.update_progress((i + 1) / num_instruments)

    if rows:
        upsert_forecasts(rows)
        logger.info(f"Wrote {len(rows)} forecast rows")
        tracker.update_status_message(f"Wrote {len(rows)} forecast rows")
    else:
        logger.warning("No forecast rows generated")
        tracker.update_status_message("No forecast rows generated")