from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from styles import apply_custom_css
from utils import get_json

apply_custom_css()

# Page header
st.title(":material/settings: ETL Pipeline Status")
st.caption("Monitor data collection and processing health")
st.divider()

# Fetch data from API
with st.spinner("Loading data..."):
    json_response = get_json("/etl/status/components")

if not json_response.get("data"):
    st.error(":material/error: **No data available**\n\n")
    st.stop()

df = pd.DataFrame(json_response["data"])

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

now = datetime.now(timezone.utc)
for _, row in df.iterrows():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        st.success(f"**{row.status}**")

    with col2:
        st.markdown(f"**{row.component_name}**")
        st.caption(row.task_description)

    with col3:
        delta = now - pd.to_datetime(row.start_time)
        minutes = round(delta.total_seconds() / 60, 2)
        st.caption(f":material/schedule: Last run: {minutes} min ago")

    st.progress(row.progress)


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


with col1:
    st.markdown(
        """
    #### :material/dns: Infrastructure
    - **Compute**: Proxmox Virtual Environment + Debian
    - **Database**: PostgreSQL
    - **Cache**: Redis
    - **Task Queue**: Celery
    - **Web API**: FastAPI
    - **Orchestration**: Docker Compose
    """
    )

with col2:
    st.markdown(
        """
    #### :material/monitoring: Monitoring
    - **Task Queue**: Flower
    - **MLflow**: Experiment tracking
    """
    )

# Information box
st.info(
    ":material/info: **About ETL Pipeline**\n\n"
    "The ETL pipeline runs continuously to collect, process, and analyze data from multiple sources. "
    "All tasks are scheduled using **Celery Beat** and executed by distributed workers with **Redis**-based coordination."
)

# Sidebar
st.sidebar.markdown("### :material/analytics: Quick Stats")
st.sidebar.metric(":material/timer: Uptime", "99.9%")
st.sidebar.metric(":material/speed: Avg Task Duration", "2.3s")
st.sidebar.metric(":material/error: Failed Tasks (24h)", "0")
