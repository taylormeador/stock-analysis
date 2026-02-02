import logging
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from utils import fetch_s3_json

from styles import (
    create_header,
    create_metric_card,
    create_subheader,
    format_large_number,
    format_percentage,
    style_dataframe,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

# Page header
create_header(
    "What's Hot? 🔥", "Top trending tickers from r/WallStreetBets daily discussion"
)

# Fetch data from S3
with st.spinner("Loading data..."):
    json_response = fetch_s3_json("dashboard/whats_hot.json")

if not json_response:
    st.error("❌ No data available. The data pipeline may not have run yet.")
    st.info(
        "💡 The data is refreshed every 5 minutes from the WSB daily discussion thread."
    )
    st.stop()

# Extract ticker mentions data
ticker_data = json_response.get("data", {}).get("ticker_mentions", [])

if not ticker_data:
    st.warning("⚠️ No ticker mentions found in the latest data.")
    st.stop()

df = pd.DataFrame(ticker_data)

# Calculate summary metrics
total_mentions = df["todays_mentions"].sum()
top_ticker = df.iloc[0]["ticker"] if len(df) > 0 else "N/A"
top_ticker_mentions = df.iloc[0]["todays_mentions"] if len(df) > 0 else 0
avg_change = df["pct_change"].mean() if "pct_change" in df.columns else 0

# Display metrics in columns
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="Total Mentions",
        value=format_large_number(total_mentions),
    )

with col2:
    st.metric(
        label="Top Ticker",
        value=top_ticker,
        delta=f"{top_ticker_mentions} mentions",
    )

with col3:
    st.metric(
        label="Tickers Tracked",
        value=len(df),
    )

with col4:
    st.metric(
        label="Avg % Change",
        value=format_percentage(avg_change),
        delta_color="normal" if avg_change >= 0 else "inverse",
    )

st.markdown("<br>", unsafe_allow_html=True)

# Prepare data for display
display_df = df.copy()

# Format columns for better display
if "pct_change" in display_df.columns:
    display_df["pct_change"] = display_df["pct_change"].apply(
        lambda x: format_percentage(x) if pd.notna(x) else "N/A"
    )

# Rename columns for display
column_rename = {
    "ticker": "Ticker",
    "todays_mentions": "Today's Mentions",
    "previous_mentions": "Yesterday's Mentions",
    "pct_change": "% Change",
}
display_df = display_df.rename(columns=column_rename)

# Create two tabs for different views
tab1, tab2 = st.tabs(["📊 Table View", "📈 Visualization"])

with tab1:
    create_subheader("Ticker Mention Rankings")

    # Style the dataframe with color-coded changes
    if "% Change" in display_df.columns:
        # Convert % Change back to numeric for styling
        numeric_df = display_df.copy()
        numeric_df["% Change"] = df["pct_change"]

        styled_df = style_dataframe(numeric_df, highlight_col="% Change")

        # Replace the numeric column with formatted string for display
        numeric_df["% Change"] = display_df["% Change"]

        st.dataframe(
            numeric_df.style.apply(
                lambda x: ["background-color: #1a1d29; color: #fafafa" for _ in x],
                axis=1,
            )
            .set_properties(**{"text-align": "center", "padding": "10px"})
            .set_table_styles(
                [
                    {
                        "selector": "thead th",
                        "props": [
                            ("background-color", "#00d4aa"),
                            ("color", "#0e1117"),
                            ("font-weight", "bold"),
                            ("text-align", "center"),
                            ("padding", "12px"),
                            ("font-size", "14px"),
                        ],
                    },
                    {
                        "selector": "tbody td",
                        "props": [
                            ("border", "1px solid #2a2e3a"),
                            ("font-size", "13px"),
                        ],
                    },
                ]
            )
            .applymap(
                lambda val: (
                    "color: #00d4aa; font-weight: bold"
                    if isinstance(val, str) and "+" in val
                    else (
                        "color: #ef5350; font-weight: bold"
                        if isinstance(val, str) and "-" in val
                        else ""
                    )
                ),
                subset=["% Change"],
            ),
            use_container_width=True,
            height=600,
        )
    else:
        st.dataframe(display_df, use_container_width=True, height=600)

    st.caption(
        f"📅 Showing top {len(df)} tickers from the latest WSB daily discussion thread"
    )

with tab2:
    create_subheader("Mention Trend Comparison")

    # Create bar chart comparing today vs yesterday
    fig = go.Figure()

    # Sort by today's mentions for better visualization
    chart_df = df.sort_values("todays_mentions", ascending=False).head(15)

    fig.add_trace(
        go.Bar(
            name="Today's Mentions",
            x=chart_df["ticker"],
            y=chart_df["todays_mentions"],
            marker_color="#00d4aa",
            text=chart_df["todays_mentions"],
            textposition="outside",
        )
    )

    fig.add_trace(
        go.Bar(
            name="Yesterday's Mentions",
            x=chart_df["ticker"],
            y=chart_df["previous_mentions"],
            marker_color="#ffa726",
            text=chart_df["previous_mentions"],
            textposition="outside",
        )
    )

    fig.update_layout(
        title="Top 15 Tickers: Today vs Yesterday",
        xaxis_title="Ticker",
        yaxis_title="Number of Mentions",
        barmode="group",
        height=500,
        template="plotly_dark",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#1a1d29",
        font=dict(color="#fafafa"),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Percent change chart
    if "pct_change" in df.columns:
        create_subheader("Biggest Movers")

        # Get biggest gainers and losers
        change_df = df.dropna(subset=["pct_change"]).sort_values(
            "pct_change", ascending=False
        )

        fig2 = go.Figure()

        colors = [
            "#00d4aa" if x >= 0 else "#ef5350" for x in change_df["pct_change"].head(15)
        ]

        fig2.add_trace(
            go.Bar(
                x=change_df["ticker"].head(15),
                y=change_df["pct_change"].head(15),
                marker_color=colors,
                text=[f"{x:+.1f}%" for x in change_df["pct_change"].head(15)],
                textposition="outside",
            )
        )

        fig2.update_layout(
            title="Top 15 Tickers by % Change in Mentions",
            xaxis_title="Ticker",
            yaxis_title="% Change",
            height=500,
            template="plotly_dark",
            paper_bgcolor="#0e1117",
            plot_bgcolor="#1a1d29",
            font=dict(color="#fafafa"),
            showlegend=False,
        )

        fig2.add_hline(y=0, line_dash="dash", line_color="#a0a0a0", opacity=0.5)

        st.plotly_chart(fig2, use_container_width=True)

# Sidebar information
st.sidebar.markdown("### 📊 About This Dashboard")
st.sidebar.info(
    """
    This dashboard tracks ticker mentions from the r/WallStreetBets daily discussion thread.
    
    **Data Updates:** Every 5 minutes
    
    **Metrics Explained:**
    - **Today's Mentions:** Count of ticker mentions in the current thread
    - **Yesterday's Mentions:** Count from the previous thread
    - **% Change:** Percentage change in mention frequency
    """
)

st.sidebar.markdown("### 🔍 Quick Stats")
st.sidebar.metric("Data Points", len(df))
st.sidebar.metric("Last Updated", "Live")
