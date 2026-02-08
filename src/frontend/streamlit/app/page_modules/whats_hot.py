import logging

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from styles import apply_custom_css, colors, format_large_number, format_percentage
from utils import get_json
from components.topic_sentiment import (
    create_multi_snapshot_chart,
)

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

# Fetch data from API
with st.spinner("Loading data..."):
    json_response = get_json("/whats-hot")

if not json_response.get("data"):
    st.error(
        ":material/error: **No data available**\n\nThe data pipeline may not have run yet."
    )
    st.info(
        ":material/info: **Data Refresh**\n\nThe data is refreshed every 5 minutes from the WSB daily discussion thread."
    )
    st.stop()

# Extract data
ticker_data = json_response.get("data", {}).get("ticker_mentions", [])
comments_data = json_response.get("data", {}).get("top_comments", [])
snapshots_data = json_response.get("data", {}).get("snapshots", [])

if not ticker_data or not comments_data or not snapshots_data:
    st.warning(":material/warning: No data found in the latest update.")
    st.stop()

mentions_df = pd.DataFrame(ticker_data)
comments_df = pd.DataFrame(comments_data)

# Calculate summary metrics
total_mentions = (
    mentions_df[["ticker_mentions_1", "ticker_mentions_2", "ticker_mentions_3"]]
    .sum(axis=1)
    .sum()
)
mentions_df = mentions_df.sort_values("ticker_mentions_1", ascending=False)
top_ticker = mentions_df.iloc[0]["ticker"]
top_ticker_mentions = mentions_df.iloc[0]["ticker_mentions_1"]
top_ticker_mentions_delta = (
    top_ticker_mentions - mentions_df.iloc[0]["ticker_mentions_3"]
)
avg_change = mentions_df["mention_pct_change"].mean()

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
        delta=f"{top_ticker_mentions_delta} mentions",
    )

with col3:
    st.metric(
        label=":material/show_chart: Tickers Tracked",
        value=len(mentions_df.index),
    )

with col4:
    st.metric(
        label=":material/percent: Avg % Change",
        value=format_percentage(avg_change),
        delta_color="normal" if avg_change >= 0 else "inverse",
    )

st.divider()


# Format columns for better display
display_df = mentions_df.copy()
for col in ("mention_pct_change", "day_change", "year_change"):
    display_df[col] = display_df[col].apply(lambda x: format_percentage(x))


display_df = display_df.sort_values(["ticker_mentions_1"], ascending=False)
cols = {
    "ticker": "Ticker",
    "price": "Price",
    "day_change": "Day Change",
    "year_change": "Year Change",
    "ticker_mentions_1": "Current Thread Mentions",
    "ticker_mentions_2": "Previous Thread Mentions",
    "ticker_mentions_3": "Thread Before Last Mentions",
    "mention_pct_change": "% Change",
}
display_df = display_df.rename(columns=cols)
display_df = display_df[cols.values()]
display_df.reset_index(inplace=True, drop=True)


column_rename = {
    "body": "Body",
    "score": "Score",
}
comments_df = comments_df[["body", "score"]]
comments_df = comments_df.rename(columns=column_rename)

# Create two tabs for different views
tab1, tab2, tab3 = st.tabs(
    [
        ":material/table: Table View",
        ":material/bar_chart: Ticker Visualization",
        ":material/bar_chart: Topic Visualization",
    ]
)

# TODO add topics table?
with tab1:
    st.subheader("Ticker Mention Rankings")

    st.dataframe(
        display_df,
        width="stretch",
        height="content",
    )

    st.caption(
        f"Showing **top {len(display_df)} tickers** from the latest WSB daily discussion thread"
    )

    st.subheader("Current Top Comments")

    st.dataframe(
        comments_df,
        width="stretch",
        height="content",
    )

    st.caption(
        f"Showing **top {len(comments_df)} comments** from the latest WSB daily discussion thread"
    )

with tab2:
    st.subheader("Mention Trend Comparison")

    # Create bar chart comparing today vs yesterday
    mentions_bar = go.Figure()
    chart_df = mentions_df.sort_values("ticker_mentions_1", ascending=False).head(15)

    mentions_bar.add_trace(
        go.Bar(
            name="Current Thread's Mentions",
            x=chart_df["ticker"],
            y=chart_df["ticker_mentions_1"],
            marker_color=colors.bright_green,
            text=chart_df["ticker_mentions_1"],
            textposition="outside",
            textfont=dict(size=12, color=colors.bright_green),
            opacity=0.9,
        )
    )

    mentions_bar.add_trace(
        go.Bar(
            name="Yesterday's Mentions",
            x=chart_df["ticker"],
            y=chart_df["ticker_mentions_2"],
            marker_color=colors.blue,
            text=chart_df["ticker_mentions_2"],
            textposition="outside",
            textfont=dict(size=11, color=colors.blue),
            opacity=0.7,
        )
    )

    mentions_bar.add_trace(
        go.Bar(
            name="Thread Before Last's Mentions",
            x=chart_df["ticker"],
            y=chart_df["ticker_mentions_3"],
            marker_color=colors.orange,
            text=chart_df["ticker_mentions_3"],
            textposition="outside",
            textfont=dict(size=11, color=colors.orange),
            opacity=0.7,
        )
    )

    mentions_bar.update_layout(
        barmode="group",
        plot_bgcolor=colors.dark_bg,
        paper_bgcolor=colors.dark_bg,
        font=dict(color=colors.text_gray, family="monospace"),
        title=dict(
            text="Top 15 Tickers",
            font=dict(size=18, color=colors.bright_green),
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
            bordercolor=colors.bright_green,
            borderwidth=1,
        ),
        hovermode="x unified",
        height=500,
    )

    st.plotly_chart(mentions_bar, width="stretch")

    st.divider()

    # Percentage change waterfall chart
    st.subheader("Mention Growth Analysis")

    change_df = (
        mentions_df[mentions_df["mention_pct_change"] != 0]
        .sort_values("mention_pct_change", ascending=False)
        .head(15)
    )

    pct_change_bar = go.Figure()

    # Color based on positive/negative change
    bar_colors = [
        colors.bright_green if val > 0 else colors.orange
        for val in change_df["mention_pct_change"]
    ]

    pct_change_bar.add_trace(
        go.Bar(
            x=change_df["ticker"],
            y=change_df["mention_pct_change"],
            marker_color=bar_colors,
            text=[format_percentage(val) for val in change_df["mention_pct_change"]],
            textposition="outside",
            textfont=dict(size=12),
            opacity=0.9,
        )
    )

    pct_change_bar.update_layout(
        plot_bgcolor=colors.dark_bg,
        paper_bgcolor=colors.dark_bg,
        font=dict(color=colors.text_gray, family="monospace"),
        title=dict(
            text="Top 15 Tickers by % Change",
            font=dict(size=18, color=colors.bright_green),
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
            zerolinecolor=colors.blue,
            zerolinewidth=2,
        ),
        showlegend=False,
        hovermode="x",
        height=500,
    )

    st.plotly_chart(pct_change_bar, width="stretch")

    # Add insights
    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("### :material/trending_up: Trending Up")
        trending_up = (
            mentions_df[mentions_df["mention_pct_change"] > 0]
            .sort_values("mention_pct_change", ascending=False)
            .head(5)
        )
        if not trending_up.empty:
            for _, row in trending_up.iterrows():
                st.markdown(
                    f"**{row['ticker']}** {format_percentage(row['mention_pct_change'])}"
                )
        else:
            st.caption("No tickers trending up")

    with col2:
        st.markdown("### :material/trending_down: Trending Down")
        trending_down = (
            mentions_df[mentions_df["mention_pct_change"] < 0]
            .sort_values("mention_pct_change")
            .head(5)
        )
        if not trending_down.empty:
            for _, row in trending_down.iterrows():
                st.markdown(
                    f"**{row['ticker']}** {format_percentage(row['mention_pct_change'])}"
                )
        else:
            st.caption("No tickers trending down")

    with col3:
        st.markdown("### :material/travel: New Arrivals")
        new = mentions_df[mentions_df["ticker_mentions_3"] == 0].head(5)
        if not new.empty:
            for _, row in new.iterrows():
                st.markdown(f"**{row['ticker']}**")
        else:
            st.caption("No tickers added")

    with col4:
        st.markdown("### :material/waving_hand: Irish Goodbye-ers")
        goners = mentions_df[mentions_df["ticker_mentions_1"] == 0].head(5)
        if not goners.empty:
            for _, row in goners.iterrows():
                st.markdown(f"**{row['ticker']}**")
        else:
            st.caption("No tickers left")

with tab3:
    st.subheader("Topic Clusters")
    fig = create_multi_snapshot_chart(snapshots_df)
    st.plotly_chart(fig, width="stretch")


# Sidebar info
st.sidebar.markdown("### :material/info: Data Info")
st.sidebar.success("**STATUS:** TODO - fix this")
st.sidebar.caption(
    f"**LAST UPDATE:** TODO - fix this\n\n**TOTAL TICKERS:** {len(mentions_df)}\n\n**TOTAL MENTIONS:** {format_large_number(total_mentions)}"
)
