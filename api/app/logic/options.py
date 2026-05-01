import json
import logging
import os

import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.environ["REDIS_URL"]
_rc = redis.Redis.from_url(REDIS_URL)


def get_vol_surface() -> dict:
    try:
        raw = _rc.get("options:vol_surface")
        return json.loads(raw) if raw else {}
    except Exception:
        logger.exception("Error reading options:vol_surface from Redis")
        return {}


def get_anomalies() -> list:
    try:
        raw = _rc.get("options:anomalies")
        return json.loads(raw) if raw else []
    except Exception:
        logger.exception("Error reading options:anomalies from Redis")
        return []


def get_pipeline_metrics() -> dict:
    try:
        raw = _rc.get("options:pipeline_metrics")
        return json.loads(raw) if raw else {}
    except Exception:
        logger.exception("Error reading options:pipeline_metrics from Redis")
        return {}
