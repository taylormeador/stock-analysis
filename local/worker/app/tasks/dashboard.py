import logging
import pandas as pd

from app.celery_app import app
import app.database.db as db
from app.tasks.utils import SingleInstanceTask, write_to_s3


logger = logging.getLogger(__name__)


@app.task(base=SingleInstanceTask)
def calculate_whats_hot_data():
    """Calculate the data for the `What's Hot?` dashboard and upload the JSON to S3"""
    logger.info("calculating data for hot dashboard")

    today_sql = """
        WITH daily_thread AS (
            SELECT post_id
            FROM reddit_posts
            WHERE is_daily_thread IS TRUE
            ORDER BY created_utc DESC
            LIMIT 1
        ),
        ticker_sentiment AS (
            SELECT 
                ticker,
                COUNT(*) as total_mentions,
                ROUND(100.0 * SUM(CASE WHEN label = 'positive' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_positive,
                ROUND(100.0 * SUM(CASE WHEN label = 'neutral' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_neutral,
                ROUND(100.0 * SUM(CASE WHEN label = 'negative' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_negative,
                -- Aggregate sentiment score (-1 to 1)
                ROUND(
                    (SUM(CASE WHEN label = 'positive' THEN 1 ELSE 0 END) - 
                    SUM(CASE WHEN label = 'negative' THEN 1 ELSE 0 END))::NUMERIC / COUNT(*),
                    3
                ) as sentiment_score
            FROM reddit_comment_sentiment_predictions predictions
            LEFT JOIN reddit_comments ON predictions.reddit_comments_id = reddit_comments.id
            WHERE reddit_comments_id IN (
                SELECT id
                FROM first_reddit_comments
                WHERE post_id = (SELECT post_id FROM daily_thread) 
                AND ticker IS NOT NULL
            )
            GROUP BY ticker
            ORDER BY total_mentions DESC
            LIMIT 25
        )
        SELECT * FROM ticker_sentiment;
    """
    with db.get_connection() as conn:
        df = pd.read_sql(today_sql, conn)

    logger.info(f"got {len(df.index)} tickers for hot dashboard")

    data = {"data": df.to_dict("records")}
    key = "dashboard/whats_hot.json"
    write_to_s3(data, key)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    calculate_whats_hot_data()
