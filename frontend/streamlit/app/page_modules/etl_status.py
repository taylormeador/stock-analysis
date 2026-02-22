import pandas as pd
import streamlit as st
from styles import apply_custom_css
from utils import get_json, live_clock

from components.etl_status import (
    # system_health_overview,
    realtime_component_status,
    task_performance,
    sidebar_stats,
)

apply_custom_css()

# Page header
st.title(":material/settings: ETL Pipeline Status")
st.caption("Monitor data collection and processing health")
st.divider()

# Fetch data from API
with st.spinner("Loading data..."):
    json_response = get_json("/etl-status")
    data = json_response["data"]

if not data:
    st.error(":material/error: **No data available**\n\n")
    st.stop()

etl_status_df = pd.DataFrame(data["etl_task_statuses"])
failed_task_df = pd.DataFrame(data["failed_task_count"])
task_deltas_df = pd.DataFrame(data["task_time_deltas"])
num_tasks_processed = data["num_tasks_processed"]
task_failure_rate = data["task_failure_rate"]

# Overall system status
# st.markdown("### :material/search: System Health Overview")
# system_health_overview()
# st.divider()

# ETL component real time dashboard
st.subheader(":material/account_tree: Pipeline Components")
realtime_component_status()
st.divider()

# Data Quality Metrics
# st.subheader(":material/verified: Data Quality Metrics")
# data_quality_metrics()
# st.divider()

# Task Performance Statistics
st.subheader(":material/speed: Task Performance")
task_performance(task_deltas_df)
st.divider()

# static_info()
# Information box
st.info(
    ":material/info: **About ETL Pipeline**\n\n"
    "The ETL pipeline runs continuously to collect, process, and analyze data from multiple sources. "
    "All tasks are scheduled using **Celery Beat** and executed by distributed workers with **Redis**-based coordination."
)

# Sidebar
with st.sidebar:
    st.markdown("### :material/schedule: Time")
    live_clock()

    sidebar_stats()
