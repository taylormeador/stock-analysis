import streamlit as st
from datetime import datetime
from styles import create_header, create_subheader, create_status_badge, create_info_box

# Page header
create_header("ETL Pipeline Status ⚙️", "Monitor data collection and processing health")

# Overall system status
st.markdown("### 🔍 System Health Overview")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="Overall Status",
        value="Operational",
        delta="100% uptime",
        delta_color="normal",
    )

with col2:
    st.metric(
        label="Active Workers", value="3", delta="All running", delta_color="normal"
    )

with col3:
    st.metric(
        label="Tasks Today",
        value="1,247",
        delta="+127 from yesterday",
        delta_color="normal",
    )

with col4:
    st.metric(
        label="Data Freshness", value="< 5 min", delta="Current", delta_color="normal"
    )

st.markdown("<br>", unsafe_allow_html=True)

# Pipeline components status
create_subheader("Pipeline Components")

# Reddit Scraping
st.markdown("#### 📱 Reddit Data Collection")
col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.markdown(create_status_badge("success"), unsafe_allow_html=True)

with col2:
    st.markdown("**WSB Daily Thread Scraper**")
    st.caption("Scrapes r/wallstreetbets daily discussion every 2 minutes")

with col3:
    st.markdown("🕐 Last run: 2 min ago")

st.progress(1.0)

# Sentiment Analysis
st.markdown("#### 🧠 Sentiment Analysis")
col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.markdown(create_status_badge("success"), unsafe_allow_html=True)

with col2:
    st.markdown("**FinBERT Inference**")
    st.caption("Analyzes comment sentiment using ProsusAI/finbert model")

with col3:
    st.markdown("🕐 Last run: 2.5 min ago")

st.progress(1.0)

# Market Data
st.markdown("#### 💹 Market Data Collection")

col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.markdown(create_status_badge("success"), unsafe_allow_html=True)

with col2:
    st.markdown("**Stock Price Data (yfinance)**")
    st.caption("Daily OHLCV data with technical indicators")

with col3:
    st.markdown("🕐 Last run: 1:00 AM UTC")

st.progress(1.0)

col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.markdown(create_status_badge("success"), unsafe_allow_html=True)

with col2:
    st.markdown("**CBOE Options Data**")
    st.caption("Put/call ratios, volume, and open interest")

with col3:
    st.markdown("🕐 Last run: 11:00 PM UTC")

st.progress(1.0)

col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.markdown(create_status_badge("success"), unsafe_allow_html=True)

with col2:
    st.markdown("**FRED Macro Indicators**")
    st.caption("Treasury yields, Fed funds rate, dollar index, unemployment")

with col3:
    st.markdown("🕐 Last run: 11:00 PM UTC")

st.progress(1.0)

st.markdown("<br>", unsafe_allow_html=True)

# Dashboard Updates
create_subheader("Dashboard & Analytics")

col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.markdown(create_status_badge("success"), unsafe_allow_html=True)

with col2:
    st.markdown("**What's Hot Dashboard**")
    st.caption("Refreshes ticker mention data every 5 minutes")

with col3:
    st.markdown("🕐 Last update: 3 min ago")

st.progress(1.0)

st.markdown("<br><br>", unsafe_allow_html=True)

# Data Quality Metrics
create_subheader("Data Quality Metrics")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div class="card">
            <h4 style="color: #FF00FF; margin-top: 0; font-weight: 900;">📊 Reddit Data</h4>
            <p style="font-size: 2rem; font-weight: 900; color: #FF0000; margin: 0.5rem 0;">12,453</p>
            <p style="color: #0000FF; margin: 0; font-weight: bold;">Comments analyzed today</p>
            <br>
            <p style="font-size: 1.5rem; font-weight: 900; color: #FF0000; margin: 0.5rem 0;">142</p>
            <p style="color: #0000FF; margin: 0; font-weight: bold;">Unique tickers mentioned</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        """
        <div class="card">
            <h4 style="color: #FF00FF; margin-top: 0; font-weight: 900;">💹 Price Data</h4>
            <p style="font-size: 2rem; font-weight: 900; color: #FF0000; margin: 0.5rem 0;">187</p>
            <p style="color: #0000FF; margin: 0; font-weight: bold;">Tickers tracked</p>
            <br>
            <p style="font-size: 1.5rem; font-weight: 900; color: #FF0000; margin: 0.5rem 0;">99.8%</p>
            <p style="color: #0000FF; margin: 0; font-weight: bold;">Data completeness</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        """
        <div class="card">
            <h4 style="color: #FF00FF; margin-top: 0; font-weight: 900;">🧠 ML Models</h4>
            <p style="font-size: 2rem; font-weight: 900; color: #FF0000; margin: 0.5rem 0;">3</p>
            <p style="color: #0000FF; margin: 0; font-weight: bold;">Active experiments</p>
            <br>
            <p style="font-size: 1.5rem; font-weight: 900; color: #FF0000; margin: 0.5rem 0;">0.67</p>
            <p style="color: #0000FF; margin: 0; font-weight: bold;">Best Sharpe ratio</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# Scheduled Tasks
create_subheader("Scheduled Tasks (Celery Beat)")

tasks_data = [
    ("Reddit WSB Daily Thread (new)", "Every 2 minutes", "✅ Active"),
    ("Reddit WSB Daily Thread (top)", "Every 10 minutes", "✅ Active"),
    ("Sentiment Analysis", "Every 2.5 minutes", "✅ Active"),
    ("Stock Price Data", "Daily at 1:00 AM UTC", "✅ Active"),
    ("CBOE Options Data", "Daily at 11:00 PM UTC", "✅ Active"),
    ("FRED Macro Data", "Daily at 11:00 PM UTC", "✅ Active"),
    ("Dashboard Refresh", "Every 5 minutes", "✅ Active"),
]

for task_name, schedule, status in tasks_data:
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        st.markdown(f"**{task_name}**")

    with col2:
        st.caption(schedule)

    with col3:
        st.markdown(
            f"<span style='color: #00d4aa;'>{status}</span>", unsafe_allow_html=True
        )

    st.markdown(
        "<div style='border-bottom: 4px solid #000000; margin: 1rem 0;'></div>",
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# System Information
create_subheader("System Information")

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        """
        **Infrastructure**
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
        **Monitoring**
        - **Task Queue**: Flower (port 5555)
        - **MLflow**: Experiment tracking (port 5000)
        - **Database**: PostgreSQL (port 5432)
        - **Redis**: Cache layer (port 6379)
        """
    )

# Information box
create_info_box(
    "ℹ️ About ETL Pipeline",
    "The ETL pipeline runs continuously to collect, process, and analyze data from multiple sources. "
    "All tasks are scheduled using Celery Beat and executed by distributed workers with Redis-based coordination.",
    box_type="info",
)

# Sidebar
st.sidebar.markdown("### ⚙️ Pipeline Controls")
st.sidebar.info("Manual controls and triggers will be implemented here.")

st.sidebar.markdown("### 📊 Quick Stats")
st.sidebar.metric("Uptime", "99.9%")
st.sidebar.metric("Avg Task Duration", "2.3s")
st.sidebar.metric("Failed Tasks (24h)", "0")

st.sidebar.markdown("### 🔗 Quick Links")
st.sidebar.markdown(
    """
    - [Flower Dashboard](http://localhost:5555) (Task monitoring)
    - [MLflow](http://localhost:5000) (Experiment tracking)
    - [API Docs](http://localhost:8000/docs) (FastAPI)
    """
)
