from fastapi import APIRouter
import logging
import logic.whats_hot as whats_hot
import logic.etl_status as etl_status
import asyncio
import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/whats-hot")
async def get_whats_hot():
    logger.info("calculating data for hot dashboard")

    top_comments = await whats_hot.get_top_comments()
    ticker_mentions = await whats_hot.get_ticker_mentions()

    logger.info("got whats hot data")

    dfs = {
        "ticker_mentions": ticker_mentions.to_dict("records"),
        "top_comments": top_comments.to_dict("records"),
    }

    return {"data": dfs}


@router.get("/etl-status/")
async def get_etl_status():
    tasks = [
        etl_status.get_etl_task_statuses(),
        etl_status.get_failed_task_count(),
        etl_status.get_task_time_deltas(),
    ]
    results = await asyncio.gather(*tasks)

    data = {
        "etl_task_statuses": results[0].to_dict("records"),
        "failed_task_count": results[1].to_dict("records"),
        "task_time_deltas": results[2].to_dict("records"),
    }

    return {"data": data}


if __name__ == "__main__":
    import asyncio

    asyncio.run(get_etl_status())
