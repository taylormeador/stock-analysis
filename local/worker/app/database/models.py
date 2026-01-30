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
)

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
