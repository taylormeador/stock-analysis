from fastapi import APIRouter
import logging
import logic
from sqlalchemy import text
import pandas as pd
import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/whats-hot")
async def get_whats_hot():
    logger.info("calculating data for hot dashboard")

    top_comments = await logic.get_top_comments()
    ticker_mentions = await logic.get_ticker_mentions()

    logger.info("got whats hot data")

    dfs = {
        "ticker_mentions": ticker_mentions.to_dict("records"),
        "top_comments": top_comments.to_dict("records"),
    }

    return {"data": dfs}


@router.get("/etl-status/")
async def get_etl_status():
    # TODO implement a table or something that has overall status
    # overall status = operational, degraded, planned downtime, etc
    # active workers, services, etc
    # data freshness?

    sql = """
        SELECT * FROM (
            SELECT DISTINCT ON (task_description)
                component_name,
                task_description,
                status,
                status_message,
                progress,
                start_time,
                end_time
            FROM etl_task_status
            ORDER BY task_description, start_time DESC
        ) AS latest_tasks
        ORDER BY start_time DESC;
    """
    async with db.AsyncSessionLocal() as session:
        result = await session.execute(text(sql))
        data = result.fetchall()

    df = pd.DataFrame(data)
    df["run_time"] = df.end_time - df.start_time

    return {"data": df.to_dict("records")}


@router.get("/etl/status/components")
async def get_etl_components_status():
    sql = """
        SELECT DISTINCT ON (task_description)
            component_name,
            task_description,
            status,
            progress,
            start_time,
            end_time
        FROM etl_task_status
        WHERE start_time > NOW() - INTERVAL '24 HOURS'
        ORDER BY task_description, start_time DESC;
    """
    async with db.AsyncSessionLocal() as session:
        result = await session.execute(text(sql))
        data = result.fetchall()

    df = pd.DataFrame(data)

    return {"data": df.to_dict("records")}


@router.get("/etl/status/data-quality")
async def get_etl_data_quality_status():
    # TODO implement a table or something that counts total reddit comments/posts analyzed
    # unique tickers
    # active ML models

    return {"data": {}}


if __name__ == "__main__":
    import asyncio

    asyncio.run(get_etl_status())
