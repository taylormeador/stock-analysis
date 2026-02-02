import logging
import pandas as pd
from sqlalchemy import text
import db


logger = logging.getLogger(__name__)


async def get_ticker_mentions():
    """Gets the ticker mention data for today's + yesterday's daily discussion thread."""
    todays_mentions = """
        WITH daily_thread AS (
            SELECT post_id
            FROM reddit_posts
            WHERE is_daily_thread IS TRUE
            ORDER BY created_utc DESC
            LIMIT 1
        ),
        ticker_mentions AS (
            SELECT 
                ticker,
                COUNT(*) as todays_mentions
            FROM reddit_comments
            WHERE id IN (
                SELECT id
                FROM first_reddit_comments
                WHERE post_id = (SELECT post_id FROM daily_thread) 
                AND ticker IS NOT NULL
            )
            GROUP BY ticker
            ORDER BY todays_mentions DESC
            LIMIT 25
        )
        SELECT * FROM ticker_mentions;
    """

    yesterdays_mentions = """
        WITH daily_thread AS (
            SELECT distinct post_id, created_utc
            FROM reddit_posts
            WHERE is_daily_thread IS TRUE
            ORDER BY created_utc DESC
            OFFSET 1 LIMIT 1
        ),
        yesterdays_mentions AS (
            SELECT 
                ticker,
                COUNT(*) as previous_mentions
            FROM reddit_comments
            WHERE id IN (
                SELECT id
                FROM first_reddit_comments
                WHERE post_id = (SELECT post_id FROM daily_thread) 
                AND ticker IS NOT NULL
            )
            GROUP BY ticker
            ORDER BY previous_mentions DESC
            LIMIT 25
        )
        SELECT * FROM yesterdays_mentions;
    """
    async with db.AsyncSessionLocal() as session:
        today_result = await session.execute(text(todays_mentions))
        today_rows = today_result.fetchall()
        today_columns = today_result.keys()

        yesterday_result = await session.execute(text(yesterdays_mentions))
        yesterday_rows = yesterday_result.fetchall()
        yesterday_columns = yesterday_result.keys()

    today = pd.DataFrame(today_rows, columns=today_columns)  # type: ignore
    yesterday = pd.DataFrame(yesterday_rows, columns=yesterday_columns)  # type: ignore

    logger.info(f"got {len(today.index)} tickers for hot dashboard")

    df = today.merge(right=yesterday, how="left", on=["ticker"])
    df["pct_change"] = (df["todays_mentions"] / df["previous_mentions"] - 1) * 100
    df = df.fillna(value=0, axis=1)

    return df


async def get_top_comments():
    """Get the top comments for the current daily discussion thread."""
    sql = "SELECT body, score FROM current_top_reddit_comments;"
    async with db.AsyncSessionLocal() as session:
        result = await session.execute(text(sql))
        rows = result.fetchall()

    df = pd.DataFrame(rows, columns=result.keys())  # type: ignore

    return df


if __name__ == "__main__":
    import asyncio

    asyncio.run(get_top_comments())
