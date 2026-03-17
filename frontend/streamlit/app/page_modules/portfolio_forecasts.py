"""
Portfolio forecast visualization page.

Shows price + EMA overlay and forecast strength charts
for each active instrument in the portfolio.
"""

import pandas as pd
import streamlit as st
from components.portfolio_forecasts import build_chart
from styles import apply_custom_css
from utils import get_json

apply_custom_css()

st.title(":material/show_chart: Portfolio Forecasts")
st.caption("Price trends, moving averages, and EWMAC forecast strength per instrument")
st.divider()

# ── Controls ──────────────────────────────────────────────────────────────────
col1, col2 = st.columns([2, 1])

with col1:
    lookback_days = st.select_slider(
        "Lookback period",
        options=[30, 60, 90, 180, 252, 365],
        value=180,
        help="Number of trading days to display",
    )

with col2:
    show_all = st.toggle("Show all instruments", value=True)

st.divider()

# ── Data fetch ────────────────────────────────────────────────────────────────
with st.spinner("Loading portfolio data..."):
    response = get_json(f"/portfolio/forecasts?lookback_days={lookback_days}")

if not response.get("data"):
    st.error(":material/error: No portfolio forecast data available.")
    st.info(
        "Make sure the forecast and portfolio calculation pipelines have run. "
        "Check the ETL Status page for details."
    )
    st.stop()

data = response["data"]
instruments = data.get("instruments", [])

if not instruments:
    st.warning("No active instruments found.")
    st.stop()

# Instrument selector if not showing all
if not show_all:
    labels = [i["label"] for i in instruments]
    selected_labels = st.multiselect(
        "Select instruments",
        options=labels,
        default=labels[:3] if len(labels) >= 3 else labels,
    )
    instruments = [i for i in instruments if i["label"] in selected_labels]

# ── Summary metrics ───────────────────────────────────────────────────────────
calculations_df = pd.DataFrame(data.get("calculations", []))
if not calculations_df.empty:
    from components.portfolio_forecasts import portfolio_summary_table
    portfolio_summary_table(calculations_df)
    st.divider()

# ── Per-instrument charts ──────────────────────────────────────────────────────

for instrument in instruments:
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

        # Expandable raw data
        with st.expander("View raw data"):
            tab1, tab2 = st.tabs(["Prices", "Forecasts"])
            with tab1:
                st.dataframe(
                    prices_df.sort_values("date", ascending=False).head(30),
                    use_container_width=True,
                )
            with tab2:
                pivot = forecasts_df.pivot_table(
                    index="date", columns="rule_name", values="scaled_value"
                ).sort_index(ascending=False)
                pivot["combined"] = pivot.mean(axis=1)
                st.dataframe(pivot.head(30), use_container_width=True)

    st.divider()

# Sidebar
with st.sidebar:
    st.markdown("### :material/analytics: Portfolio Stats")
    if not calculations_df.empty:
        latest = (
            calculations_df.sort_values("date")
            .groupby("symbol")
            .last()
            .reset_index()
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