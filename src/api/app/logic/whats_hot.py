import logging
import pandas as pd
from sqlalchemy import text
import db
import models
import yfinance as yf

import price_cache

logger = logging.getLogger(__name__)


async def get_ticker_mentions():
    """Gets the ticker mention data for daily discussion threads."""
    sql = """
        WITH daily_thread AS (
            SELECT DISTINCT post_id, created_utc
            FROM reddit_posts
            WHERE is_daily_thread IS TRUE
            ORDER BY created_utc DESC
            OFFSET {offset} LIMIT 1
        ),
        latest_comment_ids AS (
            SELECT DISTINCT ON (comment_id) 
                id,
                comment_id,
                post_id
            FROM reddit_comments
            WHERE post_id = (SELECT post_id FROM daily_thread)
            ORDER BY comment_id, scraped_at DESC
        )
        SELECT ticker, count(ticker) as ticker_mentions
        FROM latest_comment_ids lci
        JOIN reddit_comments rc ON rc.id = lci.id
        GROUP BY ticker
        ORDER BY ticker_mentions DESC
        LIMIT 25;
    """
    current = sql.format(offset=0)
    previous = sql.format(offset=1)
    before_previous = sql.format(offset=2)
    async with db.AsyncSessionLocal() as session:
        current_result = await session.execute(text(current))
        current_rows = current_result.fetchall()
        current_cols = current_result.keys()

        previous_result = await session.execute(text(previous))
        previous_rows = previous_result.fetchall()
        previous_cols = previous_result.keys()

        before_result = await session.execute(text(before_previous))
        before_rows = before_result.fetchall()
        before_cols = before_result.keys()

    # Create df with mention data
    current = pd.DataFrame(current_rows, columns=current_cols)  # type: ignore
    previous = pd.DataFrame(previous_rows, columns=previous_cols)  # type: ignore
    before = pd.DataFrame(before_rows, columns=before_cols)  # type: ignore

    logger.info(f"got {len(current.index)} tickers for hot dashboard")

    mentions_df = current.merge(right=previous, how="outer", on=["ticker"])
    mentions_df = mentions_df.merge(right=before, how="outer", on=["ticker"])

    cols = {
        "ticker_mentions_x": "ticker_mentions_1",
        "ticker_mentions_y": "ticker_mentions_2",
        "ticker_mentions": "ticker_mentions_3",
    }
    mentions_df = mentions_df.rename(columns=cols)

    mentions_df["mention_pct_change"] = (
        mentions_df["ticker_mentions_1"] / mentions_df["ticker_mentions_3"] - 1
    ) * 100

    # join current price data
    price_data = price_cache.get_current_prices()  # TODO fall back to recent close
    cols = ["ticker", "price", "day_change", "year_change"]
    price_df = pd.DataFrame(price_data, columns=cols)
    ticker_mentions = mentions_df.merge(right=price_df, how="left", on="ticker")
    ticker_mentions = ticker_mentions.fillna(value=0, axis=1)

    return ticker_mentions


async def get_top_comments():
    """Get the top comments for the current daily discussion thread."""
    sql = """
        WITH daily_thread AS (
            SELECT post_id
            FROM reddit_posts
            WHERE is_daily_thread IS TRUE
            ORDER BY created_utc DESC
            LIMIT 1
        ),
        latest_comment_ids AS (
            SELECT DISTINCT ON (comment_id) 
                id,
                comment_id,
                post_id
            FROM reddit_comments
            WHERE post_id = (SELECT post_id FROM daily_thread)
            ORDER BY comment_id, scraped_at DESC
        )
        SELECT rc.comment_id, rc.body, rc.score
        FROM latest_comment_ids lci
        JOIN reddit_comments rc ON rc.id = lci.id
        ORDER BY rc.score DESC
        LIMIT 25;
    """
    async with db.AsyncSessionLocal() as session:
        result = await session.execute(text(sql))
        rows = result.fetchall()

    df = pd.DataFrame(rows, columns=result.keys())  # type: ignore

    return df


if __name__ == "__main__":
    import asyncio

    asyncio.run(get_ticker_mentions())
