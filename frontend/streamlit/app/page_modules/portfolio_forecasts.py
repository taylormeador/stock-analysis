"""
Portfolio forecast visualization page.

Tab 1 — Forecasts: price + EMA overlay and forecast strength per instrument.
Tab 2 — Portfolio: batch selector, position-over-time chart, latest recs table.
"""

import pandas as pd
import streamlit as st
from components.portfolio_forecasts import (
    build_chart,
    position_over_time_chart,
    latest_positions_table,
)
from styles import apply_custom_css
from utils import get_json

apply_custom_css()

st.title(":material/show_chart: Portfolio Analysis")
st.divider()

# ── Controls ──────────────────────────────────────────────────────────────────
col1, col2 = st.columns([2, 1])

with col1:
    lookback_days = st.select_slider(
        "Lookback period",
        options=[30, 60, 90, 180, 252, 365],
        value=180,
        help="Number of calendar days to display",
    )

with col2:
    show_all = st.toggle("Show all instruments", value=True)

st.divider()

# ── Initial fetch (no batch_id — gets most recent batch) ─────────────────────
with st.spinner("Loading portfolio data..."):
    response = get_json(f"/portfolio/forecasts?lookback_days={lookback_days}")

if not response.get("data"):
    st.error(":material/error: No portfolio data available.")
    st.info("Make sure the forecast and portfolio calculation pipelines have run.")
    st.stop()

data = response["data"]
instruments = data.get("instruments", [])
batches = data.get("batches", [])

if not instruments:
    st.warning("No active instruments found.")
    st.stop()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_forecasts, tab_portfolio = st.tabs(
    [
        ":material/candlestick_chart: Forecasts",
        ":material/table_chart: Portfolio",
    ]
)

# ════════════════════════════════════════════════════════════════════════
# TAB 1 — FORECASTS
# ════════════════════════════════════════════════════════════════════════
with tab_forecasts:
    if not show_all:
        labels = [i["label"] for i in instruments]
        selected_labels = st.multiselect(
            "Select instruments",
            options=labels,
            default=labels[:3] if len(labels) >= 3 else labels,
        )
        display_instruments = [i for i in instruments if i["label"] in selected_labels]
    else:
        display_instruments = instruments

    for instrument in display_instruments:
        symbol = instrument["symbol"]
        label = instrument["label"]

        prices_raw = instrument.get("prices", [])
        forecasts_raw = instrument.get("forecasts", [])

        if not prices_raw or not forecasts_raw:
            st.warning(f"No data available for {label} ({symbol})")
            continue

        prices_df = pd.DataFrame(prices_raw)
        prices_df["date"] = pd.to_datetime(prices_df["date"])

        forecasts_df = pd.DataFrame(forecasts_raw)
        forecasts_df["date"] = pd.to_datetime(forecasts_df["date"])

        with st.container(border=True):
            st.markdown(f"### {label} `{symbol}`")
            fig = build_chart(prices_df, forecasts_df, label)
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("View raw data"):
                t1, t2 = st.tabs(["Prices", "Forecasts"])
                with t1:
                    st.dataframe(
                        prices_df.sort_values("date", ascending=False).head(30),
                        use_container_width=True,
                    )
                with t2:
                    pivot = forecasts_df.pivot_table(
                        index="date", columns="rule_name", values="scaled_value"
                    ).sort_index(ascending=False)
                    pivot["combined"] = pivot.mean(axis=1)
                    st.dataframe(pivot.head(30), use_container_width=True)

        st.divider()

# ════════════════════════════════════════════════════════════════════════
# TAB 2 — PORTFOLIO
# ════════════════════════════════════════════════════════════════════════
with tab_portfolio:
    # Batch selector — re-fetches calculations for selected batch
    if batches:
        selected_batch = st.selectbox(
            "Batch",
            options=batches,
            index=len(batches) - 1,  # default to last (most recent)
            help="Each batch is a labeled group of portfolio calculation runs.",
        )
    else:
        st.warning("No batches found in portfolio_calculations.")
        st.stop()

    # Re-fetch if a non-default batch was selected
    batch_param = f"&batch_id={selected_batch}" if selected_batch else ""
    with st.spinner(f"Loading calculations for batch '{selected_batch}'..."):
        batch_response = get_json(
            f"/portfolio/forecasts?lookback_days={lookback_days}{batch_param}"
        )

    calculations_df = pd.DataFrame(
        batch_response.get("data", {}).get("calculations", [])
    )

    if calculations_df.empty:
        st.warning(f"No calculations found for batch '{selected_batch}'.")
        st.stop()

    calculations_df["date"] = pd.to_datetime(calculations_df["date"])

    st.divider()

    # Position over time chart
    st.markdown("#### Desired Position Over Time")
    fig = position_over_time_chart(calculations_df)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Latest positions table
    st.markdown("#### Latest Recommendations")
    latest_positions_table(calculations_df)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### :material/analytics: Portfolio Stats")
    if not calculations_df.empty:
        latest = (
            calculations_df.sort_values("date").groupby("symbol").last().reset_index()
        )
        total_long = (latest["desired_position"] > 0).sum()
        total_short = (latest["desired_position"] < 0).sum()
        total_flat = (latest["desired_position"] == 0).sum()

        st.metric("Long positions", total_long)
        st.metric("Short positions", total_short)
        st.metric("Flat", total_flat)

        st.divider()
        avg_forecast = latest["combined_forecast"].mean()
        st.metric(
            "Avg combined forecast",
            f"{avg_forecast:.2f}",
            help="Average across all instruments. +10 = typical bullish conviction.",
        )
