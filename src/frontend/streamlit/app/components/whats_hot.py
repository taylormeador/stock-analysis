import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from styles import colors, format_percentage


def ticker_mentions(display_df: pd.DataFrame):
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


def mention_trend_comparison(mentions_df: pd.DataFrame):
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


def current_topics(topics: pd.DataFrame):
    # Topic Clusters Table
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
    display_topics = display_topics.sort_values(by="Count", ascending=False)

    # TODO I might want to use this elsewhere later
    # @st.dialog("Topic Details")
    # def show_topic_details(topic_row):
    #     st.subheader(topic_row["LLM Theme"])
    #     col1, col2 = st.columns(2)
    #     with col1:
    #         st.write(topic_row.top_tickers)

    #     with col2:
    #         st.write(topic_row.representative_docs)

    #     st.divider()

    #     col1, col2 = st.columns(2)
    #     with col1:
    #         st.metric("Sentiment", topic_row["Sentiment"])
    #     with col2:
    #         st.metric("Confidence", f"{topic_row['Confidence']:.2f}")

    #     st.write(topic_row["llm_insight"])

    #     st.divider()

    #     st.write("**Generated At:**", topic_row["generated_at"])

    # @st.fragment
    # def topic_cards():
    #     for idx, (_, row) in enumerate(display_topics.iterrows()):
    #         with st.container(border=True):
    #             col1, col2, col3, col4 = st.columns([8, 1, 1, 1])
    #             with col1:
    #                 st.write(f"**{row['LLM Theme']}**")
    #             with col2:
    #                 st.caption(f"Count: {row['Count']}")
    #                 st.caption(f"Max Score: {int(row['Max Score'])}")
    #             with col3:
    #                 st.caption(f"Sentiment: {row['Sentiment']}")
    #                 st.caption(f"Confidence: {row['Confidence']}")
    #             with col4:
    #                 if st.button("→", key=f"expand_{idx}"):
    #                     show_topic_details(row)

    # topic_cards()

    for idx, (_, row) in enumerate(display_topics.iterrows()):
        with st.container(border=True):
            # Collapsed view
            col1, col2, col3, col4 = st.columns([8, 1, 1, 1])
            with col1:
                st.write(f"**{row['LLM Theme']}**")
            with col2:
                st.caption(f"Count: {row['Count']}")
                st.caption(f"Max Score: {int(row['Max Score'])}")
            with col3:
                st.caption(f"Sentiment: {row['Sentiment']}")
                st.caption(f"Confidence: {row['Confidence']}")
            with col4:
                expand_key = f"expand_{idx}"

            # Use expander inside the container for details
            with st.expander("View Details", expanded=False):
                col1, col2, col3 = st.columns([1, 1, 8])
                with col1:
                    st.metric("Sentiment", row["Sentiment"])
                with col2:
                    st.metric("Confidence", f"{row['Confidence']:.2f}")
                st.write(row["llm_insight"])
                st.divider()

                col1, col2 = st.columns(2)
                with col1:
                    st.write(row.top_tickers)

                with col2:
                    st.write(row.representative_docs)
                st.divider()

                st.write("**Generated At:**", row["generated_at"])

    st.caption(
        f"Showing **top {len(display_topics)} topics** from the latest WSB daily discussion thread"
    )
