import logging

from app.celery_app import app
import app.logic.dashboard as logic
from app.tasks.utils import SingleInstanceTask, write_to_s3


logger = logging.getLogger(__name__)


@app.task(base=SingleInstanceTask)
def calculate_whats_hot_data():
    """Calculate the data for the `What's Hot?` dashboard and upload the JSON to S3"""
    logger.info("calculating data for hot dashboard")

    ticker_mentions = logic.get_ticker_mention_df()

    data = {"data": ticker_mentions.to_dict("records")}
    key = "dashboard/whats_hot.json"
    write_to_s3(data, key)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    calculate_whats_hot_data()
