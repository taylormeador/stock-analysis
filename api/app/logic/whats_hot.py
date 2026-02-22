import logging
import pandas as pd
from sqlalchemy import text

import app.db as db
import app.price_cache as price_cache

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
        SELECT 
            ticker, 
            count(ticker) as ticker_mentions,
            count(ticker)::float / sum(count(ticker)) OVER () as mention_share
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
        "mention_share_x": "mention_share_1",
        "ticker_mentions_y": "ticker_mentions_2",
        "mention_share_y": "mention_share_2",
        "ticker_mentions": "ticker_mentions_3",
        "mention_share": "mention_share_3",
    }
    mentions_df = mentions_df.rename(columns=cols)

    mentions_df["mention_pct_change"] = (
        mentions_df["ticker_mentions_1"] / mentions_df["ticker_mentions_3"] - 1
    ) * 100
    mentions_df["mention_share_pct_change"] = (
        mentions_df["mention_share_1"] / mentions_df["mention_share_3"] - 1
    ) * 100

    # join current price data
    price_data = price_cache.get_current_prices()  # TODO fall back to recent close
    cols = ["ticker", "price", "day_change", "year_change"]
    price_df = pd.DataFrame.from_dict(price_data, orient="index", columns=cols)
    price_df.ticker = price_df.index
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


async def get_topic_snapshot():
    """Gets the most recent topic snapshot."""
    sql = """
        SELECT
            count,
            top_words,
            representative_docs,
            top_tickers,
            avg_score,
            max_score,
            llm_theme,
            llm_sentiment,
            llm_confidence,
            llm_insight,
            generated_at
        FROM reddit_topic_cluster_summaries
        ORDER BY generated_at DESC
        LIMIT 10;
    """
    async with db.AsyncSessionLocal() as session:
        result = await session.execute(text(sql))
        rows = result.fetchall()

    return pd.DataFrame(rows)


async def get_topic_snapshots():
    # Get the summaries for the most snapshots in the past ?? interval
    sql = """
        SELECT
            count,
            top_words,
            representative_docs,
            top_tickers,
            avg_score,
            max_score,
            llm_theme,
            llm_sentiment,
            llm_confidence,
            llm_insight,
            generated_at
        FROM reddit_topic_cluster_summaries
        WHERE generated_at > NOW() - INTERVAL '1 Week'
        ORDER BY generated_at DESC;
    """
    async with db.AsyncSessionLocal() as session:
        result = await session.execute(text(sql))
        rows = result.fetchall()

    df = pd.DataFrame(rows)
    snapshots = []
    for snapshot in df.generated_at.unique():
        snapshots.append(df[df.generated_at == snapshot])

    return snapshots


async def get_market_data():
    vix_price = price_cache.get_current_price("VIX")
    spy_price = price_cache.get_current_price("SPY")
    qqq_price = price_cache.get_current_price("QQQ")
    iwm_price = price_cache.get_current_price("IWM")

    cboe_sql = """
        SELECT total_put_call_ratio
        FROM cboe_daily_stats
        ORDER BY date DESC
        LIMIT 1;
    """

    treasury_sql = """
        SELECT treasury_ten_year
        FROM fred_macro_data
        WHERE treasury_ten_year != 'NaN'
        ORDER BY date DESC
        LIMIT 1;
    """
    dollar_sql = """
        SELECT dollar_index
        FROM fred_macro_data
        WHERE dollar_index != 'NaN'
        ORDER BY date DESC
        LIMIT 1;
    """
    put_call_ratio, treasury_ten_year, dollar_index = 0, 0, 0
    async with db.AsyncSessionLocal() as session:
        cboe_result = await session.execute(text(cboe_sql))
        data = cboe_result.first()
        if data and data[0]:
            put_call_ratio = float(data[0])

        treasury_result = await session.execute(text(treasury_sql))
        data = treasury_result.first()
        if data and data[0]:
            treasury_ten_year = float(data[0])

        dollar_result = await session.execute(text(dollar_sql))
        data = dollar_result.first()
        if data and data[0]:
            dollar_index = float(data[0])

    return {
        "vix_price": vix_price,
        "spy_price": spy_price,
        "qqq_price": qqq_price,
        "iwm_price": iwm_price,
        "put_call_ratio": put_call_ratio,
        "treasury_ten_year": treasury_ten_year,
        "dollar_index": dollar_index,
    }


if __name__ == "__main__":
    import asyncio

    asyncio.run(get_ticker_mentions())
