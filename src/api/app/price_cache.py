import json
import logging
import os
import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.environ["REDIS_URL"]
redis_client = redis.Redis.from_url(REDIS_URL)


def get_current_prices() -> dict:
    """
    Get all current prices from Redis cache.

    Returns:
        Dictionary mapping ticker -> price data, or empty dict if cache miss
    """
    try:
        cached = redis_client.get("current_prices")
        if cached:
            return json.loads(cached)  # type: ignore
        logger.warning("Current prices cache miss")
        return {}
    except Exception as e:
        logger.error(f"Error reading price cache: {e}")
        return {}


def get_current_price(ticker: str) -> float | None:
    """
    Get current price for a specific ticker.

    Returns:
        Current price as float, or None if not available
    """
    prices = get_current_prices()
    return prices.get(ticker, {})
