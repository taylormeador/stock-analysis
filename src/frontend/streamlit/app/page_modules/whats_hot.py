import logging

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from styles import apply_custom_css, colors, format_large_number, format_percentage
from utils import get_json, live_clock
from components.topic_sentiment import (
    create_multi_snapshot_chart,
)

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

    # Create styled dataframe with red/green coloring
    def color_percentage(val):
        """Color positive values green, negative values red"""
        if isinstance(val, str) and "%" in val:
            # Remove % and + signs to get numeric value
            num_val = float(val.replace("%", "").replace("+", ""))
            if num_val > 0:
                return f"color: {colors.bright_green}"
            elif num_val < 0:
                return "color: #FF4444"  # Red
            else:
                return f"color: {colors.text_gray}"
        return ""

    styled_df = display_df.style.applymap(
        color_percentage,
        subset=["Day Change", "Year Change", "Count Change %"],
    ).format({"Price": "${:.2f}"})

    st.dataframe(
        styled_df,
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

    # Topic Clusters Table
    topics = snapshots[0]
    topics["avg_score"] = topics["avg_score"].round(2)
    cols = {
        "count": "Count",
        "avg_score": "Avg Score",
        "max_score": "Max Score",
        "llm_theme": "LLM Theme",
        "llm_sentiment": "Sentiment",
        "llm_confidence": "Confidence",
        "top_tickers": "top_tickers",
        "llm_insight": "llm_insight",
        "generated_at": "generated_at",
        "representative_docs": "representative_docs",
    }
    display_topics = topics.rename(columns=cols)
    display_topics = display_topics[cols.values()]
    col_config = {
        "Count": st.column_config.Column(
            width=5,
            help="Number of comments in the cluster",
        ),
        "Avg Score": st.column_config.Column(width=1),
        "Max Score": st.column_config.Column(width=1),
        "LLM Theme": st.column_config.Column(width=800),
        "LLM Sentiment": st.column_config.Column(width=1),
        "LLM Confidence": st.column_config.Column(width=1),
        "llm_insight": None,
        "top_tickers": None,
        "representative_docs": None,
        "generated_at": None,
    }

    @st.dialog("Topic Details")
    def show_topic_details(topic_row):
        st.subheader(topic_row["LLM Theme"])
        col1, col2 = st.columns(2)
        with col1:
            st.write(topic_row.top_tickers)

        with col2:
            st.write(topic_row.representative_docs)
            # for doc in topic_row.representative_docs:
            #     st.write(doc)

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Sentiment", topic_row["Sentiment"])
        with col2:
            st.metric("Confidence", f"{topic_row['Confidence']:.2f}")

        st.write(topic_row["llm_insight"])

        st.divider()

        st.write("**Generated At:**", topic_row["generated_at"])

    @st.fragment
    def topic_table():
        event = st.dataframe(
            display_topics,
            width="stretch",
            height="content",
            column_config=col_config,
            on_select="rerun",
            selection_mode="single-row",
        )

        # Show dialog when row is selected
        if event.selection.rows:
            selected_idx = event.selection.rows[0]
            show_topic_details(display_topics.iloc[selected_idx])

    topic_table()

    st.caption(
        f"Showing **top {len(display_topics)} topics** from the latest WSB daily discussion thread"
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
