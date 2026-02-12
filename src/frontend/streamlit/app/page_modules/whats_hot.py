import logging

import components.whats_hot as components
import pandas as pd
import streamlit as st
from components.topic_sentiment import (
    create_multi_snapshot_chart,
)
from styles import apply_custom_css, format_large_number, format_percentage
from utils import get_json, live_clock

apply_custom_css()

logger = logging.getLogger(__name__)

# Page header
st.title(":material/mode_heat: What's Hot")
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
ticker_data = json_response["data"].get("ticker_mentions", [])
comments_data = json_response["data"].get("top_comments", [])
snapshots_data = json_response["data"].get("topic_snapshots", [])
market_data = json_response["data"].get("market_data", [])

if not ticker_data or not comments_data or not snapshots_data:
    st.warning(":material/warning: No data found in the latest update.")
    st.stop()

mentions_df = pd.DataFrame(ticker_data)
comments_df = pd.DataFrame(comments_data)
snapshots = [pd.DataFrame(snapshot) for snapshot in snapshots_data]

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
pct_cols = [
    "day_change",
    "year_change",
    "mention_share_1",
    "mention_share_2",
    "mention_share_3",
]
display_df[pct_cols] = display_df[pct_cols] * 100

for col in ("mention_pct_change", "day_change", "year_change"):
    display_df[col] = display_df[col].apply(lambda x: format_percentage(x))

for col in ("mention_share_1", "mention_share_2", "mention_share_3"):
    display_df[col] = display_df[col].apply(
        lambda x: format_percentage(x, include_sign=False)
    )


display_df = display_df.sort_values(["ticker_mentions_1"], ascending=False)
cols = {
    "ticker": "Ticker",
    "price": "Price",
    "day_change": "Day Change",
    "year_change": "Year Change",
    "ticker_mentions_1": "Current Count",
    "mention_share_1": "Current %",
    "ticker_mentions_2": "Previous Count",
    "mention_share_2": "Previous %",
    "ticker_mentions_3": "Thread Before Last Count",
    "mention_share_3": "Thread Before Last %",
    "mention_pct_change": "Count Change %",
}
display_df = display_df.rename(columns=cols)
display_df = display_df[cols.values()]

int_cols = ["Current Count", "Previous Count", "Thread Before Last Count"]
display_df[int_cols] = display_df[int_cols].astype(int)
display_df.reset_index(inplace=True, drop=True)


column_rename = {
    "body": "Body",
    "score": "Score",
}
comments_df = comments_df[["body", "score"]]
comments_df = comments_df.rename(columns=column_rename)

# Create two tabs for different views
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        ":material/table: Ticker Mentions",
        ":material/table: Top Comments",
        ":material/table: Top Topics",
        ":material/bar_chart: Ticker Visualization",
        ":material/bar_chart: Topic Visualization",
    ]
)

with tab1:
    components.ticker_mentions(display_df)

with tab2:
    st.subheader("Current Top Comments")

    st.dataframe(
        comments_df,
        width="stretch",
        height="content",
    )

    st.caption(
        f"Showing **top {len(comments_df)} comments** from the latest WSB daily discussion thread"
    )

with tab3:
    st.subheader("Current Topics")
    components.current_topics(snapshots[0])


with tab4:
    st.subheader("Mention Trend Comparison")
    components.mention_trend_comparison(mentions_df)

with tab5:
    st.subheader("Topic Clusters")
    fig = create_multi_snapshot_chart(snapshots)
    st.plotly_chart(fig, width="stretch")


# Sidebar info
with st.sidebar:
    st.sidebar.markdown("### :material/schedule: Time")
    live_clock()

    st.markdown("### :material/candlestick_chart: Market Context")

    vix_data = market_data["vix_price"]
    spy_data = market_data["spy_price"]
    qqq_data = market_data["qqq_price"]
    iwm_data = market_data["iwm_price"]
    put_call_ratio = market_data["put_call_ratio"]
    dollar_index = market_data["dollar_index"]

    if vix_data:
        st.sidebar.metric(
            "VIX",
            f"{vix_data['price']:.2f}",
            delta=f"{vix_data['day_change']*100:.2f}%",
        )
    if spy_data:
        st.sidebar.metric(
            "SPY",
            f"${spy_data['price']:.2f}",
            delta=f"{spy_data['day_change']*100:.2f}%",
        )
    if qqq_data:
        st.sidebar.metric(
            "QQQ",
            f"{qqq_data['price']:.2f}",
            delta=f"{qqq_data['day_change']*100:.2f}%",
        )
    if iwm_data:
        st.sidebar.metric(
            "IWM",
            f"{iwm_data['price']:.2f}",
            delta=f"{iwm_data['day_change']*100:.2f}%",
        )
    if put_call_ratio:
        st.sidebar.metric("Put/Call Ratio", f"{put_call_ratio:.2f}")
    if dollar_index:
        st.sidebar.metric("Dollar Index", f"{dollar_index:.2f}")
