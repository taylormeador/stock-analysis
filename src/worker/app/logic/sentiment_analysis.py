"""
Sentiment analysis logic for Reddit comments.

This module provides sentiment scoring using VADER and FinBERT models.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Dict, List

import torch
from sqlalchemy import text
from torch.nn.functional import softmax
from transformers import AutoModelForSequenceClassification, AutoTokenizer

import app.database.db as db
from app.utils import TaskStatusTracker

logger = logging.getLogger(__name__)

SENTIMENT_NUM_BATCHES = int(os.getenv("SENTIMENT_NUM_BATCHES", 0))
SENTIMENT_BATCH_SIZE = int(os.getenv("SENTIMENT_BATCH_SIZE", 0))


def load_vader_analyzer():
    """
    Load VADER sentiment analyzer.
    Lazy loading to avoid loading in containers that don't need it.
    """
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    logger.info("Loading VADER sentiment analyzer")
    analyzer = SentimentIntensityAnalyzer()
    logger.info("VADER analyzer loaded")
    return analyzer


def load_finbert_model():
    """
    Load FinBERT model and tokenizer.
    Lazy loading to avoid loading in containers that don't need it.
    """

    logger.info("Loading FinBERT model")
    model_name = "ProsusAI/finbert"

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)

    # Move to GPU if available
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    model.eval()

    logger.info(f"FinBERT model loaded on {device}")
    return tokenizer, model, device


def run_vader_analysis(tracker: TaskStatusTracker):

    analyzer = load_vader_analyzer()
    total_processed = 0

    for batch_num in range(SENTIMENT_NUM_BATCHES):
        # Get batch of comments without VADER sentiment
        sql = """
            SELECT hrc.comment_id, hrc.body
            FROM historical_reddit_comments hrc
            LEFT JOIN comment_sentiment cs ON hrc.comment_id = cs.comment_id
            WHERE cs.vader_compound IS NULL
            ORDER BY hrc.created_utc DESC
            LIMIT :batch_size;
        """
        with db.get_connection() as conn:
            result = conn.execute(text(sql), {"batch_size": SENTIMENT_BATCH_SIZE})
            rows = result.fetchall()

        if not rows:
            logger.info("No more comments to process with VADER")
            break

        # Extract comment_ids and bodies
        comment_ids = [row.comment_id for row in rows]
        bodies = [row.body for row in rows]

        # Generate VADER sentiment
        logger.info(f"Generating VADER sentiment for {len(bodies)} comments")
        tracker.update_status_message(
            f"Batch {batch_num + 1}/{SENTIMENT_NUM_BATCHES}: Processing {len(bodies)} comments"
        )

        sentiment_scores = []
        for body in bodies:
            scores = analyzer.polarity_scores(body)
            sentiment_scores.append(
                {
                    "compound": scores["compound"],
                    "pos": scores["pos"],
                    "neg": scores["neg"],
                    "neu": scores["neu"],
                }
            )

        # Update database
        processed_at = datetime.now(timezone.utc)
        with db.get_connection() as conn:
            for comment_id, scores in zip(comment_ids, sentiment_scores):
                upsert_sql = """
                    INSERT INTO comment_sentiment (
                        comment_id,
                        vader_compound,
                        vader_pos,
                        vader_neg,
                        vader_neu,
                        processed_at
                    ) VALUES (
                        :comment_id,
                        :compound,
                        :pos,
                        :neg,
                        :neu,
                        :processed_at
                    )
                    ON CONFLICT (comment_id) DO UPDATE SET
                        vader_compound = EXCLUDED.vader_compound,
                        vader_pos = EXCLUDED.vader_pos,
                        vader_neg = EXCLUDED.vader_neg,
                        vader_neu = EXCLUDED.vader_neu,
                        processed_at = EXCLUDED.processed_at;
                """
                conn.execute(
                    text(upsert_sql),
                    {
                        "comment_id": comment_id,
                        "compound": scores["compound"],
                        "pos": scores["pos"],
                        "neg": scores["neg"],
                        "neu": scores["neu"],
                        "processed_at": processed_at,
                    },
                )
            conn.commit()

        total_processed += len(comment_ids)

        # Track progress
        tracker.update_progress(
            min(
                total_processed / (SENTIMENT_NUM_BATCHES * SENTIMENT_BATCH_SIZE),
                0.95,
            ),
            persist=True,
        )
        tracker.update_status_message(
            f"Processed {total_processed:,} comments with VADER"
        )

        logger.info(f"Total processed so far: {total_processed:,}")

    logger.info(f"VADER sentiment generation complete: {total_processed:,} comments")
    tracker.update_status_message(f"Complete: {total_processed:,} comments processed")


def run_finbert_analysis(tracker: TaskStatusTracker):
    tokenizer, model, device = load_finbert_model()
    total_processed = 0

    for batch_num in range(SENTIMENT_NUM_BATCHES):
        # Get batch of comments without FinBERT sentiment
        sql = """
            SELECT hrc.comment_id, hrc.body
            FROM historical_reddit_comments hrc
            LEFT JOIN comment_sentiment cs ON hrc.comment_id = cs.comment_id
            WHERE cs.finbert_label IS NULL
            ORDER BY hrc.created_utc DESC
            LIMIT :batch_size;
        """
        with db.get_connection() as conn:
            result = conn.execute(text(sql), {"batch_size": SENTIMENT_BATCH_SIZE})
            rows = result.fetchall()

        if not rows:
            logger.info("No more comments to process with FinBERT")
            break

        # Extract comment_ids and bodies
        comment_ids = [row.comment_id for row in rows]
        bodies = [row.body for row in rows]

        # Generate FinBERT sentiment
        logger.info(f"Generating FinBERT sentiment for {len(bodies)} comments")
        tracker.update_status_message(
            f"Batch {batch_num + 1}/{SENTIMENT_NUM_BATCHES}: Processing {len(bodies)} comments"
        )

        sentiment_results = analyze_finbert_sentiment(tokenizer, model, device, bodies)

        # Update database
        processed_at = datetime.now(timezone.utc)
        with db.get_connection() as conn:
            for comment_id, result in zip(comment_ids, sentiment_results):
                upsert_sql = """
                    INSERT INTO comment_sentiment (
                        comment_id,
                        finbert_label,
                        finbert_score,
                        processed_at
                    ) VALUES (
                        :comment_id,
                        :label,
                        :score,
                        :processed_at
                    )
                    ON CONFLICT (comment_id) DO UPDATE SET
                        finbert_label = EXCLUDED.finbert_label,
                        finbert_score = EXCLUDED.finbert_score,
                        processed_at = EXCLUDED.processed_at;
                """
                conn.execute(
                    text(upsert_sql),
                    {
                        "comment_id": comment_id,
                        "label": result["label"],
                        "score": result["score"],
                        "processed_at": processed_at,
                    },
                )
            conn.commit()

        total_processed += len(comment_ids)

        # Track progress
        tracker.update_progress(
            min(
                total_processed / (SENTIMENT_NUM_BATCHES * SENTIMENT_BATCH_SIZE),
                0.95,
            ),
            persist=True,
        )
        tracker.update_status_message(
            f"Processed {total_processed:,} comments with FinBERT"
        )

        logger.info(f"Total processed so far: {total_processed:,}")

    logger.info(f"FinBERT sentiment generation complete: {total_processed:,} comments")
    tracker.update_status_message(f"Complete: {total_processed:,} comments processed")


def analyze_finbert_sentiment(
    tokenizer, model, device, bodies: List[str]
) -> List[Dict]:
    """
    Analyze sentiment using FinBERT.

    Returns:
        List of dictionaries with keys: label (positive/negative/neutral), score (confidence)
    """

    results = []
    batch_size = 32

    for i in range(0, len(bodies), batch_size):
        batch = bodies[i : i + batch_size]

        # Tokenize + predict
        inputs = tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(device)

        with torch.no_grad():
            outputs = model(**inputs)
            predictions = softmax(outputs.logits, dim=-1)

        predictions = predictions.cpu().numpy()

        # FinBERT outputs: [positive, negative, neutral]
        for pred in predictions:
            label_idx = pred.argmax()
            score = float(pred[label_idx])

            labels = ["positive", "negative", "neutral"]
            label = labels[label_idx]

            results.append(
                {
                    "label": label,
                    "score": score,
                }
            )

    return results
