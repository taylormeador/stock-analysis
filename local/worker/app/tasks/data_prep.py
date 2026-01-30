"""
Data preparation tasks for ML model training.

This module handles joining historical Reddit sentiment data with stock prices
to create training datasets for prediction models.
"""

import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from app.celery_app import app
from app.database.db import get_connection

logger = logging.getLogger(__name__)

DATA_DIR = Path("/data/training")
DATA_DIR.mkdir(parents=True, exist_ok=True)


@app.task
def prepare_training_data(
    start_date: str,
    end_date: str,
    output_name: str | None = None,
) -> str:
    """
    Prepare training dataset by joining historical sentiment and price data.

    This creates a dataset where each row represents a ticker on a specific date with:
    - Features: sentiment metrics from that day, technical indicators
    - Label: forward 1-day return (for prediction)

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        output_name: Optional custom name for output file

    Returns:
        Path to the generated parquet file
    """
    logger.info(f"Preparing training data from {start_date} to {end_date}")

    # Aggregate sentiment by ticker and date
    query = """
    WITH daily_sentiment AS (
        SELECT 
            c.ticker,
            DATE(c.created_utc) as date,
            COUNT(*) as mention_count,
            AVG(CASE 
                WHEN s.label = 'positive' THEN s.confidence
                WHEN s.label = 'negative' THEN -s.confidence
                ELSE 0 
            END) as sentiment_score,
            AVG(s.confidence) as avg_confidence,
            SUM(CASE WHEN s.label = 'positive' THEN 1 ELSE 0 END) as positive_count,
            SUM(CASE WHEN s.label = 'negative' THEN 1 ELSE 0 END) as negative_count,
            SUM(CASE WHEN s.label = 'neutral' THEN 1 ELSE 0 END) as neutral_count,
            AVG(c.score) as avg_comment_score,
            MAX(c.score) as max_comment_score
        FROM historical_reddit_comments c
        JOIN historical_reddit_comment_sentiment_predictions s 
            ON c.id = s.historical_reddit_comments_id
        WHERE 
            c.ticker IS NOT NULL 
            AND c.created_utc BETWEEN :start_date AND :end_date
        GROUP BY c.ticker, DATE(c.created_utc)
    )
    SELECT 
        p.ticker,
        p.date,
        p.open,
        p.high,
        p.low,
        p.close,
        p.volume,
        p.rsi_14,
        p.sma_50,
        p.sma_200,
        p.ema_12,
        p.ema_26,
        p.macd_12_26_9,
        p.bbu_20,
        p.bbl_20,
        -- Sentiment features (NULL if no comments that day)
        COALESCE(s.mention_count, 0) as mention_count,
        COALESCE(s.sentiment_score, 0) as sentiment_score,
        COALESCE(s.avg_confidence, 0) as avg_confidence,
        COALESCE(s.positive_count, 0) as positive_count,
        COALESCE(s.negative_count, 0) as negative_count,
        COALESCE(s.neutral_count, 0) as neutral_count,
        COALESCE(s.avg_comment_score, 0) as avg_comment_score,
        COALESCE(s.max_comment_score, 0) as max_comment_score,
        -- Label: forward 1-day return
        (LEAD(p.close, 1) OVER (PARTITION BY p.ticker ORDER BY p.date) - p.close) / p.close as forward_1d_return,
        -- Also calculate current day return (could be useful feature)
        (p.close - p.open) / p.open as intraday_return
    FROM stock_prices p
    LEFT JOIN daily_sentiment s 
        ON p.ticker = s.ticker AND p.date = s.date
    WHERE 
        p.date BETWEEN :start_date AND :end_date
        AND p.close IS NOT NULL
    ORDER BY p.ticker, p.date
    """

    with get_connection() as conn:
        logger.info("Executing training data query...")
        df = pd.read_sql(
            text(query),
            conn,
            params={"start_date": start_date, "end_date": end_date},
        )

    # Remove rows with NULL forward return (last day of each ticker)
    initial_rows = len(df)
    df = df.dropna(subset=["forward_1d_return"])
    logger.info(
        f"Removed {initial_rows - len(df)} rows with NULL forward return (last day per ticker)"
    )

    # Generate output filename
    if output_name is None:
        output_name = f"training_data_{start_date}_{end_date}.parquet"

    output_path = DATA_DIR / output_name
    df.to_parquet(output_path, index=False)

    logger.info(f"Training data saved to {output_path}")
    logger.info(f"Dataset shape: {df.shape}")
    logger.info(f"Date range: {df['date'].min()} to {df['date'].max()}")
    logger.info(f"Unique tickers: {df['ticker'].nunique()}")
    logger.info(f"Rows with sentiment data: {(df['mention_count'] > 0).sum()}")

    # Log some basic stats
    logger.info(
        f"Forward return stats - Mean: {df['forward_1d_return'].mean():.4f}, "
        f"Std: {df['forward_1d_return'].std():.4f}"
    )

    return str(output_path)


@app.task
def generate_fake_training_data(
    start_date: str = "2023-01-01",
    end_date: str = "2023-12-31",
    num_tickers: int = 10,
) -> str:
    """
    Generate fake data for testing the training pipeline.

    This populates historical_reddit_comments with synthetic data and creates
    fake sentiment predictions, then prepares a training dataset.

    Args:
        start_date: Start date for fake data
        end_date: End date for fake data
        num_tickers: Number of tickers to generate data for

    Returns:
        Path to generated training data parquet file
    """
    import numpy as np
    from app.logic.tickers import TICKERS

    logger.info(
        f"Generating fake training data from {start_date} to {end_date} for {num_tickers} tickers"
    )

    # Sample some tickers
    sample_tickers = list(TICKERS)[:num_tickers]

    # Generate date range
    dates = pd.date_range(start=start_date, end=end_date, freq="D")

    fake_comments = []
    comment_id = 1

    for ticker in sample_tickers:
        for date in dates:
            # Random number of comments per day (0-50)
            num_comments = np.random.randint(0, 50)

            for _ in range(num_comments):
                fake_comments.append(
                    {
                        "comment_id": f"fake_{comment_id}",
                        "post_id": f"post_{comment_id // 10}",
                        "subreddit": np.random.choice(
                            ["wallstreetbets", "stocks", "investing"]
                        ),
                        "body": f"Fake comment about {ticker}",
                        "score": np.random.randint(1, 100),
                        "ticker": ticker,
                        "controversiality": np.random.randint(0, 2),
                        "author": f"user_{np.random.randint(1, 100)}",
                        "depth": np.random.randint(0, 3),
                        "created_utc": date,
                    }
                )
                comment_id += 1

    logger.info(f"Generated {len(fake_comments)} fake comments")

    # Insert into database
    if fake_comments:
        df_comments = pd.DataFrame(fake_comments)
        with get_connection() as conn:
            # Clear existing fake data first
            conn.execute(
                text(
                    "DELETE FROM historical_reddit_comment_sentiment_predictions WHERE historical_reddit_comments_id IN (SELECT id FROM historical_reddit_comments WHERE comment_id LIKE 'fake_%')"
                )
            )
            conn.execute(
                text(
                    "DELETE FROM historical_reddit_comments WHERE comment_id LIKE 'fake_%'"
                )
            )
            conn.commit()

            # Insert comments
            df_comments.to_sql(
                "historical_reddit_comments",
                conn,
                if_exists="append",
                index=False,
            )
            conn.commit()

            # Get the IDs we just inserted
            result = conn.execute(
                text(
                    "SELECT id FROM historical_reddit_comments WHERE comment_id LIKE 'fake_%'"
                )
            )
            comment_ids = [row[0] for row in result]

            # Generate fake sentiment predictions
            fake_sentiments = []
            for cid in comment_ids:
                label = np.random.choice(
                    ["positive", "negative", "neutral"], p=[0.4, 0.3, 0.3]
                )
                fake_sentiments.append(
                    {
                        "historical_reddit_comments_id": cid,
                        "label": label,
                        "confidence": np.random.uniform(0.5, 0.99),
                        "model_version": "fake_finbert",
                    }
                )

            df_sentiments = pd.DataFrame(fake_sentiments)
            df_sentiments.to_sql(
                "historical_reddit_comment_sentiment_predictions",
                conn,
                if_exists="append",
                index=False,
            )
            conn.commit()

    logger.info("Fake data inserted into database")

    # Now prepare training data from the fake data
    return prepare_training_data(
        start_date, end_date, output_name="fake_training_data.parquet"
    )


if __name__ == "__main__":
    # Test locally
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Generate fake data
    path = generate_fake_training_data()
    print(f"Generated fake training data at: {path}")
