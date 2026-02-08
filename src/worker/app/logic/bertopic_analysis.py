"""
BERTopic clustering analysis for Reddit comments.

This script extracts embeddings from the database, runs BERTopic clustering,
and generates LLM summaries of discovered themes.

Usage:
    python bertopic_analysis.py --hours 24
"""

import argparse
import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from bertopic import BERTopic
from sqlalchemy import text

# Assuming your worker database connection setup
import sys

sys.path.append("/app")
from app.database.db import get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_embeddings_for_period(
    hours: int = 24, embedding_model: str = "all-MiniLM-L6-v2"
):
    """
    Fetch comment embeddings from the database for the specified time period.

    Args:
        hours: Number of hours to look back from now
        embedding_model: Name of the embedding model (matches column naming convention)

    Returns:
        DataFrame with columns: id, comment_id, body, ticker, score, created_utc, embedding
    """
    logger.info(
        f"Fetching embeddings from last {hours} hours using model {embedding_model}"
    )

    # Calculate time threshold
    threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Query comments with embeddings
    # Adjust the embedding column name based on your naming convention
    embedding_column = (
        f"{embedding_model.replace('/', '_').replace('-', '_')}_embedding"
    )

    query = f"""
    SELECT
        comment_id,
        body,
        ticker,
        score,
        created_utc,
        {embedding_column} as embedding
    FROM historical_reddit_comments
    WHERE 
        created_utc BETWEEN '2025-12-24' AND '2026-01-01'
        AND {embedding_column} IS NOT NULL
        AND body IS NOT NULL
        AND LENGTH(body) > 10
    ORDER BY created_utc DESC
    """

    with get_connection() as conn:
        df = pd.read_sql(text(query), conn, params={"threshold": threshold})

    logger.info(f"Fetched {len(df)} comments with embeddings")

    # Convert embedding column from string representation to numpy array
    # pgvector stores as string like '[0.1, 0.2, ...]'
    if len(df) > 0:
        df["embedding"] = df["embedding"].apply(
            lambda x: (
                np.array(x)
                if isinstance(x, (list, np.ndarray))
                else np.fromstring(x.strip("[]"), sep=",")
            )
        )

    return df


def run_bertopic_clustering(df: pd.DataFrame, min_cluster_size: int = 50):
    """
    Run BERTopic clustering on the embeddings.

    Args:
        df: DataFrame with 'embedding' column containing numpy arrays
        min_cluster_size: Minimum number of documents per cluster

    Returns:
        Tuple of (BERTopic model, topics array, probabilities array)
    """
    logger.info(f"Running BERTopic with min_cluster_size={min_cluster_size}")

    # Extract embeddings as a 2D array
    embeddings = np.vstack(df["embedding"].values)
    documents = df["body"].tolist()

    logger.info(f"Embeddings shape: {embeddings.shape}")

    # Initialize BERTopic
    # Using pre-computed embeddings, so we don't need an embedding model
    topic_model = BERTopic(
        embedding_model=None,  # We already have embeddings
        min_topic_size=min_cluster_size,
        nr_topics="auto",  # Let it determine optimal number
        calculate_probabilities=True,  # Needed for confidence scores
        verbose=True,
    )

    # Fit the model on documents with pre-computed embeddings
    topics, probabilities = topic_model.fit_transform(documents, embeddings)

    logger.info(f"Found {len(set(topics)) - 1} topics (excluding noise cluster -1)")

    # Log topic distribution
    topic_counts = pd.Series(topics).value_counts().sort_index()
    logger.info(f"Topic distribution:\n{topic_counts}")

    return topic_model, topics, probabilities


def get_topic_info(topic_model: BERTopic, df: pd.DataFrame, topics: np.ndarray):
    """
    Extract detailed information about each topic.

    Args:
        topic_model: Fitted BERTopic model
        df: Original dataframe with comment metadata
        topics: Array of topic assignments

    Returns:
        DataFrame with topic metadata and representative documents
    """
    logger.info("Extracting topic information")

    # Get BERTopic's built-in topic info
    topic_info = topic_model.get_topic_info()

    # Add our custom metadata
    df_with_topics = df.copy()
    df_with_topics["topic"] = topics

    enhanced_topics = []
    for topic_id in topic_info["Topic"]:
        if topic_id == -1:  # Skip noise cluster
            continue

        # Get documents in this topic
        topic_docs = df_with_topics[df_with_topics["topic"] == topic_id]

        # Get representative documents (BERTopic provides this)
        representative_docs = topic_model.get_representative_docs(topic_id)

        # Calculate sentiment distribution (using your existing FinBERT predictions if available)
        # For now, we'll just aggregate based on what's in the data

        # Ticker distribution
        ticker_dist = topic_docs["ticker"].value_counts().head(5).to_dict()

        # Score statistics
        avg_score = topic_docs["score"].mean()
        max_score = topic_docs["score"].max()

        enhanced_topics.append(
            {
                "topic_id": topic_id,
                "count": len(topic_docs),
                "top_words": topic_info[topic_info["Topic"] == topic_id]["Name"].values[
                    0
                ],
                "representative_docs": representative_docs[:3],  # Top 3 representative
                "top_tickers": ticker_dist,
                "avg_score": avg_score,
                "max_score": max_score,
                "time_range": f"{topic_docs['created_utc'].min()} to {topic_docs['created_utc'].max()}",
            }
        )

    return pd.DataFrame(enhanced_topics)


def analyze_topics(hours: int = 24, min_cluster_size: int = 50):
    """
    Main analysis function that orchestrates the entire pipeline.

    Args:
        hours: Number of hours to look back
        min_cluster_size: Minimum cluster size for BERTopic
    """
    logger.info("=" * 80)
    logger.info("Starting BERTopic Analysis")
    logger.info("=" * 80)

    # Step 1: Fetch data
    df = fetch_embeddings_for_period(hours=hours)

    if len(df) < min_cluster_size:
        logger.warning(
            f"Only {len(df)} documents found, which is less than min_cluster_size={min_cluster_size}"
        )
        logger.warning(
            "Cannot perform meaningful clustering. Try increasing the time window."
        )
        return None

    # Step 2: Run clustering
    topic_model, topics, probabilities = run_bertopic_clustering(
        df, min_cluster_size=min_cluster_size
    )

    # Step 3: Extract topic information
    topic_summary = get_topic_info(topic_model, df, topics)

    # Step 4: Display results
    logger.info("\n" + "=" * 80)
    logger.info("TOPIC SUMMARY")
    logger.info("=" * 80)

    for _, topic in topic_summary.iterrows():
        logger.info(f"\n--- Topic {topic['topic_id']} ---")
        logger.info(f"Count: {topic['count']} documents")
        logger.info(f"Top words: {topic['top_words']}")
        logger.info(f"Top tickers: {topic['top_tickers']}")
        logger.info(
            f"Avg score: {topic['avg_score']:.1f}, Max score: {topic['max_score']}"
        )
        logger.info(f"Time range: {topic['time_range']}")
        logger.info("\nRepresentative documents:")
        for i, doc in enumerate(topic["representative_docs"][:2], 1):
            logger.info(f"  {i}. {doc[:200]}...")

    # Save visualizations (optional - BERTopic has many built-in visualizations)
    logger.info("\nGenerating visualizations...")
    try:
        # These will save to current directory as HTML files
        fig_topics = topic_model.visualize_topics()
        fig_topics.write_html("topic_visualization.html")
        logger.info("Saved topic_visualization.html")

        # Embeddings visualization requires UMAP to be fitted
        # This might be slow for large datasets
        embeddings = np.vstack(df["embedding"].values)
        fig_docs = topic_model.visualize_documents(
            df["body"].tolist(),
            embeddings=embeddings,
            hide_document_hover=True,  # Faster rendering
        )
        fig_docs.write_html("document_visualization.html")
        logger.info("Saved document_visualization.html")
    except Exception as e:
        logger.warning(f"Could not generate visualizations: {e}")

    return {
        "model": topic_model,
        "topics": topics,
        "probabilities": probabilities,
        "summary": topic_summary,
        "dataframe": df,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run BERTopic clustering on Reddit comments"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Number of hours to look back (default: 24)",
    )
    parser.add_argument(
        "--min-cluster-size",
        type=int,
        default=50,
        help="Minimum cluster size for BERTopic (default: 50)",
    )

    args = parser.parse_args()

    results = analyze_topics(hours=args.hours, min_cluster_size=args.min_cluster_size)

    if results:
        logger.info("\n" + "=" * 80)
        logger.info("Analysis complete!")
        logger.info(
            f"Found {len(results['summary'])} topics from {len(results['dataframe'])} comments"
        )
        logger.info("Check the HTML files for interactive visualizations")
        logger.info("=" * 80)
