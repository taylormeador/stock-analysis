import logging
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from styles import apply_custom_css, format_large_number, format_percentage, colors
from utils import fetch_s3_json

apply_custom_css()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

# Page header
st.title(":material/trending_up: What's Hot")
st.caption("Top trending tickers from r/WallStreetBets daily discussion")
st.divider()

# Fetch data from S3
with st.spinner("Loading data..."):
    json_response = fetch_s3_json("dashboard/whats_hot.json")

if not json_response:
    st.error(
        ":material/error: **No data available**\n\nThe data pipeline may not have run yet."
    )
    st.info(
        ":material/info: **Data Refresh**\n\nThe data is refreshed every 5 minutes from the WSB daily discussion thread."
    )
    st.stop()

# Extract ticker mentions data
ticker_data = json_response.get("data", {}).get("ticker_mentions", [])

if not ticker_data:
    st.warning(":material/warning: No ticker mentions found in the latest data.")
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
        label=":material/forum: Total Mentions",
        value=format_large_number(total_mentions),
    )

with col2:
    st.metric(
        label=":material/star: Top Ticker",
        value=top_ticker,
        delta=f"{top_ticker_mentions} mentions",
    )

with col3:
    st.metric(
        label=":material/show_chart: Tickers Tracked",
        value=len(df),
    )

with col4:
    st.metric(
        label=":material/percent: Avg % Change",
        value=format_percentage(avg_change),
        delta_color="normal" if avg_change >= 0 else "inverse",
    )

st.divider()


# Format columns for better display
display_df = df.copy()
if "pct_change" in display_df.columns:
    display_df["pct_change"] = display_df["pct_change"].apply(
        lambda x: format_percentage(x) if pd.notna(x) else "N/A"
    )

column_rename = {
    "ticker": "Ticker",
    "todays_mentions": "Today's Mentions",
    "previous_mentions": "Yesterday's Mentions",
    "pct_change": "% Change",
}
display_df = display_df.rename(columns=column_rename)

# Create two tabs for different views
tab1, tab2 = st.tabs(
    [":material/table: Table View", ":material/bar_chart: Visualization"]
)

with tab1:
    st.subheader("Ticker Mention Rankings")
    st.dataframe(display_df, width="stretch", height="content")
    st.caption(
        f"Showing **top {len(df)} tickers** from the latest WSB daily discussion thread"
    )

with tab2:
    st.subheader("Mention Trend Comparison")

    # Create bar chart comparing today vs yesterday
    fig = go.Figure()
    chart_df = df.sort_values("todays_mentions", ascending=False).head(15)
    fig.add_trace(
        go.Bar(
            name="Today's Mentions",
            x=chart_df["ticker"],
            y=chart_df["todays_mentions"],
            marker_color="#00C932",
            text=chart_df["todays_mentions"],
            textposition="outside",
            textfont=dict(size=12, color="#00AA2B"),
            opacity=0.9,
        )
    )

    fig.add_trace(
        go.Bar(
            name="Yesterday's Mentions",
            x=chart_df["ticker"],
            y=chart_df["previous_mentions"],
            marker_color="#4B8BCF",
            text=chart_df["previous_mentions"],
            textposition="outside",
            textfont=dict(size=11, color="#1670D1"),
            opacity=0.7,
        )
    )

    fig.update_layout(
        barmode="group",
        plot_bgcolor="#0d1117",
        paper_bgcolor="#0d1117",
        font=dict(color="#C9D1D9", family="monospace"),
        title=dict(
            text="Top 15 Tickers: Today vs Yesterday",
            font=dict(size=18, color="#00FF41"),
        ),
        xaxis=dict(
            title="Ticker",
            gridcolor="rgba(0, 255, 65, 0.1)",
            showgrid=True,
        ),
        yaxis=dict(
            title="Number of Mentions",
            gridcolor="rgba(0, 255, 65, 0.1)",
            showgrid=True,
        ),
        legend=dict(
            bgcolor="rgba(0, 0, 0, 0)",
            bordercolor="#00FF41",
            borderwidth=1,
        ),
        hovermode="x unified",
        height=500,
    )

    st.plotly_chart(fig, width="stretch")

    st.divider()

    # Percentage change waterfall chart
    st.subheader("Mention Growth Analysis")

    # Calculate and sort by percentage change
    change_df = (
        df[df["pct_change"].notna()].sort_values("pct_change", ascending=False).head(10)
    )

    fig2 = go.Figure()

    # Color based on positive/negative change
    colors = ["#00FF41" if val > 0 else "#D18616" for val in change_df["pct_change"]]

    fig2.add_trace(
        go.Bar(
            x=change_df["ticker"],
            y=change_df["pct_change"],
            marker_color=colors,
            text=[format_percentage(val) for val in change_df["pct_change"]],
            textposition="outside",
            textfont=dict(size=12),
            opacity=0.9,
        )
    )

    fig2.update_layout(
        plot_bgcolor="#0d1117",
        paper_bgcolor="#0d1117",
        font=dict(color="#C9D1D9", family="monospace"),
        title=dict(
            text="Top 10 Tickers by % Change", font=dict(size=18, color="#00FF41")
        ),
        xaxis=dict(
            title="Ticker",
            gridcolor="rgba(0, 255, 65, 0.1)",
        ),
        yaxis=dict(
            title="% Change from Yesterday",
            gridcolor="rgba(0, 255, 65, 0.1)",
            showgrid=True,
            zeroline=True,
            zerolinecolor="#58A6FF",
            zerolinewidth=2,
        ),
        showlegend=False,
        hovermode="x",
        height=500,
    )

    st.plotly_chart(fig2, width="stretch")

    # Add insights
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### :material/trending_up: Trending Up")
        trending_up = (
            df[df["pct_change"] > 0].sort_values("pct_change", ascending=False).head(5)
        )
        if not trending_up.empty:
            for _, row in trending_up.iterrows():
                st.markdown(
                    f"**{row['ticker']}** - {format_percentage(row['pct_change'])}"
                )
        else:
            st.caption("No tickers trending up")

    with col2:
        st.markdown("### :material/trending_down: Trending Down")
        trending_down = df[df["pct_change"] < 0].sort_values("pct_change").head(5)
        if not trending_down.empty:
            for _, row in trending_down.iterrows():
                st.markdown(
                    f"**{row['ticker']}** - {format_percentage(row['pct_change'])}"
                )
        else:
            st.caption("No tickers trending down")

# Sidebar info
st.sidebar.markdown("### :material/info: Data Info")
st.sidebar.success("**STATUS:** LIVE DATA")
st.sidebar.caption(
    f"**LAST UPDATE:** Just now\n\n**TOTAL TICKERS:** {len(df)}\n\n**TOTAL MENTIONS:** {format_large_number(total_mentions)}"
)
