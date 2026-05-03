import json
import logging
import os

import redis
from app.db import AsyncSessionLocal
from sqlalchemy import text

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


async def get_benchmark_runs() -> list:
    sql = """
        SELECT run_id, version_tag, warmup_s, duration_s, ticks_processed, metrics, created_at
        FROM benchmark_runs
        ORDER BY created_at DESC
        LIMIT 100
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text(sql))
            rows = result.fetchall()
            return [
                {
                    "run_id": str(r.run_id),
                    "version_tag": r.version_tag,
                    "warmup_s": r.warmup_s,
                    "duration_s": r.duration_s,
                    "ticks_processed": r.ticks_processed,
                    "created_at": r.created_at.isoformat(),
                    **r.metrics,
                }
                for r in rows
            ]
    except Exception:
        logger.exception("Error reading benchmark_runs from DB")
        return []
