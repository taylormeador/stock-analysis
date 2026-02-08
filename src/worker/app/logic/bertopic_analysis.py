"""
BERTopic clustering analysis for Reddit comments.

This script extracts embeddings from the database, runs BERTopic clustering,
and generates LLM summaries of discovered themes.

Usage:
    python bertopic_analysis.py --hours 24
"""

import argparse
import logging
import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from anthropic import Anthropic
from bertopic import BERTopic
from sqlalchemy import text

# Assuming your worker database connection setup
import sys

sys.path.append("/app")
from app.database.db import get_connection

# Initialize Anthropic client
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

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
        created_utc BETWEEN '2025-12-31' AND '2026-01-01'
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


def summarize_topic_with_llm(
    topic_id: int, representative_docs: list, top_words: str, top_tickers: dict
) -> dict:
    """
    Use Claude to generate a natural language summary of a topic.

    Args:
        topic_id: The topic ID
        representative_docs: List of representative documents from the cluster
        top_words: The c-TF-IDF top words
        top_tickers: Dictionary of top tickers mentioned

    Returns:
        Dictionary with summary, sentiment, and confidence
    """
    logger.info(f"Generating LLM summary for topic {topic_id}")

    # Prepare the prompt
    prompt = f"""Analyze this cluster of Reddit comments from r/wallstreetbets and provide a structured summary.

                Top words (from clustering): {top_words}
                Top tickers mentioned: {', '.join([f"{k} ({v})" for k, v in list(top_tickers.items())[:5]])}

                Representative comments from this cluster:
                {chr(10).join([f"{i+1}. {doc}" for i, doc in enumerate(representative_docs[:5])])}

                Please provide:
                1. Theme Summary (2-3 sentences): What is the main topic/narrative being discussed?
                2. Market Sentiment: Is the overall sentiment BULLISH, BEARISH, or NEUTRAL?
                3. Confidence Level: How confident are you in the sentiment assessment? (HIGH/MEDIUM/LOW)
                4. Key Insight: One sentence capturing the most important takeaway

                Format your response as:
                THEME: [your summary]
                SENTIMENT: [BULLISH/BEARISH/NEUTRAL]
                CONFIDENCE: [HIGH/MEDIUM/LOW]
                INSIGHT: [key insight]
    """

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",  # Haiku for cost efficiency
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse the response
        response_text = message.content[0].text

        # Extract structured fields
        lines = response_text.strip().split("\n")
        result = {"theme": "", "sentiment": "", "confidence": "", "insight": ""}

        for line in lines:
            if line.startswith("THEME:"):
                result["theme"] = line.replace("THEME:", "").strip()
            elif line.startswith("SENTIMENT:"):
                result["sentiment"] = line.replace("SENTIMENT:", "").strip()
            elif line.startswith("CONFIDENCE:"):
                result["confidence"] = line.replace("CONFIDENCE:", "").strip()
            elif line.startswith("INSIGHT:"):
                result["insight"] = line.replace("INSIGHT:", "").strip()

        logger.info(
            f"Topic {topic_id} - Sentiment: {result['sentiment']}, Confidence: {result['confidence']}"
        )

        return result

    except Exception as e:
        logger.error(f"Error calling Claude API: {e}")
        return {
            "theme": "Error generating summary",
            "sentiment": "UNKNOWN",
            "confidence": "LOW",
            "insight": "Failed to analyze",
        }


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

    # Step 4: Generate LLM summaries for each topic
    logger.info("\n" + "=" * 80)
    logger.info("Generating LLM summaries...")
    logger.info("=" * 80)

    llm_summaries = []
    for _, topic in topic_summary.iterrows():
        summary = summarize_topic_with_llm(
            topic_id=topic["topic_id"],
            representative_docs=topic["representative_docs"],
            top_words=topic["top_words"],
            top_tickers=topic["top_tickers"],
        )
        llm_summaries.append(summary)

    # Add LLM summaries to the dataframe
    topic_summary["llm_theme"] = [s["theme"] for s in llm_summaries]
    topic_summary["llm_sentiment"] = [s["sentiment"] for s in llm_summaries]
    topic_summary["llm_confidence"] = [s["confidence"] for s in llm_summaries]
    topic_summary["llm_insight"] = [s["insight"] for s in llm_summaries]

    # Step 5: Display results
    logger.info("\n" + "=" * 80)
    logger.info("TOPIC SUMMARY WITH LLM ANALYSIS")
    logger.info("=" * 80)

    for _, topic in topic_summary.iterrows():
        logger.info(f"\n{'='*60}")
        logger.info(f"TOPIC {topic['topic_id']}")
        logger.info(f"{'='*60}")
        logger.info(f"Documents: {topic['count']}")
        logger.info(f"Top words: {topic['top_words']}")
        logger.info(f"Top tickers: {topic['top_tickers']}")
        logger.info(
            f"Engagement: Avg score {topic['avg_score']:.1f}, Max {topic['max_score']}"
        )
        logger.info("\n--- LLM ANALYSIS ---")
        logger.info(f"Theme: {topic['llm_theme']}")
        logger.info(
            f"Sentiment: {topic['llm_sentiment']} (Confidence: {topic['llm_confidence']})"
        )
        logger.info(f"Key Insight: {topic['llm_insight']}")
        logger.info("\nSample comments:")
        for i, doc in enumerate(topic["representative_docs"][:2], 1):
            logger.info(f"  {i}. {doc[:150]}...")
        logger.info("")

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
