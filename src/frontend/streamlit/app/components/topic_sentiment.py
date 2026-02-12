"""
Plotly visualization for topic sentiment/confidence quadrant chart.

This module creates an interactive scatter plot showing topics positioned by
sentiment (x-axis) and confidence (y-axis), with colors assigned dynamically
per snapshot based on dominant ticker.
"""

import plotly.graph_objects as go
import pandas as pd
from typing import List, Dict


# Color palette for ticker assignment (24 distinct colors)
TICKER_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
    "#aec7e8",
    "#ffbb78",
    "#98df8a",
    "#ff9896",
    "#c5b0d5",
    "#c49c94",
    "#f7b6d2",
    "#c7c7c7",
    "#dbdb8d",
    "#9edae5",
    "#393b79",
    "#637939",
    "#8c6d31",
    "#843c39",
]

DEFAULT_COLOR = "#cccccc"  # Gray for topics without clear ticker dominance


def assign_ticker_colors(topic_summary_df: pd.DataFrame) -> Dict[str, str]:
    """
    Assign colors to tickers dynamically for this snapshot.

    Args:
        topic_summary_df: DataFrame with topic info including 'top_tickers'

    Returns:
        Dictionary mapping ticker symbols to hex colors
    """
    # Collect all tickers mentioned across all topics
    all_tickers = set()
    for tickers_dict in topic_summary_df["top_tickers"]:
        if isinstance(tickers_dict, dict):
            all_tickers.update(tickers_dict.keys())

    # Sort tickers by total mentions across all topics
    ticker_counts = {}
    for ticker in all_tickers:
        ticker_counts[ticker] = sum(
            tickers_dict.get(ticker, 0)
            for tickers_dict in topic_summary_df["top_tickers"]
            if isinstance(tickers_dict, dict)
        )

    sorted_tickers = sorted(ticker_counts.items(), key=lambda x: x[1], reverse=True)

    # Assign colors from palette
    ticker_color_map = {}
    for i, (ticker, _) in enumerate(sorted_tickers):
        if i < len(TICKER_COLORS):
            ticker_color_map[ticker] = TICKER_COLORS[i]
        else:
            ticker_color_map[ticker] = DEFAULT_COLOR

    return ticker_color_map


def get_dominant_ticker(
    top_tickers: dict, min_concentration: float = 0.3
) -> str | None:
    """
    Get the dominant ticker for a topic if one exists.

    Args:
        top_tickers: Dictionary of ticker -> count
        min_concentration: Minimum % of mentions for a ticker to be considered dominant

    Returns:
        Ticker symbol if dominant, None otherwise
    """
    if not top_tickers or not isinstance(top_tickers, dict):
        return None

    total_mentions = sum(top_tickers.values())
    if total_mentions == 0:
        return None

    # Get ticker with most mentions
    top_ticker = max(top_tickers.items(), key=lambda x: x[1])
    concentration = top_ticker[1] / total_mentions

    if concentration >= min_concentration:
        return top_ticker[0]

    return None


def create_topic_sentiment_chart(
    topic_summary_df: pd.DataFrame, snapshot_timestamp: str = None
) -> go.Figure:
    """
    Create interactive sentiment/confidence scatter plot for topics.

    Args:
        topic_summary_df: DataFrame with columns:
            - llm_sentiment: float from -1 to 1
            - llm_confidence: float from 0 to 1
            - llm_theme: str summary
            - llm_insight: str key insight
            - count: int number of comments
            - top_tickers: dict of ticker -> count
            - representative_docs: list of sample comments
        snapshot_timestamp: Optional timestamp string for chart title

    Returns:
        Plotly Figure object
    """
    # Assign colors for this snapshot
    ticker_color_map = assign_ticker_colors(topic_summary_df)

    # Prepare data for plotting
    plot_data = []
    for _, topic in topic_summary_df.iterrows():
        # Determine color based on dominant ticker
        dominant_ticker = get_dominant_ticker(topic["top_tickers"])
        color = (
            ticker_color_map.get(dominant_ticker, DEFAULT_COLOR)
            if dominant_ticker
            else DEFAULT_COLOR
        )

        # Format ticker info for hover
        ticker_info = ", ".join(
            [
                f"{ticker}: {count}"
                for ticker, count in sorted(
                    (
                        topic["top_tickers"].items()
                        if isinstance(topic["top_tickers"], dict)
                        else []
                    ),
                    key=lambda x: x[1],
                    reverse=True,
                )[:5]
            ]
        )

        # Format sample comment for hover (first representative doc)
        sample_comment = (
            topic["representative_docs"][0][:200] + "..."
            if topic["representative_docs"] and len(topic["representative_docs"]) > 0
            else "N/A"
        )

        # Create hover text
        hover_text = (
            f"<b>{topic['llm_theme'][:100]}</b><br>"
            f"<br>"
            f"<b>Sentiment:</b> {topic['llm_sentiment']:.2f} | <b>Confidence:</b> {topic['llm_confidence']:.2f}<br>"
            f"<b>Comments:</b> {topic['count']}<br>"
            f"<b>Tickers:</b> {ticker_info}<br>"
            f"<br>"
            f"<b>Key Insight:</b> {topic['llm_insight']}<br>"
            f"<br>"
            f"<b>Sample:</b> {sample_comment}"
        )

        plot_data.append(
            {
                "sentiment": topic["llm_sentiment"],
                "confidence": topic["llm_confidence"],
                "size": topic["count"],
                "color": color,
                "ticker_label": dominant_ticker if dominant_ticker else "Mixed",
                "hover_text": hover_text,
                "theme": (
                    topic["llm_theme"][:50] + "..."
                    if len(topic["llm_theme"]) > 50
                    else topic["llm_theme"]
                ),
            }
        )

    df_plot = pd.DataFrame(plot_data)

    # Create scatter plot
    fig = go.Figure()

    # Group by color (ticker) for legend
    for ticker_label in df_plot["ticker_label"].unique():
        ticker_data = df_plot[df_plot["ticker_label"] == ticker_label]

        fig.add_trace(
            go.Scatter(
                x=ticker_data["sentiment"],
                y=ticker_data["confidence"],
                mode="markers+text",
                name=ticker_label,
                marker=dict(
                    size=ticker_data["size"] / 2,  # Scale down for visibility
                    color=ticker_data["color"].iloc[0],
                    opacity=0.7,
                    line=dict(width=1, color="white"),
                ),
                text=ticker_data["theme"],
                textposition="top center",
                textfont=dict(size=9, color="#fafafa"),
                hovertext=ticker_data["hover_text"],
                hoverinfo="text",
            )
        )

    # Update layout
    title_text = "WSB Topic Sentiment & Confidence Analysis"
    if snapshot_timestamp:
        title_text += f" - {snapshot_timestamp}"

    fig.update_layout(
        title=dict(text=title_text, font=dict(size=18, color="#00FF41")),
        xaxis=dict(
            title="Sentiment (Bearish ← → Bullish)",
            range=[-1.1, 1.1],
            gridcolor="rgba(0, 255, 65, 0.1)",
            zeroline=True,
            zerolinecolor="rgba(0, 255, 65, 0.3)",
            zerolinewidth=2,
        ),
        yaxis=dict(
            title="Confidence",
            range=[-0.05, 1.05],
            gridcolor="rgba(0, 255, 65, 0.1)",
        ),
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="#fafafa", family="monospace"),
        hovermode="closest",
        showlegend=True,
        legend=dict(
            title=dict(text="Dominant Ticker"),
            bgcolor="rgba(0, 0, 0, 0.5)",
            bordercolor="#00FF41",
            borderwidth=1,
        ),
        height=600,
    )

    # Add quadrant lines
    fig.add_hline(y=0.5, line_dash="dot", line_color="rgba(0, 255, 65, 0.2)")
    fig.add_vline(x=0, line_dash="dot", line_color="rgba(0, 255, 65, 0.2)")

    return fig


def create_multi_snapshot_chart(snapshots: List[pd.DataFrame]) -> go.Figure:
    """
    Create chart with slider to navigate between multiple snapshots.

    Args:
        snapshots: List of DataFrames, each representing one snapshot

    Returns:
        Plotly Figure with slider
    """
    if not snapshots:
        # Return empty chart
        return go.Figure().update_layout(
            title="No snapshots available",
            plot_bgcolor="#0e1117",
            paper_bgcolor="#0e1117",
        )

    # Create frames for each snapshot
    frames = []
    for snapshot_df in snapshots:
        # Get timestamp from the dataframe (all rows have same generated_at)
        timestamp = snapshot_df["generated_at"].iloc[0]
        timestamp_str = pd.to_datetime(timestamp).strftime("%Y-%m-%d %H:%M UTC")

        # Assign colors for this snapshot
        ticker_color_map = assign_ticker_colors(snapshot_df)

        # Prepare data
        plot_data = []
        for _, topic in snapshot_df.iterrows():
            dominant_ticker = get_dominant_ticker(topic["top_tickers"])
            color = (
                ticker_color_map.get(dominant_ticker, DEFAULT_COLOR)
                if dominant_ticker
                else DEFAULT_COLOR
            )

            ticker_info = ", ".join(
                [
                    f"{ticker}: {count}"
                    for ticker, count in sorted(
                        (
                            topic["top_tickers"].items()
                            if isinstance(topic["top_tickers"], dict)
                            else []
                        ),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:5]
                ]
            )

            sample_comment = (
                topic["representative_docs"][0][:200] + "..."
                if topic["representative_docs"]
                and len(topic["representative_docs"]) > 0
                else "N/A"
            )

            hover_text = (
                f"<b>{topic['llm_theme'][:150]}</b><br>"
                f"<b>{topic['llm_theme'][150:400]}</b><br>"
                f"<br>"
                f"<b>Sentiment:</b> {topic['llm_sentiment']:.2f} | <b>Confidence:</b> {topic['llm_confidence']:.2f}<br>"
                f"<b>Comments:</b> {topic['count']}<br>"
                f"<b>Tickers:</b> {ticker_info}<br>"
                f"<br>"
                f"<b>Key Insight:</b> {topic['llm_insight']}<br>"
                f"<br>"
                f"<b>Sample:</b> {sample_comment}"
            )

            plot_data.append(
                {
                    "sentiment": topic["llm_sentiment"],
                    "confidence": topic["llm_confidence"],
                    "size": topic["count"] / 2,
                    "color": color,
                    "ticker_label": dominant_ticker if dominant_ticker else "Mixed",
                    "hover_text": hover_text,
                    "theme": (
                        topic["llm_theme"][:50] + "..."
                        if len(topic["llm_theme"]) > 50
                        else topic["llm_theme"]
                    ),
                }
            )

        df_plot = pd.DataFrame(plot_data)

        # Create traces for this frame
        frame_traces = []
        for ticker_label in df_plot["ticker_label"].unique():
            ticker_data = df_plot[df_plot["ticker_label"] == ticker_label]

            frame_traces.append(
                go.Scatter(
                    x=ticker_data["sentiment"],
                    y=ticker_data["confidence"],
                    mode="markers+text",
                    name=ticker_label,
                    marker=dict(
                        size=ticker_data["size"] / 2,
                        color=ticker_data["color"].iloc[0],
                        opacity=0.7,
                        line=dict(width=1, color="white"),
                    ),
                    text=ticker_data["theme"],
                    textposition="top center",
                    textfont=dict(size=9, color="#fafafa"),
                    hovertext=ticker_data["hover_text"],
                    hoverinfo="text",
                )
            )

        frames.append(go.Frame(data=frame_traces, name=timestamp_str))

    # Create initial figure with first snapshot
    initial_timestamp = pd.to_datetime(snapshots[0]["generated_at"].iloc[0]).strftime(
        "%Y-%m-%d %H:%M UTC"
    )
    fig = go.Figure(data=frames[0].data, frames=frames)

    # Add slider
    sliders = [
        dict(
            active=0,
            steps=[
                dict(
                    method="animate",
                    args=[
                        [
                            pd.to_datetime(
                                snapshot_df["generated_at"].iloc[0]
                            ).strftime("%Y-%m-%d %H:%M UTC")
                        ],
                        dict(
                            mode="immediate",
                            frame=dict(duration=300, redraw=True),
                            transition=dict(duration=300),
                        ),
                    ],
                    label=pd.to_datetime(snapshot_df["generated_at"].iloc[0]).strftime(
                        "%Y-%m-%d %H:%M UTC"
                    ),
                )
                for snapshot_df in snapshots
            ],
            x=0.1,
            y=0,
            currentvalue=dict(prefix="Snapshot: ", visible=True, xanchor="left"),
            len=0.9,
        )
    ]

    # Update layout
    fig.update_layout(
        title=dict(
            text=f"WSB Topic Sentiment & Confidence - {initial_timestamp}",
            font=dict(size=18, color="#00FF41"),
        ),
        xaxis=dict(
            title="Sentiment (Bearish ← → Bullish)",
            range=[-1.1, 1.1],
            gridcolor="rgba(0, 255, 65, 0.1)",
            zeroline=True,
            zerolinecolor="rgba(0, 255, 65, 0.3)",
            zerolinewidth=2,
        ),
        yaxis=dict(
            title="Confidence",
            range=[-0.05, 1.05],
            gridcolor="rgba(0, 255, 65, 0.1)",
        ),
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="#fafafa", family="monospace"),
        hovermode="closest",
        showlegend=True,
        legend=dict(
            title=dict(text="Dominant Ticker"),
            bgcolor="rgba(0, 0, 0, 0.5)",
            bordercolor="#00FF41",
            borderwidth=1,
        ),
        height=1000,
        sliders=sliders,
    )

    # Add quadrant lines
    fig.add_hline(y=0.5, line_dash="dot", line_color="rgba(0, 255, 65, 0.2)")
    fig.add_vline(x=0, line_dash="dot", line_color="rgba(0, 255, 65, 0.2)")

    return fig
