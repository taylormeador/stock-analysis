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

    sql = """
        WITH daily_thread AS (
            SELECT post_id
            FROM reddit_posts
            WHERE is_daily_thread IS TRUE
            ORDER BY created_utc DESC
            LIMIT 1
        )
        SELECT ticker, COUNT(*) as mention_count
        FROM first_reddit_comments
        WHERE
            post_id = (SELECT post_id FROM daily_thread) AND
            ticker IS NOT NULL
        GROUP BY ticker
        ORDER BY mention_count DESC
        LIMIT 25;
    """
    with db.get_connection() as conn:
        df = pd.read_sql(sql, conn)

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
