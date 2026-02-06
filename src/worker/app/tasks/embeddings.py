import logging
import os
from datetime import datetime, timezone

import mlflow
from sqlalchemy import text

from app.celery_app import app
from app.database.db import get_connection
from app.utils import (
    ETLStatusTracker,
    SingleInstanceTask,
    track_records_processed,
    track_task_metrics,
)

logger = logging.getLogger(__name__)

# Model configuration
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "10000"))
EMBEDDING_NUM_BATCHES = int(os.getenv("EMBEDDING_NUM_BATCHES", "10"))
COLUMN_NAME = "all_minilm_l6_v2_embedding"
TIMESTAMP_COLUMN = "all_minilm_l6_v2_generated_at"


def load_model():
    """
    Load the embedding model. This is done lazily to avoid having
    all containers load it into memory. Since the task is run infrequently
    and not a part of the real-time pipeline, this tradeoff makes sense.
    The latency is permitted.
    """
    from sentence_transformers import SentenceTransformer

    logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)
    logger.info(f"Model loaded: {EMBEDDING_MODEL}")
    return model


@app.task(base=SingleInstanceTask, bind=True, queue="gpu")
@track_task_metrics
def generate_historical_embeddings(self):
    """
    Generate embeddings for historical Reddit comments.
    Processes in batches and logs to MLflow.
    """
    tracker = ETLStatusTracker(
        task_id=self.request.id,
        component_name="Historical Comment Embeddings",
        task_description=f"Generating embeddings with {EMBEDDING_MODEL}",
    )
    tracker.start_task()
    embedding_model = load_model()

    mlflow_run_name = (
        f"embeddings_{EMBEDDING_MODEL}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    try:
        with mlflow.start_run(run_name=mlflow_run_name):
            # Log model metadata
            mlflow.log_param("model_name", EMBEDDING_MODEL)
            mlflow.log_param("embedding_dimension", EMBEDDING_DIM)
            mlflow.log_param("batch_size", EMBEDDING_BATCH_SIZE)
            mlflow.log_param("num_batches", EMBEDDING_NUM_BATCHES)
            mlflow.log_param("column_name", COLUMN_NAME)
            mlflow.log_param("task_id", self.request.id)

            total_embedded = 0
            for _ in range(EMBEDDING_NUM_BATCHES):
                # Get batch of comments without embeddings in this column
                sql = f"""
                    SELECT comment_id, body
                    FROM historical_reddit_comments
                    WHERE {COLUMN_NAME} IS NULL
                    ORDER BY created_utc DESC
                    LIMIT {EMBEDDING_BATCH_SIZE};
                """
                with get_connection() as conn:
                    result = conn.execute(text(sql))
                    rows = result.fetchall()

                if not rows:
                    logger.info("No more comments to embed")
                    break

                # Extract IDs and bodies
                ids = [row.comment_id for row in rows]
                bodies = [row.body for row in rows]

                # Generate embeddings
                logger.info(f"Generating embeddings for {len(bodies)} comments")
                embeddings = embedding_model.encode(
                    bodies,
                    show_progress_bar=False,
                    batch_size=32,
                    normalize_embeddings=True,
                )

                # Update database
                generated_at = datetime.now(timezone.utc)
                with get_connection() as conn:
                    for comment_id, embedding in zip(ids, embeddings):
                        update_sql = f"""
                            UPDATE historical_reddit_comments
                            SET
                                {COLUMN_NAME} = :embedding,
                                {TIMESTAMP_COLUMN} = :generated_at
                            WHERE comment_id = :comment_id
                        """
                        conn.execute(
                            text(update_sql),
                            {
                                "embedding": embedding.tolist(),
                                "generated_at": generated_at,
                                "comment_id": comment_id,
                            },
                        )
                    conn.commit()

                total_embedded += len(ids)

                # Track progress
                tracker.update_progress(
                    min(total_embedded / 1_000_000, 0.95), persist=True
                )
                tracker.update_status_message(f"Embedded {total_embedded:,} comments")

                track_records_processed(
                    task_name="generate_historical_embeddings",
                    count=len(ids),
                    record_type="reddit_comment_embedding",
                )

                logger.info(f"Total embedded so far: {total_embedded:,}")

            # Log final metrics to MLflow
            mlflow.log_metric("total_comments_embedded", total_embedded)
            mlflow.log_metric(
                "batches_processed", total_embedded / EMBEDDING_BATCH_SIZE
            )

            logger.info(f"Embedding generation complete: {total_embedded:,} comments")
            tracker.update_status_message(
                f"Complete: {total_embedded:,} comments embedded"
            )
            tracker.complete_task()

            return {
                "total_embedded": total_embedded,
                "model": EMBEDDING_MODEL,
                "column": COLUMN_NAME,
                "mlflow_run_id": mlflow.active_run().info.run_id,
            }

    except Exception as e:
        logger.exception("Error generating embeddings")
        tracker.fail_task(str(e))

        if mlflow.active_run():
            mlflow.log_param("status", "failed")
            mlflow.log_param("error", str(e))

        raise
