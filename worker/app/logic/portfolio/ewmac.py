import logging
from datetime import date

import pandas as pd

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
    parts = variation_name.split("_")
    if len(parts) != 3 or parts[0] != "ewmac":
        raise ValueError(f"Cannot parse ewmac variation name: {variation_name!r}")
    return int(parts[1]), int(parts[2])


def run_ewmac_variation(
    variation_name: str, prices: pd.Series, as_of: date
) -> dict | None:
    """
    Compute a single EWMAC forecast for a given variation and price series.
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
