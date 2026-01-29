import logging
import time

import torch
from sqlalchemy import insert, text
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.celery_app import app
from app.database import models
from app.database.db import get_connection
from app.tasks.utils import SingleInstanceTask

logger = logging.getLogger(__name__)

tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")


@app.task(base=SingleInstanceTask)
def run_sentiment_analysis():
    logger.info("running sentiment analysis for reddit comments")
    with get_connection() as db:

        # Get reddit comments that don't have inferences yet
        sql = """
            SELECT 
                c.id,
                c.body,
                c.comment_id
            FROM first_reddit_comments c
            LEFT JOIN reddit_comment_sentiment_predictions s ON s.reddit_comments_id = c.id
            WHERE
                c.ticker IS NOT NULL AND
                s.id IS NULL
            LIMIT 1000;
        """
        need_inference = db.execute(text(sql)).fetchall()
        logger.info(f"got {len(need_inference)} comments to analyze")

        start = time.perf_counter()
        for row in need_inference:
            comment_body = row[1]
            inputs = tokenizer(
                comment_body, return_tensors="pt", truncation=True, max_length=512
            )
            outputs = model(**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)

            label = ["negative", "neutral", "positive"][predictions.argmax().item()]  # type: ignore
            confidence = predictions.max().item()

            stmt = insert(models.reddit_comment_sentiment_predictions).values(
                reddit_comments_id=row.id,
                label=label,
                confidence=confidence,
                model_version="finbert",
            )
            db.execute(stmt)
            logger.debug(
                f"made sentiment inference for {row.id} - label {label} confidence {confidence}"
            )

    db.commit()
    total_time = time.perf_counter() - start
    logger.info(f"reddit comment inference time: {total_time}")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    run_sentiment_analysis()
