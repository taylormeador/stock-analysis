"""
Backtesting interface for strategy evaluation.

This page allows users to configure and run backtests, monitor progress,
and view historical backtest results.
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from styles import apply_custom_css
from utils import get_json
import requests
import os

apply_custom_css()

API_URL = os.environ["API_URL"]

# Page header
st.title(":material/science: Strategy Backtesting")
st.caption("Test trading strategies against historical data")
st.divider()

# Create tabs for different views
tab1, tab2 = st.tabs(
    [":material/play_arrow: New Backtest", ":material/history: Backtest History"]
)

with tab1:
    st.subheader("Configure Backtest Parameters")

    # Strategy Selection
    st.markdown("### :material/strategy: Strategy Configuration")
    col1, col2 = st.columns(2)

    with col1:
        strategy_type = st.selectbox(
            "Strategy Type",
            options=[
                "RSI Strategy",
                "MACD Crossover",
                "Sentiment + Technical",
                "Custom",
            ],
            help="Select the strategy logic to backtest",
        )

        ticker = st.selectbox(
            "Ticker",
            options=["AAPL", "MSFT", "GOOGL", "TSLA", "SPY", "QQQ"],
            help="Stock ticker to backtest",
        )

    with col2:
        initial_capital = st.number_input(
            "Initial Capital ($)",
            min_value=1000,
            max_value=1000000,
            value=10000,
            step=1000,
            help="Starting portfolio value",
        )

        position_sizing = st.selectbox(
            "Position Sizing",
            options=["Full Portfolio", "Fixed Percentage", "Kelly Criterion"],
            help="How to size positions",
        )

    # Strategy-specific parameters
    st.markdown("### :material/tune: Strategy Parameters")

    if strategy_type == "RSI Strategy":
        col1, col2, col3 = st.columns(3)
        with col1:
            rsi_period = st.number_input(
                "RSI Period", value=14, min_value=5, max_value=50
            )
        with col2:
            buy_threshold = st.slider("Buy Threshold", 0, 50, 30)
        with col3:
            sell_threshold = st.slider("Sell Threshold", 50, 100, 70)

    elif strategy_type == "Sentiment + Technical":
        col1, col2 = st.columns(2)
        with col1:
            sentiment_weight = st.slider("Sentiment Weight", 0.0, 1.0, 0.4, 0.1)
            min_mentions = st.number_input("Min Daily Mentions", value=10, min_value=1)
        with col2:
            technical_indicator = st.selectbox(
                "Technical Indicator", ["RSI", "MACD", "SMA Crossover"]
            )
            require_both = st.checkbox("Require Both Signals", value=True)

    # Date Range
    st.markdown("### :material/calendar_month: Backtest Period")
    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date.today() - timedelta(days=365),
            max_value=date.today(),
            help="Beginning of backtest period",
        )

    with col2:
        end_date = st.date_input(
            "End Date",
            value=date.today(),
            max_value=date.today(),
            help="End of backtest period",
        )

    # Advanced Options
    with st.expander(":material/settings: Advanced Options"):
        col1, col2 = st.columns(2)
        with col1:
            transaction_cost = st.number_input(
                "Transaction Cost (bps)",
                value=5,
                min_value=0,
                max_value=100,
                help="Trading costs in basis points",
            )
            slippage = st.number_input(
                "Slippage (bps)",
                value=2,
                min_value=0,
                max_value=50,
                help="Expected slippage in basis points",
            )
        with col2:
            risk_free_rate = st.number_input(
                "Risk-Free Rate (%)",
                value=4.5,
                min_value=0.0,
                max_value=10.0,
                step=0.1,
                help="For Sharpe ratio calculation",
            )
            max_drawdown_limit = st.number_input(
                "Max Drawdown Limit (%)",
                value=20,
                min_value=5,
                max_value=50,
                help="Stop trading if exceeded",
            )

    # Run Backtest Button
    st.divider()

    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        run_button = st.button(
            ":material/play_arrow: Run Backtest",
            use_container_width=True,
            type="primary",
        )

    if run_button:
        # Validate inputs
        if start_date >= end_date:
            st.error("Start date must be before end date")
        else:
            # Prepare payload
            payload = {
                "strategy_type": strategy_type,
                "ticker": ticker,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "initial_capital": initial_capital,
                "position_sizing": position_sizing,
                "strategy_params": {},
                "advanced_params": {
                    "transaction_cost_bps": transaction_cost,
                    "slippage_bps": slippage,
                    "risk_free_rate": risk_free_rate / 100,
                    "max_drawdown_limit": max_drawdown_limit / 100,
                },
            }

            # Add strategy-specific params
            if strategy_type == "RSI Strategy":
                payload["strategy_params"] = {
                    "rsi_period": rsi_period,
                    "buy_threshold": buy_threshold,
                    "sell_threshold": sell_threshold,
                }
            elif strategy_type == "Sentiment + Technical":
                payload["strategy_params"] = {
                    "sentiment_weight": sentiment_weight,
                    "min_mentions": min_mentions,
                    "technical_indicator": technical_indicator,
                    "require_both": require_both,
                }

            # Submit to API
            with st.spinner("Submitting backtest..."):
                try:
                    response = requests.post(
                        f"{API_URL}/backtests/run", json=payload, timeout=10
                    )

                    if response.ok:
                        result = response.json()
                        backtest_id = result["backtest_id"]
                        st.success(f"Backtest submitted! ID: {backtest_id}")
                        st.info("Switch to 'Backtest History' tab to monitor progress")
                    else:
                        st.error(f"Failed to submit backtest: {response.text}")

                except Exception as e:
                    st.error(f"Error submitting backtest: {str(e)}")

with tab2:
    st.subheader("Backtest History")

    # Fetch backtest history
    with st.spinner("Loading backtest history..."):
        response = get_json("/backtests/history")

    if not response.get("data"):
        st.info(
            "No backtests found. Run your first backtest in the 'New Backtest' tab!"
        )
    else:
        backtests_df = pd.DataFrame(response["data"])

        # Add filters
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.multiselect(
                "Filter by Status",
                options=["Running", "Complete", "Failed"],
                default=["Running", "Complete"],
            )
        with col2:
            strategy_filter = st.multiselect(
                "Filter by Strategy",
                options=backtests_df["strategy_type"].unique().tolist(),
                default=backtests_df["strategy_type"].unique().tolist(),
            )
        with col3:
            sort_by = st.selectbox(
                "Sort By",
                options=[
                    "Submitted (Newest)",
                    "Submitted (Oldest)",
                    "Sharpe Ratio",
                    "Total Return",
                ],
            )

        # Apply filters
        filtered_df = backtests_df[
            (backtests_df["status"].isin(status_filter))
            & (backtests_df["strategy_type"].isin(strategy_filter))
        ]

        # Sort
        if sort_by == "Submitted (Newest)":
            filtered_df = filtered_df.sort_values("submitted_at", ascending=False)
        elif sort_by == "Submitted (Oldest)":
            filtered_df = filtered_df.sort_values("submitted_at", ascending=True)
        elif sort_by == "Sharpe Ratio":
            filtered_df = filtered_df.sort_values("sharpe_ratio", ascending=False)
        elif sort_by == "Total Return":
            filtered_df = filtered_df.sort_values("total_return", ascending=False)

        st.divider()

        # Display backtests as cards
        for _, backtest in filtered_df.iterrows():
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

                with col1:
                    st.markdown(
                        f"### {backtest['strategy_type']} - {backtest['ticker']}"
                    )
                    st.caption(f"ID: {backtest['backtest_id']}")
                    st.caption(
                        f"Period: {backtest['start_date']} to {backtest['end_date']}"
                    )

                with col2:
                    if backtest["status"] == "Running":
                        st.info(f"**Status:** {backtest['status']}")
                        st.progress(backtest.get("progress", 0.0))
                    elif backtest["status"] == "Complete":
                        st.success(f"**Status:** {backtest['status']}")
                    else:
                        st.error(f"**Status:** {backtest['status']}")

                    st.caption(f"Submitted: {backtest['submitted_at']}")

                with col3:
                    if backtest["status"] == "Complete":
                        st.metric("Total Return", f"{backtest['total_return']:.2%}")
                        st.metric("Sharpe Ratio", f"{backtest['sharpe_ratio']:.2f}")
                    else:
                        st.caption("Results pending...")

                with col4:
                    if backtest["status"] == "Complete":
                        if st.button(
                            "View Details", key=f"view_{backtest['backtest_id']}"
                        ):
                            st.session_state["selected_backtest_id"] = backtest[
                                "backtest_id"
                            ]
                            st.rerun()

                st.divider()

# If a backtest is selected, navigate to detail view
if "selected_backtest_id" in st.session_state:
    st.switch_page("page_modules/backtest_detail.py")

# Sidebar stats
st.sidebar.markdown("### :material/analytics: Quick Stats")
if "backtests_df" in locals() and not backtests_df.empty:
    st.sidebar.metric("Total Backtests", len(backtests_df))
    st.sidebar.metric("Running", len(backtests_df[backtests_df["status"] == "Running"]))
    st.sidebar.metric(
        "Completed", len(backtests_df[backtests_df["status"] == "Complete"])
    )
