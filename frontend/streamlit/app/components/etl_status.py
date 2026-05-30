import streamlit as st
from datetime import datetime, timezone
import timeago
from utils import get_json, live_clock

from styles import colors
import plotly.graph_objects as go
import pandas as pd


def system_health_overview():
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


@st.fragment(run_every="5s")
def realtime_component_status():
    """This section updates every 5s without reloading the whole page."""
    placeholder = st.empty()

    json_response = get_json("/etl-status")

    if not json_response.get('data'):
        with placeholder.container():
            st.error(":material/error: **No data available**\n\n")
        return

    df = pd.DataFrame(json_response["data"]["etl_task_statuses"])
    now = datetime.now(timezone.utc)

    with placeholder.container():
        for _, row in df.iterrows():
            col1, col2, col3, col4 = st.columns([1, 3, 2, 1])
            with col1:
                if row.status == "Complete":
                    st.success(f"**{row.status}**")
                elif row.status == "Retrying":
                    st.warning(f"**{row.status} - {row.progress * 100:.0f}%**")
                elif row.status == "Failed":
                    st.error(f"**{row.status} - {row.progress * 100:.0f}%**")
                else:
                    st.info(f"**{row.status} - {row.progress * 100:.0f}%**")

            with col2:
                st.markdown(f"**{row.component_name}**")
                st.caption(row.task_description)

            with col3:
                st.markdown("**Status**")
                st.caption(row.status_message[:150])

            with col4:
                delta = now - pd.to_datetime(row.start_time)
                ago = timeago.format(delta, now)
                st.caption(f":material/schedule: Last run: {ago}")
                st.caption(f":material/avg_time: Run time: {row.run_time}s")

            st.progress(row.progress)


def task_performance(df: pd.DataFrame):
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=[
                df["p_50"].iloc[0],
                df["p_75"].iloc[0],
                df["p_90"].iloc[0],
                df["p_95"].iloc[0],
                df["p_99"].iloc[0],
                df["max_delta"].iloc[0],
            ],
            y=["p50 (median)", "p75", "p90", "p95", "p99", "max"],
            orientation="h",
            marker_color=colors.bright_green,
            text=[
                f"{v:.1f}s"
                for v in [
                    df["p_50"].iloc[0],
                    df["p_75"].iloc[0],
                    df["p_90"].iloc[0],
                    df["p_95"].iloc[0],
                    df["p_99"].iloc[0],
                    df["max_delta"].iloc[0],
                ]
            ],
            textposition="auto",
        )
    )

    fig.update_layout(
        title="Task Duration Percentiles",
        xaxis_title="Duration (seconds)",
        plot_bgcolor=colors.dark_bg,
        paper_bgcolor=colors.dark_bg,
        font=dict(color=colors.text_gray, family="monospace"),
        height=600,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)


def data_quality_metrics():
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


def static_info():
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            """
        #### :material/dns: Infrastructure
        - **Compute**: Proxmox Virtual Environment + Debian
        - **Database**: PostgreSQL
        - **Orchestration**: Docker Compose
        """
        )

    with col2:
        st.markdown(
            """
        #### :material/monitoring: Monitoring
        - **Task Queue**: Flower
        - **MLflow**: Experiment tracking
        - **Prometheus**: Operational Metrics
        - **Grafana**: Visualization
        """
        )

    # Information box
    st.info(
        ":material/info: **About ETL Pipeline**\n\n"
        "The ETL pipeline runs continuously to collect, process, and analyze data from multiple sources. "
        "All tasks are scheduled using **Celery Beat** and executed by distributed workers with **Redis**-based coordination."
    )


@st.fragment(run_every="1m")
def sidebar_stats():
    placeholder = st.empty()

    json_response = get_json("/etl-status")
    data = json_response["data"]

    if not data:
        with placeholder.container():
            st.error(":material/error: **No data available**\n\n")
        return

    task_deltas_df = pd.DataFrame(data["task_time_deltas"])
    num_tasks_processed = data["num_tasks_processed"]
    task_failure_rate = data["task_failure_rate"]

    mean_task_duration = round(float(task_deltas_df["mean"].iloc[0]), 2)
    failure_rate = int(task_failure_rate)

    with placeholder.container():
        st.markdown("### :material/analytics: Quick Stats (24h)")
        st.metric(
            ":material/timer: Tasks Completed", f"{sum(num_tasks_processed.values())}"
        )
        st.metric(":material/error: Task Failure Rate", f"{failure_rate}%")
        st.metric(":material/speed: Mean Task Duration", f"{mean_task_duration}s")
