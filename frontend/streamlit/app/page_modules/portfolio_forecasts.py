"""
Trend forecast visualization page.

Shows price + EMA overlay and EWMAC forecast strength per instrument.
"""

import pandas as pd
import streamlit as st
from components.portfolio_forecasts import build_chart
from styles import apply_custom_css
from utils import get_json

apply_custom_css()

st.title(":material/show_chart: Trend Forecasts")
st.divider()

col1, col2 = st.columns([2, 1])
with col1:
    lookback_days = st.select_slider(
        "Lookback period",
        options=[30, 60, 90, 180, 252, 365],
        value=180,
    )
with col2:
    show_all = st.toggle("Show all instruments", value=True)

st.divider()

with st.spinner("Loading forecast data..."):
    response = get_json(f"/portfolio/forecasts/default?lookback_days={lookback_days}")

if not response.get("data"):
    st.error(":material/error: No forecast data available.")
    st.info("Make sure the forecast pipeline has run.")
    st.stop()

instruments = response["data"].get("instruments", [])

if not instruments:
    st.warning("No active instruments found.")
    st.stop()

if not show_all:
    labels = [i["label"] for i in instruments]
    selected_labels = st.multiselect(
        "Select instruments",
        options=labels,
        default=labels,
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
        st.warning(f"No data for {label} ({symbol})")
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
