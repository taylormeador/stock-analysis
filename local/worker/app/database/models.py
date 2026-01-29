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
    Column("ticker", String(10)),
    Column("date", Date),
    Column("open", Float),
    Column("high", Float),
    Column("low", Float),
    Column("close", Float),
    Column("volume", Integer),
    Column("created_at", TIMESTAMP(timezone=True)),
)
