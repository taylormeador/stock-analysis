import logging
from sqlalchemy import text
import pandas as pd
from db import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def get_etl_task_statuses():
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
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(sql))
        data = result.fetchall()

    df = pd.DataFrame(data)
    df["run_time"] = df.end_time - df.start_time

    return df


async def get_failed_task_count():
    """
    Get number of tasks that are either failed or
    haven't ended (but also are not still running)
    i.e. task failed and did not write 'Failed'
    """
    sql = """
        SELECT count(*)
        FROM etl_task_status
        WHERE
            start_time > NOW() - interval '24 Hours' AND
            (status = 'FAILED' OR
                (end_time IS NULL AND status NOT IN ('In Progress', 'Retrying', 'Not Started')));
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(sql))
        data = result.fetchall()

    return pd.DataFrame(data)


async def get_task_time_deltas():
    """Get statistical data about task durations."""
    sql = """
        WITH task_times AS (
            SELECT end_time - start_time AS deltas
            FROM etl_task_status
            WHERE
                end_time IS NOT NULL AND
                start_time > NOW() - INTERVAL '24 Hours'
        )
        SELECT
            AVG(deltas) AS mean,
            MODE() WITHIN GROUP (ORDER BY deltas),
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY deltas) AS p_50,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY deltas) AS p_75,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY deltas) AS p_90,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY deltas) AS p_95,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY deltas) AS p_99,
            MAX(deltas) AS max_delta
        FROM task_times;
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(sql))
        data = result.fetchall()

    return pd.DataFrame(data)
