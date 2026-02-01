import logging
import db
import pandas as pd

logger = logging.getLogger(__name__)


def get_ticker_mentions():
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
    with db.get_connection() as conn:
        today = pd.read_sql(todays_mentions, conn)
        yesterday = pd.read_sql(yesterdays_mentions, conn)

    logger.info(f"got {len(today.index)} tickers for hot dashboard")

    df = today.merge(right=yesterday, how="left", on=["ticker"])
    df["pct_change"] = (df["todays_mentions"] / df["previous_mentions"] - 1) * 100

    df = df.fillna(value=0, axis=1)

    return df


def get_top_comments():
    """Get the top comments for the current daily discussion thread."""
    sql = """
        WITH daily_thread AS (
            SELECT post_id
            FROM reddit_posts
            WHERE is_daily_thread IS TRUE
            ORDER BY created_utc DESC
            LIMIT 1
        ),
        top_comments AS (
            SELECT body, score, controversiality
            FROM reddit_comments
            WHERE id IN (
                SELECT id
                FROM last_reddit_comments
                WHERE post_id = (SELECT post_id FROM daily_thread)
            )
            ORDER BY score DESC
            LIMIT 25
        )
        SELECT * FROM top_comments;
    """
    with db.get_connection() as conn:
        top_comments = pd.read_sql(sql, conn)

    logger.info(f"got {len(top_comments)} top comments")

    return top_comments
