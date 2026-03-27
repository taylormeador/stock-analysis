"""
Portfolio forecast visualization page.

Tab 1 — Forecasts: price + EMA overlay and forecast strength per instrument.
Tab 2 — Portfolio: run selector, position-over-time chart, latest recs table.
Tab 3 — Run: configure and trigger ad-hoc portfolio calculation runs.
"""

import pandas as pd
import streamlit as st
from datetime import date, timedelta
from components.portfolio_forecasts import (
    build_chart,
    position_over_time_chart,
    latest_positions_table,
)
from styles import apply_custom_css
from utils import get_json, post_json

apply_custom_css()

st.title(":material/show_chart: Portfolio Analysis")
st.divider()

# ── Page-level controls (changing these reruns the full page, acceptable) ─────
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

# ── Data fetched once at page level ───────────────────────────────────────────
runs_response = get_json("/portfolio/runs")
runs = runs_response.get("data", [])

# Use the last run just to get the instruments + forecasts data structure.
# Calculations themselves are fetched inside the portfolio fragment.
_run_for_instruments = runs[-1] if runs else "default"
with st.spinner("Loading portfolio data..."):
    base_response = get_json(
        f"/portfolio/forecasts/{_run_for_instruments}?lookback_days={lookback_days}"
    )

if not base_response.get("data"):
    st.error(":material/error: No portfolio data available.")
    st.info("Make sure the forecast and portfolio calculation pipelines have run.")
    st.stop()

instruments = base_response["data"].get("instruments", [])

if not instruments:
    st.warning("No active instruments found.")
    st.stop()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_forecasts, tab_portfolio, tab_run = st.tabs(
    [
        ":material/candlestick_chart: Forecasts",
        ":material/table_chart: Portfolio",
        ":material/play_arrow: Run",
    ]
)

# ════════════════════════════════════════════════════════════════════════
# TAB 1 — FORECASTS
# (No fragment needed — multiselect here is the only widget and it
#  doesn't cause tab reset since it's scoped to this tab's content)
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

# ════════════════════════════════════════════════════════════════════════
# TAB 2 — PORTFOLIO
# Fragment isolates the run selector + chart so changing the dropdown
# doesn't reset the active tab.
# ════════════════════════════════════════════════════════════════════════
with tab_portfolio:

    @st.fragment
    def portfolio_tab(runs: list[str], lookback_days: int):
        if not runs:
            st.warning("No runs found in portfolio_calculations.")
            return

        selected_run = st.selectbox(
            "Run",
            options=runs,
            index=len(runs) - 1,
            help="Select a named run to visualize.",
        )

        with st.spinner(f"Loading calculations for run '{selected_run}'..."):
            run_response = get_json(
                f"/portfolio/forecasts/{selected_run}?lookback_days={lookback_days}"
            )

        calculations_df = pd.DataFrame(
            run_response.get("data", {}).get("calculations", [])
        )

        if calculations_df.empty:
            st.warning(f"No calculations found for run '{selected_run}'.")
            return

        calculations_df["date"] = pd.to_datetime(calculations_df["date"])

        # Store for sidebar access
        st.session_state["_portfolio_calculations_df"] = calculations_df

        st.divider()
        st.markdown("#### Desired Position Over Time")
        fig = position_over_time_chart(calculations_df)
        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.markdown("#### Latest Recommendations")
        latest_positions_table(calculations_df)

    portfolio_tab(runs, lookback_days)

# ════════════════════════════════════════════════════════════════════════
# TAB 3 — RUN
# Fragment isolates the entire form so changing any input doesn't
# reset the active tab.
# ════════════════════════════════════════════════════════════════════════
with tab_run:

    @st.fragment
    def run_tab(instruments: list[dict]):
        st.markdown("Configure and trigger an ad-hoc portfolio calculation run.")
        st.caption(
            "Results are written to `portfolio_calculations` under the run ID you specify. "
            "Once complete, select it in the **Portfolio** tab."
        )
        st.divider()

        all_labels = [i["label"] for i in instruments]
        symbol_by_label = {i["label"]: i["symbol"] for i in instruments}

        variations_response = get_json("/portfolio/variations")
        all_variations = variations_response.get("data", [])
        variation_names = [v["name"] for v in all_variations]
        variation_descriptions = {v["name"]: v["description"] for v in all_variations}

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Run ID")
            run_id_input = st.text_input(
                "Run ID",
                value="",
                placeholder="e.g. equity_only_2026, metals_test",
                help=(
                    "Human-readable label. Re-using an existing run ID "
                    "overwrites prior results for the same symbol+date."
                ),
            )

            st.markdown("#### Date Range")
            start_date = st.date_input(
                "Start date",
                value=date.today() - timedelta(days=90),
                max_value=date.today(),
            )
            end_date = st.date_input(
                "End date",
                value=date.today(),
                max_value=date.today(),
            )

            st.markdown("#### Capital")
            capital = st.number_input(
                "Capital ($)",
                min_value=1_000,
                max_value=10_000_000,
                value=100_000,
                step=5_000,
            )

            st.markdown("#### Vol Target")
            vol_target_pct = (
                st.slider("Vol target (%)", min_value=5, max_value=40, value=20, step=1)
                / 100.0
            )

        with col2:
            st.markdown("#### Instruments")
            selected_labels = st.multiselect(
                "Instruments",
                options=all_labels,
                default=all_labels,
            )

            st.markdown("#### Variations")
            selected_variations = st.multiselect(
                "Variations",
                options=variation_names,
                default=variation_names,
                format_func=lambda v: f"{v} — {variation_descriptions.get(v, '')}",
            )

        st.divider()

        ready = True
        if not run_id_input.strip():
            st.warning("Enter a run ID before submitting.")
            ready = False
        if start_date > end_date:
            st.error("Start date must be on or before end date.")
            ready = False
        if not selected_variations:
            st.warning("Select at least one variation.")
            ready = False

        days_in_range = (end_date - start_date).days + 1
        n_instruments = len(selected_labels) if selected_labels else len(all_labels)
        st.caption(
            f"**{days_in_range} day(s)** × **{n_instruments} instrument(s)** × "
            f"**{len(selected_variations)} variation(s)** × "
            f"**${capital:,.0f} capital**"
        )

        if st.button(
            ":material/play_arrow: Submit Run", type="primary", disabled=not ready
        ):
            selected_symbols = (
                [symbol_by_label[l] for l in selected_labels]
                if selected_labels
                else None
            )
            payload = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "capital": capital,
                "symbols": selected_symbols,
                "variations": (
                    selected_variations
                    if selected_variations != variation_names
                    else None
                ),
                "vol_target_pct": vol_target_pct,
            }

            with st.spinner("Submitting..."):
                result = post_json(
                    f"/portfolio/calculate/{run_id_input.strip()}", payload
                )

            if result.get("data"):
                st.success(
                    f"Run **{run_id_input.strip()}** submitted. "
                    f"Task ID: `{result['data'].get('task_id')}`\n\n"
                    "Check the ETL Status page for progress."
                )
            else:
                st.error("Submission failed. Check the ETL Status page for details.")

    run_tab(instruments)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### :material/analytics: Portfolio Stats")
    calculations_df = st.session_state.get("_portfolio_calculations_df")
    if calculations_df is not None and not calculations_df.empty:
        latest = (
            calculations_df.sort_values("date").groupby("symbol").last().reset_index()
        )
        st.metric("Long", int((latest["desired_position"] > 0).sum()))
        st.metric("Short", int((latest["desired_position"] < 0).sum()))
        st.metric("Flat", int((latest["desired_position"] == 0).sum()))
        st.divider()
        st.metric("Avg forecast", f"{latest['combined_forecast'].mean():.2f}")
    else:
        st.caption("Select a run in the Portfolio tab.")
