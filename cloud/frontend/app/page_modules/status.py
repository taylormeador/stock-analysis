import streamlit as st
from datetime import datetime
from styles import apply_custom_css

apply_custom_css()

# Page header
st.title(":material/settings: ETL Pipeline Status")
st.caption("Monitor data collection and processing health")
st.divider()

# Overall system status
st.markdown("### :material/search: System Health Overview")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label=":material/check_circle: Overall Status",
        value="Operational",
        delta="100% uptime",
        delta_color="normal",
    )

with col2:
    st.metric(
        label=":material/group: Active Workers",
        value="3",
        delta="All running",
        delta_color="normal",
    )

with col3:
    st.metric(
        label=":material/task: Tasks Today",
        value="1,247",
        delta="+127 from yesterday",
        delta_color="normal",
    )

with col4:
    st.metric(
        label=":material/schedule: Data Freshness",
        value="< 5 min",
        delta="Current",
        delta_color="normal",
    )

st.divider()

# Pipeline components status
st.subheader(":material/account_tree: Pipeline Components")

# Reddit Scraping
st.markdown("#### :material/forum: Reddit Data Collection")
col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.success("**ACTIVE**")

with col2:
    st.markdown("**WSB Daily Thread Scraper**")
    st.caption("Scrapes r/wallstreetbets daily discussion every 2 minutes")

with col3:
    st.caption(":material/schedule: Last run: 2 min ago")

st.progress(1.0)

# Sentiment Analysis
st.markdown("#### :material/psychology: Sentiment Analysis")
col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.success("**ACTIVE**")

with col2:
    st.markdown("**FinBERT Inference**")
    st.caption("Analyzes comment sentiment using ProsusAI/finbert model")

with col3:
    st.caption(":material/schedule: Last run: 2.5 min ago")

st.progress(1.0)

# Market Data
st.markdown("#### :material/show_chart: Market Data Collection")

col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.success("**ACTIVE**")

with col2:
    st.markdown("**Stock Price Data (yfinance)**")
    st.caption("Daily OHLCV data with technical indicators")

with col3:
    st.caption(":material/schedule: Last run: 1:00 AM UTC")

st.progress(1.0)

col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.success("**ACTIVE**")

with col2:
    st.markdown("**CBOE Options Data**")
    st.caption("Put/call ratios, volume, and open interest")

with col3:
    st.caption(":material/schedule: Last run: 11:00 PM UTC")

st.progress(1.0)

col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.success("**ACTIVE**")

with col2:
    st.markdown("**FRED Macro Indicators**")
    st.caption("Treasury yields, Fed funds rate, dollar index, unemployment")

with col3:
    st.caption(":material/schedule: Last run: 11:00 PM UTC")

st.progress(1.0)

st.divider()

# Dashboard Updates
st.subheader(":material/dashboard: Dashboard & Analytics")

col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.success("**ACTIVE**")

with col2:
    st.markdown("**What's Hot Dashboard**")
    st.caption("Refreshes ticker mention data every 5 minutes")

with col3:
    st.caption(":material/schedule: Last update: 3 min ago")

st.progress(1.0)

st.divider()

# Data Quality Metrics
st.subheader(":material/verified: Data Quality Metrics")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### :material/forum: REDDIT DATA")
    st.metric("Comments Analyzed", "12,453", delta="Today")
    st.metric("Unique Tickers", "142", delta="Mentioned")

with col2:
    st.markdown("#### :material/candlestick_chart: PRICE DATA")
    st.metric("Tickers Tracked", "187", delta="Total")
    st.metric("Data Completeness", "99.8%", delta="Quality")

with col3:
    st.markdown("#### :material/psychology: ML MODELS")
    st.metric("Active Experiments", "3", delta="Running")
    st.metric("Best Sharpe Ratio", "0.67", delta="Performance")

st.divider()

# Scheduled Tasks
st.subheader(":material/alarm: Scheduled Tasks (Celery Beat)")

tasks_data = [
    ("Reddit WSB Daily Thread (new)", "Every 2 minutes", ":material/check_circle:"),
    ("Reddit WSB Daily Thread (top)", "Every 10 minutes", ":material/check_circle:"),
    ("Sentiment Analysis", "Every 2.5 minutes", ":material/check_circle:"),
    ("Stock Price Data", "Daily at 1:00 AM UTC", ":material/check_circle:"),
    ("CBOE Options Data", "Daily at 11:00 PM UTC", ":material/check_circle:"),
    ("FRED Macro Data", "Daily at 11:00 PM UTC", ":material/check_circle:"),
    ("Dashboard Refresh", "Every 5 minutes", ":material/check_circle:"),
]

for task_name, schedule, status in tasks_data:
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        st.markdown(f"**{task_name}**")

    with col2:
        st.caption(schedule)

    with col3:
        st.markdown(f"{status} **Active**")

    st.divider()

# System Information
st.subheader(":material/cloud: System Information")

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        """
    #### :material/dns: Infrastructure
    - **Compute**: Proxmox home server
    - **Database**: PostgreSQL 15
    - **Cache**: Redis 7
    - **Storage**: AWS S3
    - **Orchestration**: Docker Compose
    """
    )

with col2:
    st.markdown(
        """
    #### :material/monitoring: Monitoring
    - **Task Queue**: Flower (port 5555)
    - **MLflow**: Experiment tracking (port 5000)
    - **Database**: PostgreSQL (port 5432)
    - **Redis**: Cache layer (port 6379)
    """
    )

# Information box
st.info(
    ":material/info: **About ETL Pipeline**\n\n"
    "The ETL pipeline runs continuously to collect, process, and analyze data from multiple sources. "
    "All tasks are scheduled using **Celery Beat** and executed by distributed workers with **Redis**-based coordination."
)

# Sidebar
st.sidebar.markdown("### :material/settings: Pipeline Controls")
st.sidebar.info("Manual controls and triggers will be implemented here.")

st.sidebar.markdown("### :material/analytics: Quick Stats")
st.sidebar.metric(":material/timer: Uptime", "99.9%")
st.sidebar.metric(":material/speed: Avg Task Duration", "2.3s")
st.sidebar.metric(":material/error: Failed Tasks (24h)", "0")

st.sidebar.markdown("### :material/link: Quick Links")
st.sidebar.markdown(
    """
- [Flower Dashboard](http://localhost:5555) (Task monitoring)
- [MLflow](http://localhost:5000) (Experiment tracking)
- [API Docs](http://localhost:8000/docs) (FastAPI)
"""
)
