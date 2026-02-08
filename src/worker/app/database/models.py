from sqlalchemy import (
    Table,
    Text,
    Column,
    Date,
    Integer,
    Float,
    String,
    MetaData,
    TIMESTAMP,
    BigInteger,
    Numeric,
    Boolean,
    JSON,
)
from pgvector.sqlalchemy import Vector

# Define schema
metadata = MetaData()

reddit_posts = Table(
    "reddit_posts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("post_id", String(20)),
    Column("subreddit", String(100)),
    Column("score", Integer),
    Column("title", Text),
    Column("body", Text),
    Column("ticker", String(4)),
    Column("author", String(20)),
    Column("num_comments", Integer),
    Column("is_daily_thread", Boolean),
    Column("created_utc", TIMESTAMP(timezone=True)),
    Column("scraped_at", TIMESTAMP(timezone=True)),
)

reddit_comments = Table(
    "reddit_comments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comment_id", String(20)),
    Column("parent_id", String(20)),
    Column("post_id", String(20)),
    Column("subreddit", String(100)),
    Column("body", Text),
    Column("score", Integer),
    Column("ticker", String(4)),
    Column("controversiality", Integer),
    Column("author", String(100)),
    Column("depth", Integer),
    Column("created_utc", TIMESTAMP(timezone=True)),
    Column("scraped_at", TIMESTAMP(timezone=True)),
    Column("embedding", Vector(384)),
    Column("embedding_generated_at", TIMESTAMP(timezone=True)),
)

reddit_comment_sentiment_predictions = Table(
    "reddit_comment_sentiment_predictions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("reddit_comments_id", Integer),
    Column("label", String(20)),
    Column("confidence", Float),
    Column("model_version", Text(50)),
    Column("predicted_at", TIMESTAMP(timezone=True)),
)


stock_prices = Table(
    "stock_prices",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("ticker", String(10), nullable=False),
    Column("date", Date, nullable=False),
    Column("open", Numeric(10, 2)),
    Column("high", Numeric(10, 2)),
    Column("low", Numeric(10, 2)),
    Column("close", Numeric(10, 2)),
    Column("volume", BigInteger),
    # SMA indicators
    Column("sma_9", Numeric(10, 2)),
    Column("sma_10", Numeric(10, 2)),
    Column("sma_12", Numeric(10, 2)),
    Column("sma_26", Numeric(10, 2)),
    Column("sma_50", Numeric(10, 2)),
    Column("sma_100", Numeric(10, 2)),
    Column("sma_200", Numeric(10, 2)),
    # EMA indicators
    Column("ema_9", Numeric(10, 2)),
    Column("ema_10", Numeric(10, 2)),
    Column("ema_12", Numeric(10, 2)),
    Column("ema_26", Numeric(10, 2)),
    Column("ema_50", Numeric(10, 2)),
    Column("ema_100", Numeric(10, 2)),
    Column("ema_200", Numeric(10, 2)),
    # Other indicators
    Column("rsi_14", Numeric(10, 2)),
    Column("macd_12_26_9", Numeric(10, 2)),
    Column("macdh_12_26_9", Numeric(10, 2)),
    Column("macds_12_26_9", Numeric(10, 2)),
    # Bollinger Bands
    Column("bbl_20", Numeric(10, 2)),
    Column("bbm_20", Numeric(10, 2)),
    Column("bbu_20", Numeric(10, 2)),
    Column("bbb_20", Numeric(10, 2)),
    Column("bbp_20", Numeric(10, 2)),
    Column("created_at", TIMESTAMP(timezone=True)),
)

cboe_daily_stats = Table(
    "cboe_daily_stats",
    metadata,
    Column("date", Date, primary_key=True),
    Column("total_put_call_ratio", Float),
    Column("equity_put_call_ratio", Float),
    Column("index_put_call_ratio", Float),
    Column("vix_put_call_ratio", Float),
    Column("total_volume", Integer),
    Column("total_oi", Integer),
    Column("scraped_at", TIMESTAMP(timezone=True)),
)

fred_macro_data = Table(
    "fred_macro_data",
    metadata,
    Column("date", Date, primary_key=True, nullable=False),
    Column("treasury_ten_year", Numeric(6, 4)),
    Column("fed_funds_rate", Numeric(6, 4)),
    Column("dollar_index", Numeric(8, 4)),
    Column("unemployment_rate", Numeric(5, 2)),
    Column("scraped_at", TIMESTAMP(timezone=True)),
)

etl_task_status = Table(
    "etl_task_status",
    metadata,
    Column("id", Integer, primary_key=True, nullable=False),
    Column("task_id", String(50)),
    Column("component_name", String(50)),
    Column("task_description", String(100)),
    Column("status", String(20)),
    Column("status_message", Text),
    Column("progress", Float),
    Column("start_time", TIMESTAMP(timezone=True)),
    Column("end_time", TIMESTAMP(timezone=True)),
)

tickers = Table(
    "tickers",
    metadata,
    Column("id", Integer, primary_key=True, nullable=False),
    Column("ticker", String(10)),
    Column("is_tracked", Boolean),
)

historical_reddit_comments = Table(
    "historical_reddit_comments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comment_id", String(20)),
    Column("parent_id", String(20)),
    Column("post_id", String(20)),
    Column("subreddit", String(100)),
    Column("body", Text),
    Column("score", Integer),
    Column("ticker", String(4)),
    Column("controversiality", Integer),
    Column("author", String(100)),
    Column("created_utc", TIMESTAMP(timezone=True)),
    Column("scraped_at", TIMESTAMP(timezone=True)),
    Column("all_minilm_l6_v2_embedding", Vector(384)),
    Column("all_minilm_l6_v2_generated_at", TIMESTAMP(timezone=True)),
)


historical_reddit_posts = Table(
    "historical_reddit_posts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("post_id", String(20)),
    Column("subreddit", String(100)),
    Column("score", Integer),
    Column("title", Text),
    Column("body", Text),
    Column("ticker", String(4)),
    Column("author", String(20)),
    Column("num_comments", Integer),
    Column("is_daily_thread", Boolean),
    Column("created_utc", TIMESTAMP(timezone=True)),
    Column("scraped_at", TIMESTAMP(timezone=True)),
)

historical_reddit_tracking = Table(
    "historical_reddit_tracking",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("file_name", String(200)),  # relative to mount on prod vm
    Column("file_type", String(16)),  # comments, or submissions
    Column("status", String(20)),  # READY, IN_PROGRESS, COMPLETE, FAILED
    Column("start_time", TIMESTAMP(timezone=True)),
    Column("end_time", TIMESTAMP(timezone=True)),
)

reddit_topic_cluster_summaries = Table(
    "reddit_topic_cluster_summaries",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("model", String(100)),
    Column("count", Integer),
    Column("top_words", Text),
    Column("representative_docs", JSON),
    Column("top_tickers", JSON),
    Column("avg_score", Float),
    Column("max_score", Float),
    Column("time_range_start", TIMESTAMP(timezone=True)),
    Column("time_range_end", TIMESTAMP(timezone=True)),
    Column("llm_theme", Text),
    Column("llm_sentiment", Float),
    Column("llm_confidence", Float),
    Column("llm_insight", Text),
)
