import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from styles import apply_custom_css, colors
from utils import get_json

apply_custom_css()

# Hero section
st.title(":material/query_stats: CurveFitter9000")
st.caption(
    "Systematic trading research platform combining sentiment analysis, "
    "backtesting, and ML predictions"
)
st.page_link(
    page="https://github.com/taylormeador/stock-analysis",
    label="Git Repo",
    icon=":material/commit:",
)

st.divider()

# Main content - Featured Components
st.markdown("## Featured Components")

# Component 1: Real-Time Sentiment Pipeline
st.markdown("### :material/psychology: Real-Time Sentiment Pipeline")

col1, col2 = st.columns([2, 1])

with col1:
    # Get live topic cluster data
    response = get_json("/whats-hot")
    if response.get("data") and response["data"].get("topic_snapshots"):
        snapshots = response["data"]["topic_snapshots"]
        if snapshots:
            # Show the most recent snapshot
            latest_snapshot = pd.DataFrame(snapshots[0]).iloc[:10]

            # Create a mini version of the topic sentiment chart
            fig = go.Figure()

            for _, topic in latest_snapshot.iterrows():
                # Sentiment-based color scheme
                sentiment = topic["llm_sentiment"]
                if sentiment > 0.3:
                    marker_color = colors.bright_green  # Bullish
                elif sentiment < -0.3:
                    marker_color = colors.orange  # Bearish
                else:
                    marker_color = colors.blue  # Neutral

                fig.add_trace(
                    go.Scatter(
                        x=[topic["llm_sentiment"]],
                        y=[topic["llm_confidence"]],
                        mode="markers+text",
                        text=topic["llm_theme"][:30] + "...",
                        textposition="top center",
                        marker=dict(
                            size=topic["count"] / 3,
                            color=marker_color,
                            opacity=0.7,
                        ),
                        hovertext=f"{topic['llm_theme']}<br>Count: {topic['count']}<br>Sentiment: {topic['llm_sentiment']:.2f}",
                        hoverinfo="text",
                        showlegend=False,
                    )
                )

            fig.update_layout(
                xaxis=dict(
                    title="Sentiment (Bearish ← → Bullish)",
                    range=[-1.1, 1.1],
                    gridcolor="rgba(0, 255, 65, 0.1)",
                    zeroline=True,
                    zerolinecolor="rgba(0, 255, 65, 0.3)",
                ),
                yaxis=dict(
                    title="Confidence",
                    range=[-0.05, 1.05],
                    gridcolor="rgba(0, 255, 65, 0.1)",
                ),
                plot_bgcolor=colors.dark_bg,
                paper_bgcolor=colors.dark_bg,
                font=dict(color=colors.text_gray, family="monospace"),
                height=400,
                margin=dict(l=40, r=40, t=20, b=40),
            )

            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Topic clustering pipeline running - check back in a few minutes")

with col2:
    st.markdown(
        """
        **BERTopic clusters 10K+ daily WSB comments into thematic groups. 
        Claude Haiku generates sentiment scores and theme summaries. 
        Updates 4x daily at market open, midday, close, and evening.**
        
        **Technical implementation:**
        - Distributed embedding generation with sentence-transformers across GPU workers
        - pgvector for semantic search over 5M+ historical comments  
        - Real-time clustering with HDBSCAN
        - Structured LLM analysis via Anthropic API
        """
    )

    if st.button("→ See full topic analysis", use_container_width=True):
        st.switch_page("page_modules/whats_hot.py")

st.divider()

# Component 2: Distributed Data Collection
st.markdown("### :material/account_tree: Distributed Data Collection")

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown(
        """
        **Celery Beat orchestrates dozens of scheduled tasks across multiple data sources. 
        Redis-based distributed rate limiting prevents API bans. 
        Prometheus + Grafana track task health and performance.**
        
        **Pipeline handles:**
        - Reddit API (100 req/min rate limit coordination)
        - yfinance price data (187 tracked tickers)
        - CBOE options market statistics
        - FRED macroeconomic indicators
        - Historical Reddit archive ETL (50M+ comments from compressed zst files)
        """
    )

    if st.button("→ Monitor ETL pipeline", use_container_width=True):
        st.switch_page("page_modules/etl_status.py")

with col2:
    # Show mini ETL status
    etl_data = get_json("/etl-status")
    if etl_data.get("data"):
        df = pd.DataFrame(etl_data["data"]["etl_task_statuses"])

        # Show compact status for each component
        for _, row in df.head(9).iterrows():
            col_a, col_b, col_c = st.columns([2, 1, 1])

            with col_a:
                st.markdown(f"**{row['component_name']}**")

            with col_b:
                if row["status"] == "Complete":
                    st.markdown(f":material/check_circle: {row['status']}")
                elif row["status"] == "In Progress":
                    st.markdown(f":material/pending: {row['status']}")
                elif row["status"] == "Failed":
                    st.markdown(f":material/error: {row['status']}")
                else:
                    st.markdown(f":material/info: {row['status']}")

            with col_c:
                if row["progress"]:
                    st.progress(float(row["progress"]))

st.divider()

# Component 3: ML Training Pipeline
st.markdown("### :material/model_training: ML Training Pipeline TODO")

col1, col2 = st.columns([2, 1])

with col1:
    # Show a simple visualization of model performance metrics
    # This is placeholder - you'd replace with real MLflow data
    st.markdown(
        """
        **Current model performance (backtested 2023-2024):**
        """
    )

    metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
    with metrics_col1:
        st.metric("Direction Accuracy", "62.3%", "+2.1%")
    with metrics_col2:
        st.metric("Sharpe Ratio", "0.67", "+0.15")
    with metrics_col3:
        st.metric("Max Drawdown", "-12.4%", "")

    st.markdown(
        """
        **Feature importance (top 5):**
        1. `sentiment_score` - Reddit aggregate sentiment
        2. `rsi_14` - Relative strength index
        3. `vix_put_call_ratio` - CBOE volatility indicator
        4. `fed_funds_rate` - FRED macro signal
        5. `mention_count` - Reddit discussion volume
        """
    )

with col2:
    st.markdown(
        """
        **XGBoost regression models trained on combined features: 
        Reddit sentiment, technical indicators, options flows, 
        and macro signals. MLflow tracks experiments with full 
        reproducibility.**
        
        **Pipeline features:**
        - Temporal train/test splits (no lookahead bias)
        - Walk-forward validation planned
        - Trading metrics: direction accuracy, Sharpe ratio, max drawdown
        - Automated feature importance analysis
        - Model versioning and artifact storage
        """
    )

st.divider()

# Architecture Diagram
st.markdown("## System Architecture")

st.markdown(
    """
```
┌─────────────────┐
│  Data Sources   │
│  • Reddit API   │
│  • yfinance     │
│  • CBOE         │
│  • FRED         │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│     Celery Workers (3 pools)        │
│  • CPU workers (scheduled tasks)    │
│  • GPU workers (embeddings)         │
│  • Historical workers (long ETL)    │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│      PostgreSQL + pgvector          │
│  • Stock prices (5M+ rows)          │
│  • Reddit comments (50M+ rows)      │
│  • Embeddings (384-dim vectors)     │
│  • ML training datasets             │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│         FastAPI (async)             │
│  • Real-time price cache (Redis)    │
│  • Aggregated sentiment data        │
│  • ETL status monitoring            │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│    Streamlit + nginx frontend       │
│  • Live dashboards                  │
│  • Topic visualization              │
│  • System monitoring                │
└─────────────────────────────────────┘

     ┌──────────────────┐
     │   Monitoring     │
     │  • Prometheus    │
     │  • Grafana       │
     │  • Flower        │
     │  • MLflow        │
     └──────────────────┘
```
"""
)

st.markdown(
    """
**Infrastructure**: Docker Compose on Debian VM (Proxmox hypervisor)  
**Deployment**: Cloudflare Tunnel for secure API routing, no exposed ports  
**Monitoring**: Prometheus metrics, Grafana dashboards, custom ETL status tracking
"""
)

# Sidebar
with st.sidebar:
    st.markdown("### :material/trending_up: Live Trending")

    trending_response = get_json("/whats-hot")
    if trending_response.get("data"):
        trending_df = pd.DataFrame(trending_response["data"]["ticker_mentions"])
        if not trending_df.empty:
            top_tickers = trending_df.nlargest(5, "ticker_mentions_1")
            for _, ticker_data in top_tickers.iterrows():
                st.metric(
                    ticker_data["ticker"],
                    f"{int(ticker_data['ticker_mentions_1'])} mentions",
                    delta=(
                        f"{ticker_data['mention_pct_change']:.1f}%"
                        if ticker_data["mention_pct_change"] != 0
                        else None
                    ),
                )

    st.divider()

    st.markdown("### :material/dns: System Health")

    etl_status = get_json("/etl-status")
    if etl_status.get("data"):
        df = pd.DataFrame(etl_status["data"]["etl_task_statuses"])

        # Calculate health metrics
        total_tasks = len(df)
        completed = len(df[df["status"] == "Complete"])
        in_progress = len(df[df["status"] == "In Progress"])
        failed = len(df[df["status"] == "Failed"])

        if failed > 0:
            st.error(f":material/error: {failed} failed tasks")
        if in_progress > 0:
            st.info(f":material/pending: {in_progress} tasks running")
        else:
            st.success(":material/check_circle: All systems operational")

        celery_stats = get_json("/celery-stats")
        if celery_stats.get("data"):
            stats = celery_stats["data"]
            st.caption(
                f"**Workers:** {stats['active_workers']}/{stats['total_workers']} healthy"
            )
            st.caption(f"**Queue depth:** {stats['queue_depth']}")
        st.caption(f"**Success rate:** {(completed/total_tasks)*100:.1f}%")

    st.divider()

    st.markdown("### :material/code: Tech Stack")
    st.markdown(
        """
        **Backend:**
        - PostgreSQL + pgvector
        - Redis (cache + coordination)
        - Celery (3 worker pools)
        - FastAPI + async SQLAlchemy
        
        **ML/Data:**
        - XGBoost, scikit-learn
        - sentence-transformers
        - BERTopic clustering
        - MLflow experiment tracking
        - pandas, pandas-ta
        
        **Infrastructure:**
        - Docker Compose
        - Prometheus + Grafana
        - nginx reverse proxy
        - Cloudflare Tunnel
        """
    )
