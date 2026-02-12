import asyncio
import logging

from fastapi import APIRouter

import app.logic.etl_status as etl_status
import app.logic.prometheus as prometheus
import app.logic.whats_hot as whats_hot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/home")
async def get_home():
    """Get data for home page."""
    tasks = [
        whats_hot.get_topic_snapshot(),
        whats_hot.get_ticker_mentions(),
        etl_status.get_etl_task_statuses(),
        prometheus.get_celery_stats(),
    ]
    results = await asyncio.gather(*tasks)

    data = {
        "snapshot": results[0].to_dict("records"),
        "ticker_mentions": results[1].to_dict("records"),
        "etl_task_statuses": results[2].to_dict("records"),
        "celery_stats": results[3],
    }

    return {"data": data}


@router.get("/whats-hot")
async def get_whats_hot():
    logger.info("calculating data for hot dashboard")

    tasks = [
        whats_hot.get_ticker_mentions(),
        whats_hot.get_top_comments(),
        whats_hot.get_topic_snapshots(),
        whats_hot.get_market_data(),
    ]
    results = await asyncio.gather(*tasks)

    logger.info("got whats hot data")

    data = {
        "ticker_mentions": results[0].to_dict("records"),
        "top_comments": results[1].to_dict("records"),
        "topic_snapshots": [snapshot.to_dict("records") for snapshot in results[2]],
        "market_data": results[3],
    }

    return {"data": data}


@router.get("/etl-status/")
async def get_etl_status():
    tasks = [
        etl_status.get_etl_task_statuses(),
        etl_status.get_failed_task_count(),
        etl_status.get_task_time_deltas(),
        prometheus.get_tasks_processed_last_24h(),
        prometheus.get_task_failure_rate(),
    ]
    results = await asyncio.gather(*tasks)

    data = {
        "etl_task_statuses": results[0].to_dict("records"),
        "failed_task_count": results[1].to_dict("records"),
        "task_time_deltas": results[2].to_dict("records"),
        "num_tasks_processed": results[3],
        "task_failure_rate": results[4],
    }

    return {"data": data}


@router.get("/backtest")
async def get_backtest():
    """TODO"""
    return {"data": None}


@router.get("/celery-stats")
async def get_celery_stats_endpoint():
    stats = await prometheus.get_celery_stats()
    return {"data": stats}


if __name__ == "__main__":
    import asyncio

    asyncio.run(get_etl_status())
