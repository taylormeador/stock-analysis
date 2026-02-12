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

import numpy as np
import pandas as pd
from anthropic import Anthropic
from bertopic import BERTopic
from sqlalchemy import text

from app.database.db import get_connection
from app.database.models import reddit_topic_cluster_summaries as model
from app.utils import TaskStatusTracker

logger = logging.getLogger(__name__)

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def fetch_embeddings():
    """
    Fetch comment embeddings from the database.

    Returns:
        DataFrame with columns: id, comment_id, body, ticker, score, created_utc, embedding
    """
    logger.info("Fetching embeddings from last 24 hours")

    query = """
        SELECT DISTINCT on (comment_id)
            comment_id,
            body,
            ticker,
            score,
            created_utc,
            embedding
        FROM reddit_comments
        WHERE 
            created_utc >= NOW() - INTERVAL '24 Hours'
            AND embedding IS NOT NULL
            AND body IS NOT NULL
            AND LENGTH(body) > 10
        ORDER BY comment_id, created_utc DESC;
    """
    with get_connection() as conn:
        df = pd.read_sql(text(query), conn)

    logger.info(f"Fetched {len(df)} comments with embeddings")

    # Convert embedding column from string representation to numpy array
    # pgvector stores as string like '[0.1, 0.2, ...]'
    if len(df) > 0:
        df["embedding"] = df["embedding"].apply(
            lambda x: (  # type: ignore
                np.array(x)
                if isinstance(x, (list, np.ndarray))
                else np.fromstring(x.strip("[]"), sep=",")
            )
        )

    return df


def run_bertopic_clustering(df: pd.DataFrame, min_cluster_size: int):
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
    embeddings = np.vstack(df["embedding"].values)  # type: ignore
    documents = df["body"].tolist()

    logger.info(f"Embeddings shape: {embeddings.shape}")

    # Initialize BERTopic
    # Using pre-computed embeddings, so we don't need an embedding model
    topic_model = BERTopic(
        embedding_model=None,
        min_topic_size=min_cluster_size,
        nr_topics="auto",
        calculate_probabilities=True,
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
        representative_docs = topic_model.get_representative_docs(topic_id)

        top_words = topic_info[topic_info["Topic"] == topic_id]["Name"].values[0]

        # Ticker distribution
        ticker_dist = topic_docs["ticker"].value_counts().head(5).to_dict()

        # Score statistics
        avg_score = topic_docs["score"].mean()
        max_score = topic_docs["score"].max()

        enhanced_topics.append(
            {
                "topic_id": topic_id,
                "count": len(topic_docs),
                "top_words": top_words,
                "representative_docs": representative_docs[:3],
                "top_tickers": ticker_dist,
                "avg_score": avg_score,
                "max_score": max_score,
                "time_range_start": topic_docs["created_utc"].min(),
                "time_range_end": topic_docs["created_utc"].max(),
            }
        )

    return pd.DataFrame(enhanced_topics)


def summarize_topic_with_llm(
    topic_id: int,
    representative_docs: list,
    top_words: str,
    top_tickers: dict,
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
    prompt = f"""
        Analyze this cluster of Reddit comments from r/wallstreetbets and provide a structured summary.

        Top words (from clustering): {top_words}
        Top tickers mentioned: {', '.join([f"{k} ({v})" for k, v in list(top_tickers.items())[:5]])}

        Representative comments from this cluster:
        {chr(10).join([f"{i+1}. {doc}" for i, doc in enumerate(representative_docs[:5])])}

        Please provide:
        1. Theme Summary (2-3 sentences): What is the main topic/narrative being discussed?
        2. Sentiment Score: Rate the overall market sentiment as a number from -1.0 (very bearish) to +1.0 (very bullish), with 0.0 being neutral
        3. Confidence Score: Rate your confidence in the sentiment assessment from 0.0 (very uncertain) to 1.0 (very confident)
        4. Key Insight: One sentence capturing the most important takeaway

        Format your response EXACTLY as:
        THEME: [your summary]
        SENTIMENT: [number from -1.0 to 1.0]
        CONFIDENCE: [number from 0.0 to 1.0]
        INSIGHT: [key insight]

        Example:
        THEME: Discussion about NVDA earnings beat expectations with strong guidance.
        SENTIMENT: 0.75
        CONFIDENCE: 0.85
        INSIGHT: Retail traders are highly bullish on NVDA's AI dominance continuing.
            """

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse the response
        response_text = message.content[0].text  # type: ignore
        lines = response_text.strip().split("\n")
        result = {"theme": "", "sentiment": 0.0, "confidence": 0.0, "insight": ""}

        for line in lines:
            if line.startswith("THEME:"):
                result["theme"] = line.replace("THEME:", "").strip()
            elif line.startswith("SENTIMENT:"):
                try:
                    result["sentiment"] = float(line.replace("SENTIMENT:", "").strip())
                except ValueError:
                    result["sentiment"] = 0.0
            elif line.startswith("CONFIDENCE:"):
                try:
                    result["confidence"] = float(
                        line.replace("CONFIDENCE:", "").strip()
                    )
                except ValueError:
                    result["confidence"] = 0.5
            elif line.startswith("INSIGHT:"):
                result["insight"] = line.replace("INSIGHT:", "").strip()

        logger.info(
            f"Topic {topic_id} - Sentiment: {result['sentiment']:.2f}, Confidence: {result['confidence']:.2f}"
        )

        return result

    except Exception as e:
        logger.error(f"Error calling Claude API: {e}")
        return {
            "theme": "Error generating summary",
            "sentiment": 0.0,
            "confidence": 0.0,
            "insight": "Failed to analyze",
        }


def analyze_topics(tracker: TaskStatusTracker, min_cluster_size: int):
    """
    Main analysis function that orchestrates the entire pipeline.

    Args:
        min_cluster_size: Minimum cluster size for BERTopic
    """
    logger.info("Starting BERTopic Analysis")
    tracker.update_status_message("Starting BERTopic analysis...")

    # Step 1: Fetch data
    df = fetch_embeddings()
    tracker.update_progress(0.2)

    if len(df) < min_cluster_size:
        logger.warning(
            f"Only {len(df)} documents found, which is less than min_cluster_size={min_cluster_size}"
        )
        logger.warning(
            "Cannot perform meaningful clustering. Try increasing the time window."
        )
        tracker.update_status_message(
            "Not enough documents found to perform clustering"
        )
        return None

    # Step 2: Run clustering
    tracker.update_status_message("Clustering topics...")
    topic_model, topics, probabilities = run_bertopic_clustering(df, min_cluster_size)
    tracker.update_progress(0.4)

    # Step 3: Extract topic information
    tracker.update_status_message("Extracting topic info...")
    topic_summary = get_topic_info(topic_model, df, topics)  # type: ignore
    tracker.update_progress(0.7)

    # Step 4: Generate LLM summaries for each topic
    logger.info("Generating LLM summaries...")
    tracker.update_status_message("Generating LLM summaries...")

    llm_summaries = []
    for _, topic in topic_summary.iterrows():
        summary = summarize_topic_with_llm(
            topic_id=topic["topic_id"],
            representative_docs=topic["representative_docs"],
            top_words=topic["top_words"],
            top_tickers=topic["top_tickers"],
        )
        llm_summaries.append(summary)
    tracker.update_progress(0.90)

    # Add LLM summaries to the dataframe
    topic_summary["llm_theme"] = [s["theme"] for s in llm_summaries]
    topic_summary["llm_sentiment"] = [s["sentiment"] for s in llm_summaries]
    topic_summary["llm_confidence"] = [s["confidence"] for s in llm_summaries]
    topic_summary["llm_insight"] = [s["insight"] for s in llm_summaries]

    # Write to db
    logger.info("Writing to database...")
    topic_summary = topic_summary.drop(columns=["topic_id"])
    stmt = model.insert().values(topic_summary.to_dict("records"))
    with get_connection() as conn:
        conn.execute(stmt)
        conn.commit()

    message = f"Found {len(topic_summary)} topics from {len(df)} comments"
    logger.info(message)
    tracker.update_status_message(message)

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
        "--min-cluster-size",
        type=int,
        default=50,
        help="Minimum cluster size for BERTopic (default: 50)",
    )

    args = parser.parse_args()

    tracker = TaskStatusTracker(
        task_id="delete-this-row",
        component_name="Reddit Real-Time Topic Cluster Summary",
        task_description="LLM generated analysis of Reddit comment data",
    )
    tracker.start_task()

    results = analyze_topics(tracker, min_cluster_size=args.min_cluster_size)

    if results:
        logger.info("\n" + "=" * 80)
        logger.info("Analysis complete!")
        logger.info(
            f"Found {len(results['summary'])} topics from {len(results['dataframe'])} comments"
        )
        logger.info("Check the HTML files for interactive visualizations")
        logger.info("=" * 80)
