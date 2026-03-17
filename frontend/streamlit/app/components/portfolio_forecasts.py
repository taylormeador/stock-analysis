"""
Portfolio forecast visualization component.

Shows a two-panel chart:
  - Top: price with EMA overlays
  - Bottom: individual forecast lines + combined forecast
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from styles import colors


def build_chart(prices_df: pd.DataFrame, forecasts_df: pd.DataFrame, label: str) -> go.Figure:
    """
    Build a two-panel linked chart for a single instrument.

    prices_df: columns [date, close]
    forecasts_df: columns [date, rule_name, scaled_value]
    """
    rule_names = forecasts_df["rule_name"].unique().tolist()

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.6, 0.4],
        subplot_titles=(f"{label} — Price & EMAs", "Forecast Strength"),
    )

    # ── Panel 1: Price ──────────────────────────────────────────────────
    fig.add_trace(
        go.Scatter(
            x=prices_df["date"],
            y=prices_df["close"],
            name="Price",
            line=dict(color=colors.text_gray, width=1.5),
            hovertemplate="<b>%{x}</b><br>Price: %{y:,.2f}<extra></extra>",
        ),
        row=1, col=1,
    )

    # Overlay EMAs for each rule's fast/slow spans
    # Use a larger palette so each span gets a unique color
    ema_palette = [
        "#00FF41",  # bright green
        "#58A6FF",  # blue
        "#FF9900",  # orange
        "#FF6B9D",  # pink
        "#C5B0D5",  # purple
        "#17BECF",  # teal
    ]
    ema_spans = []

    for rule in rule_names:
        parts = rule.split("_")  # ewmac_8_32 → ['ewmac', '8', '32']
        if len(parts) == 3:
            ema_spans.append((int(parts[1]), int(parts[2]), rule))

    # Collect all unique spans in order: fast1, slow1, fast2, slow2...
    seen_spans = []
    for fast, slow, rule in ema_spans:
        if fast not in seen_spans:
            seen_spans.append(fast)
        if slow not in seen_spans:
            seen_spans.append(slow)

    for idx, span in enumerate(seen_spans):
        ema = prices_df["close"].ewm(span=span, adjust=False).mean()
        fig.add_trace(
            go.Scatter(
                x=prices_df["date"],
                y=ema,
                name=f"EMA {span}",
                line=dict(
                    color=ema_palette[idx % len(ema_palette)],
                    width=1,
                    dash="dot",
                ),
                opacity=0.8,
                hovertemplate=f"<b>%{{x}}</b><br>EMA {span}: %{{y:,.2f}}<extra></extra>",
            ),
            row=1, col=1,
        )

    # ── Panel 2: Forecasts ───────────────────────────────────────────────
    # Use a separate palette offset so forecast colors don't clash with EMA colors
    forecast_palette = [
        "#FF9900",  # orange
        "#C5B0D5",  # purple
        "#17BECF",  # teal
        "#FF6B9D",  # pink
    ]

    for idx, rule in enumerate(rule_names):
        rule_df = forecasts_df[forecasts_df["rule_name"] == rule].sort_values("date")
        fig.add_trace(
            go.Scatter(
                x=rule_df["date"],
                y=rule_df["scaled_value"],
                name=rule,
                line=dict(
                    color=forecast_palette[idx % len(forecast_palette)],
                    width=1.2,
                ),
                opacity=0.8,
                hovertemplate="<b>%{x}</b><br>" + rule + ": %{y:.2f}<extra></extra>",
            ),
            row=2, col=1,
        )

    # Combined forecast (mean across rules per date)
    combined = (
        forecasts_df.groupby("date")["scaled_value"]
        .mean()
        .reset_index()
        .sort_values("date")
    )
    fig.add_trace(
        go.Scatter(
            x=combined["date"],
            y=combined["scaled_value"],
            name="Combined",
            line=dict(color="#ffffff", width=2),
            hovertemplate="<b>%{x}</b><br>Combined: %{y:.2f}<extra></extra>",
        ),
        row=2, col=1,
    )

    # Zero line and cap lines on forecast panel
    for y_val, dash, opacity in [(0, "solid", 0.4), (20, "dot", 0.2), (-20, "dot", 0.2)]:
        fig.add_hline(
            y=y_val,
            row=2, col=1,
            line_dash=dash,
            line_color=colors.bright_green,
            opacity=opacity,
        )

    # ── Layout ───────────────────────────────────────────────────────────
    fig.update_layout(
        height=620,
        plot_bgcolor=colors.dark_bg,
        paper_bgcolor=colors.dark_bg,
        font=dict(color=colors.text_gray, family="monospace"),
        hovermode="x unified",
        legend=dict(
            bgcolor="rgba(0,0,0,0.5)",
            bordercolor=colors.bright_green,
            borderwidth=1,
            font=dict(size=11),
        ),
        margin=dict(l=60, r=20, t=40, b=20),
    )

    fig.update_xaxes(
        gridcolor="rgba(0, 255, 65, 0.08)",
        showgrid=True,
    )
    fig.update_yaxes(
        gridcolor="rgba(0, 255, 65, 0.08)",
        showgrid=True,
    )
    fig.update_yaxes(
        title_text="Forecast",
        range=[-22, 22],
        row=2, col=1,
    )

    return fig


def portfolio_summary_table(calculations_df: pd.DataFrame):
    """Render latest portfolio calculations as a table."""
    latest = (
        calculations_df.sort_values("date")
        .groupby("symbol")
        .last()
        .reset_index()
    )

    st.markdown("#### :material/table: Latest Portfolio Positions")

    display = latest[[
        "symbol", "desired_position", "combined_forecast",
        "current_price", "ewma_vol", "date",
    ]].copy()

    display = display.rename(columns={
        "symbol":             "Symbol",
        "desired_position":   "Contracts",
        "combined_forecast":  "Forecast",
        "current_price":      "Price",
        "ewma_vol":           "Daily Vol",
        "date":               "As Of",
    })

    display["Contracts"] = display["Contracts"].astype(int)
    display["Forecast"] = display["Forecast"].round(2)
    display["Price"] = display["Price"].round(2)
    display["Daily Vol"] = display["Daily Vol"].round(4)
    display = display.sort_values("Forecast", ascending=False).reset_index(drop=True)

    st.dataframe(display, use_container_width=True, hide_index=True)