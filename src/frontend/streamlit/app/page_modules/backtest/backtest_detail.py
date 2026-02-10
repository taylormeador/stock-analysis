"""
Detailed backtest results page.

Shows comprehensive performance metrics, equity curves, drawdown analysis,
trade statistics, and links to MLflow experiments.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from styles import apply_custom_css, colors, format_percentage, format_large_number
from utils import get_json
import os

apply_custom_css()

API_URL = os.environ["API_URL"]

# Get backtest ID from session state
if "selected_backtest_id" not in st.session_state:
    st.error("No backtest selected")
    st.stop()

backtest_id = st.session_state["selected_backtest_id"]

# Back button
if st.button(":material/arrow_back: Back to History"):
    del st.session_state["selected_backtest_id"]
    st.switch_page("page_modules/backtest.py")

st.divider()

# Fetch detailed results
with st.spinner("Loading backtest results..."):
    response = get_json(f"/backtests/{backtest_id}/details")

if not response.get("data"):
    st.error(f"Could not load backtest {backtest_id}")
    st.stop()

backtest = response["data"]
metrics = backtest["metrics"]
trades = pd.DataFrame(backtest["trades"])
equity_curve = pd.DataFrame(backtest["equity_curve"])

# Header with key info
st.title(f":material/science: {backtest['strategy_type']} Backtest")
st.caption(
    f"Ticker: {backtest['ticker']} | Period: {backtest['start_date']} to {backtest['end_date']}"
)
st.caption(f"Backtest ID: {backtest_id}")

# Link to MLflow
if backtest.get("mlflow_run_id"):
    mlflow_url = f"http://localhost:5000/#/experiments/{backtest['mlflow_experiment_id']}/runs/{backtest['mlflow_run_id']}"
    st.markdown(f"[:material/open_in_new: View in MLflow]({mlflow_url})")

st.divider()

# Key Metrics Overview
st.subheader(":material/monitoring: Performance Summary")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Total Return",
        format_percentage(metrics["total_return"]),
        delta=f"vs Buy & Hold: {format_percentage(metrics['total_return'] - metrics['buy_hold_return'])}",
    )

with col2:
    st.metric(
        "Sharpe Ratio",
        f"{metrics['sharpe_ratio']:.2f}",
        help="Risk-adjusted return metric",
    )

with col3:
    st.metric(
        "Max Drawdown",
        format_percentage(metrics["max_drawdown"]),
        delta_color="inverse",
    )

with col4:
    st.metric(
        "Win Rate",
        format_percentage(metrics["win_rate"]),
        help="Percentage of profitable trades",
    )

with col5:
    st.metric(
        "Total Trades",
        metrics["total_trades"],
        delta=f"{metrics['avg_trades_per_month']:.1f}/month",
    )

st.divider()

# Equity Curve
st.subheader(":material/show_chart: Equity Curve")

fig_equity = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.05,
    row_heights=[0.7, 0.3],
    subplot_titles=("Portfolio Value", "Drawdown"),
)

# Portfolio value line
fig_equity.add_trace(
    go.Scatter(
        x=equity_curve["date"],
        y=equity_curve["portfolio_value"],
        name="Strategy",
        line=dict(color=colors.bright_green, width=2),
        hovertemplate="<b>%{x}</b><br>Value: $%{y:,.2f}<extra></extra>",
    ),
    row=1,
    col=1,
)

# Buy & hold comparison
fig_equity.add_trace(
    go.Scatter(
        x=equity_curve["date"],
        y=equity_curve["buy_hold_value"],
        name="Buy & Hold",
        line=dict(color=colors.blue, width=2, dash="dash"),
        hovertemplate="<b>%{x}</b><br>Value: $%{y:,.2f}<extra></extra>",
    ),
    row=1,
    col=1,
)

# Drawdown
fig_equity.add_trace(
    go.Scatter(
        x=equity_curve["date"],
        y=equity_curve["drawdown"],
        name="Drawdown",
        fill="tozeroy",
        line=dict(color=colors.orange, width=1),
        hovertemplate="<b>%{x}</b><br>Drawdown: %{y:.2%}<extra></extra>",
    ),
    row=2,
    col=1,
)

fig_equity.update_layout(
    plot_bgcolor=colors.dark_bg,
    paper_bgcolor=colors.dark_bg,
    font=dict(color=colors.text_gray, family="monospace"),
    height=600,
    hovermode="x unified",
    showlegend=True,
    legend=dict(
        bgcolor="rgba(0, 0, 0, 0.5)",
        bordercolor=colors.bright_green,
        borderwidth=1,
    ),
)

fig_equity.update_xaxes(gridcolor="rgba(0, 255, 65, 0.1)")
fig_equity.update_yaxes(gridcolor="rgba(0, 255, 65, 0.1)")

st.plotly_chart(fig_equity, use_container_width=True)

st.divider()

# Detailed Metrics
st.subheader(":material/analytics: Detailed Metrics")

tab1, tab2, tab3 = st.tabs(
    [
        ":material/assessment: Risk Metrics",
        ":material/swap_horiz: Trade Analysis",
        ":material/calendar_month: Period Returns",
    ]
)

with tab1:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Return Metrics")
        metrics_data = {
            "Total Return": format_percentage(metrics["total_return"]),
            "CAGR": format_percentage(metrics["cagr"]),
            "Best Day": format_percentage(metrics["best_day_return"]),
            "Worst Day": format_percentage(metrics["worst_day_return"]),
            "Avg Daily Return": format_percentage(metrics["avg_daily_return"]),
            "Volatility (Annual)": format_percentage(metrics["volatility"]),
        }
        for label, value in metrics_data.items():
            col_a, col_b = st.columns([2, 1])
            col_a.markdown(f"**{label}**")
            col_b.markdown(f"`{value}`")

    with col2:
        st.markdown("#### Risk Metrics")
        risk_data = {
            "Max Drawdown": format_percentage(metrics["max_drawdown"]),
            "Avg Drawdown": format_percentage(metrics["avg_drawdown"]),
            "Max Drawdown Duration": f"{metrics['max_drawdown_days']} days",
            "Sharpe Ratio": f"{metrics['sharpe_ratio']:.2f}",
            "Sortino Ratio": f"{metrics['sortino_ratio']:.2f}",
            "Calmar Ratio": f"{metrics['calmar_ratio']:.2f}",
        }
        for label, value in risk_data.items():
            col_a, col_b = st.columns([2, 1])
            col_a.markdown(f"**{label}**")
            col_b.markdown(f"`{value}`")

with tab2:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Trade Statistics")
        trade_stats = {
            "Total Trades": metrics["total_trades"],
            "Winning Trades": metrics["winning_trades"],
            "Losing Trades": metrics["losing_trades"],
            "Win Rate": format_percentage(metrics["win_rate"]),
            "Avg Win": format_percentage(metrics["avg_win"]),
            "Avg Loss": format_percentage(metrics["avg_loss"]),
            "Best Trade": format_percentage(metrics["best_trade"]),
            "Worst Trade": format_percentage(metrics["worst_trade"]),
        }
        for label, value in trade_stats.items():
            col_a, col_b = st.columns([2, 1])
            col_a.markdown(f"**{label}**")
            col_b.markdown(f"`{value}`")

    with col2:
        st.markdown("#### Position Metrics")
        position_stats = {
            "Avg Days Held": f"{metrics['avg_holding_days']:.1f}",
            "Longest Trade": f"{metrics['longest_trade_days']} days",
            "Shortest Trade": f"{metrics['shortest_trade_days']} days",
            "Profit Factor": f"{metrics['profit_factor']:.2f}",
            "Expectancy": format_percentage(metrics["expectancy"]),
        }
        for label, value in position_stats.items():
            col_a, col_b = st.columns([2, 1])
            col_a.markdown(f"**{label}**")
            col_b.markdown(f"`{value}`")

    # Trade list
    st.divider()
    st.markdown("#### Recent Trades")

    # Format trades dataframe for display
    display_trades = trades.copy()
    display_trades["entry_date"] = pd.to_datetime(
        display_trades["entry_date"]
    ).dt.strftime("%Y-%m-%d")
    display_trades["exit_date"] = pd.to_datetime(
        display_trades["exit_date"]
    ).dt.strftime("%Y-%m-%d")
    display_trades["return_pct"] = display_trades["return_pct"].apply(
        lambda x: format_percentage(x)
    )
    display_trades["profit_loss"] = display_trades["profit_loss"].apply(
        lambda x: f"${x:,.2f}"
    )

    st.dataframe(
        display_trades[
            [
                "entry_date",
                "exit_date",
                "entry_price",
                "exit_price",
                "return_pct",
                "profit_loss",
                "holding_days",
            ]
        ].head(20),
        use_container_width=True,
    )

with tab3:
    # Monthly returns heatmap
    st.markdown("#### Monthly Returns Heatmap")

    # Calculate monthly returns
    equity_curve["date"] = pd.to_datetime(equity_curve["date"])
    equity_curve.set_index("date", inplace=True)
    monthly_returns = equity_curve["portfolio_value"].resample("M").last().pct_change()

    # Create pivot table for heatmap
    monthly_returns_df = pd.DataFrame(
        {
            "year": monthly_returns.index.year,
            "month": monthly_returns.index.month,
            "return": monthly_returns.values,
        }
    )

    pivot = monthly_returns_df.pivot(index="year", columns="month", values="return")

    fig_heatmap = go.Figure(
        data=go.Heatmap(
            z=pivot.values * 100,  # Convert to percentage
            x=[
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ],
            y=pivot.index,
            colorscale=[
                [0, colors.orange],
                [0.5, colors.dark_bg],
                [1, colors.bright_green],
            ],
            zmid=0,
            text=pivot.values * 100,
            texttemplate="%{text:.1f}%",
            textfont={"size": 10},
            hovertemplate="<b>%{y} %{x}</b><br>Return: %{z:.2f}%<extra></extra>",
        )
    )

    fig_heatmap.update_layout(
        plot_bgcolor=colors.dark_bg,
        paper_bgcolor=colors.dark_bg,
        font=dict(color=colors.text_gray, family="monospace"),
        height=400,
    )

    st.plotly_chart(fig_heatmap, use_container_width=True)

st.divider()

# Strategy Parameters Used
st.subheader(":material/settings: Strategy Configuration")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Strategy Parameters")
    for key, value in backtest["strategy_params"].items():
        st.text(f"{key}: {value}")

with col2:
    st.markdown("#### Advanced Settings")
    for key, value in backtest["advanced_params"].items():
        st.text(f"{key}: {value}")

st.divider()

# Download Options
st.subheader(":material/download: Export Results")

col1, col2, col3 = st.columns(3)

with col1:
    csv_data = trades.to_csv(index=False)
    st.download_button(
        label="Download Trades (CSV)",
        data=csv_data,
        file_name=f"backtest_{backtest_id}_trades.csv",
        mime="text/csv",
    )

with col2:
    equity_csv = equity_curve.to_csv()
    st.download_button(
        label="Download Equity Curve (CSV)",
        data=equity_csv,
        file_name=f"backtest_{backtest_id}_equity.csv",
        mime="text/csv",
    )

with col3:
    import json

    config_json = json.dumps(
        {
            "strategy_params": backtest["strategy_params"],
            "advanced_params": backtest["advanced_params"],
            "ticker": backtest["ticker"],
            "start_date": backtest["start_date"],
            "end_date": backtest["end_date"],
        },
        indent=2,
    )

    st.download_button(
        label="Download Config (JSON)",
        data=config_json,
        file_name=f"backtest_{backtest_id}_config.json",
        mime="application/json",
    )
