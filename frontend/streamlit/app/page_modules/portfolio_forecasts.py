"""
Trend forecast visualization page.

Tab 1 — Signals: summary metrics, colored forecast table, combined bar chart.
Tab 2 — Charts: price + EMA overlay and forecast lines grouped by asset class.
"""

import pandas as pd
import streamlit as st
from components.portfolio_forecasts import (
    ASSET_CLASS_LABELS,
    ASSET_CLASS_ORDER,
    build_chart,
    forecast_bar_chart,
    forecast_table,
    signals_summary,
)
from styles import apply_custom_css
from utils import get_json

apply_custom_css()

st.title(":material/show_chart: Trend Forecasts")
st.divider()

with st.spinner("Loading forecast data..."):
    response = get_json("/portfolio/forecasts/default?lookback_days=365")

if not response.get("data"):
    st.error(":material/error: No forecast data available.")
    st.info("Make sure the forecast pipeline has run.")
    st.stop()

instruments = response["data"].get("instruments", [])

if not instruments:
    st.warning("No active instruments found.")
    st.stop()

tab_signals, tab_charts = st.tabs([
    ":material/dashboard: Signals",
    ":material/candlestick_chart: Charts",
])

# ── TAB 1: SIGNALS ────────────────────────────────────────────────────────────
with tab_signals:
    signals_summary(instruments)
    st.divider()
    forecast_bar_chart(instruments)
    st.divider()
    forecast_table(instruments)

# ── TAB 2: CHARTS ─────────────────────────────────────────────────────────────
with tab_charts:
    lookback_days = st.select_slider(
        "Lookback period",
        options=[30, 60, 90, 180, 252, 365],
        value=180,
        key="charts_lookback",
    )

    if lookback_days != 365:
        with st.spinner("Loading..."):
            chart_response = get_json(f"/portfolio/forecasts/default?lookback_days={lookback_days}")
        chart_instruments = chart_response["data"].get("instruments", []) if chart_response.get("data") else []
    else:
        chart_instruments = instruments

    by_class: dict[str, list] = {}
    for inst in chart_instruments:
        ac = inst.get("asset_class", "other")
        by_class.setdefault(ac, []).append(inst)

    for asset_class in ASSET_CLASS_ORDER:
        group = by_class.get(asset_class, [])
        if not group:
            continue

        label = ASSET_CLASS_LABELS.get(asset_class, asset_class.title())
        st.subheader(f":material/category: {label}")

        cols = st.columns(2)
        for i, instrument in enumerate(group):
            symbol = instrument["symbol"]
            inst_label = instrument["label"]
            prices_raw = instrument.get("prices", [])
            forecasts_raw = instrument.get("forecasts", [])

            with cols[i % 2]:
                if not prices_raw or not forecasts_raw:
                    st.warning(f"No data for {inst_label} ({symbol})")
                    continue

                prices_df = pd.DataFrame(prices_raw)
                prices_df["date"] = pd.to_datetime(prices_df["date"])
                forecasts_df = pd.DataFrame(forecasts_raw)
                forecasts_df["date"] = pd.to_datetime(forecasts_df["date"])

                with st.container(border=True):
                    fig = build_chart(prices_df, forecasts_df, inst_label, height=400)
                    st.plotly_chart(fig, use_container_width=True)

                    with st.expander("Raw data"):
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
