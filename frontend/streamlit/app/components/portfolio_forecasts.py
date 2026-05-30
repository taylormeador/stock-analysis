import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from styles import colors

BULLISH_THRESHOLD = 3.0
BEARISH_THRESHOLD = -3.0

ASSET_CLASS_LABELS = {
    "equity_index": "Equities",
    "rates": "Rates",
    "metals": "Metals",
    "crypto": "Crypto",
    "fx": "FX",
}
ASSET_CLASS_ORDER = ["equity_index", "rates", "metals", "crypto", "fx"]


def _current_forecasts(instrument: dict) -> dict[str, float] | None:
    """Return latest scaled_value per rule + combined for one instrument."""
    forecasts_df = pd.DataFrame(instrument.get("forecasts", []))
    if forecasts_df.empty:
        return None
    forecasts_df["date"] = pd.to_datetime(forecasts_df["date"])
    latest = forecasts_df.sort_values("date").groupby("rule_name")["scaled_value"].last()
    combined = latest.mean()
    return {**latest.to_dict(), "combined": combined}


def signals_summary(instruments: list[dict]) -> None:
    values = [
        v["combined"]
        for i in instruments
        if (v := _current_forecasts(i)) is not None
    ]
    if not values:
        st.warning("No forecast data available.")
        return

    bullish = sum(1 for v in values if v > BULLISH_THRESHOLD)
    bearish = sum(1 for v in values if v < BEARISH_THRESHOLD)
    flat = len(values) - bullish - bearish
    avg = sum(values) / len(values)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(":material/trending_up: Bullish", bullish)
    with col2:
        st.metric(":material/trending_down: Bearish", bearish)
    with col3:
        st.metric(":material/trending_flat: Flat", flat)
    with col4:
        st.metric(":material/analytics: Avg Signal", f"{avg:+.1f}")


def forecast_table(instruments: list[dict]) -> None:
    rows = []
    for inst in sorted(
        instruments,
        key=lambda x: (
            ASSET_CLASS_ORDER.index(x["asset_class"])
            if x["asset_class"] in ASSET_CLASS_ORDER
            else 99,
            x["label"],
        ),
    ):
        cf = _current_forecasts(inst)
        if cf is None:
            continue
        row = {"Label": inst["label"], "Sector": ASSET_CLASS_LABELS.get(inst["asset_class"], inst["asset_class"])}
        rule_names = sorted(
            [k for k in cf if k != "combined"],
            key=lambda r: int(r.split("_")[1]) if r.startswith("ewmac_") else r,
        )
        for rule in rule_names:
            fast, slow = rule.split("_")[1], rule.split("_")[2]
            row[f"{fast}/{slow}"] = round(cf[rule], 1)
        row["Combined"] = round(cf["combined"], 1)
        rows.append(row)

    if not rows:
        st.warning("No forecast data.")
        return

    df = pd.DataFrame(rows)
    numeric_cols = [c for c in df.columns if c not in ("Label", "Sector")]

    styled = (
        df.style
        .background_gradient(cmap="RdYlGn", subset=numeric_cols, vmin=-20, vmax=20)
        .format({c: "{:+.1f}" for c in numeric_cols})
        .set_properties(**{"text-align": "center"}, subset=numeric_cols)
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)


def forecast_bar_chart(instruments: list[dict]) -> None:
    rows = []
    for inst in instruments:
        cf = _current_forecasts(inst)
        if cf is None:
            continue
        rows.append({
            "label": inst["label"],
            "asset_class": inst["asset_class"],
            "combined": cf["combined"],
        })

    if not rows:
        return

    df = pd.DataFrame(rows).sort_values("combined")
    bar_colors = [
        colors.bright_green if v >= 0 else "#CC3300"
        for v in df["combined"]
    ]

    fig = go.Figure(go.Bar(
        x=df["combined"],
        y=df["label"],
        orientation="h",
        marker_color=bar_colors,
        text=[f"{v:+.1f}" for v in df["combined"]],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Combined: %{x:.2f}<extra></extra>",
    ))

    fig.add_vline(x=0, line_color=colors.text_gray, line_width=1, opacity=0.5)
    fig.add_vline(x=10, line_dash="dot", line_color=colors.bright_green, line_width=1, opacity=0.2)
    fig.add_vline(x=-10, line_dash="dot", line_color="#CC3300", line_width=1, opacity=0.2)

    fig.update_layout(
        height=max(280, len(df) * 28),
        plot_bgcolor=colors.dark_bg,
        paper_bgcolor=colors.dark_bg,
        font=dict(color=colors.text_gray, family="monospace"),
        xaxis=dict(
            range=[-24, 24],
            gridcolor="rgba(0, 255, 65, 0.08)",
            showgrid=True,
            zeroline=False,
            title="Combined Forecast",
        ),
        yaxis=dict(showgrid=False),
        margin=dict(l=60, r=60, t=10, b=30),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def build_chart(
    prices_df: pd.DataFrame,
    forecasts_df: pd.DataFrame,
    label: str,
    height: int = 460,
) -> go.Figure:
    """Two-panel chart: price + EMAs (top), forecast lines (bottom)."""
    rule_names = sorted(
        forecasts_df["rule_name"].unique().tolist(),
        key=lambda r: int(r.split("_")[1]) if r.startswith("ewmac_") else r,
    )

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.6, 0.4],
        subplot_titles=(f"{label} — Price & EMAs", "Forecast Strength"),
    )

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

    ema_palette = ["#00FF41", "#58A6FF", "#FF9900", "#FF6B9D", "#C5B0D5", "#17BECF"]
    seen_spans = set()
    for rule in rule_names:
        parts = rule.split("_")
        if len(parts) == 3:
            seen_spans.update([int(parts[1]), int(parts[2])])
    seen_spans = sorted(seen_spans)

    for idx, span in enumerate(seen_spans):
        ema = prices_df["close"].ewm(span=span, adjust=False).mean()
        fig.add_trace(
            go.Scatter(
                x=prices_df["date"],
                y=ema,
                name=f"EMA {span}",
                line=dict(color=ema_palette[idx % len(ema_palette)], width=1, dash="dot"),
                opacity=0.8,
                hovertemplate=f"<b>%{{x}}</b><br>EMA {span}: %{{y:,.2f}}<extra></extra>",
            ),
            row=1, col=1,
        )

    forecast_palette = ["#FF9900", "#C5B0D5", "#17BECF", "#FF6B9D"]
    for idx, rule in enumerate(rule_names):
        rule_df = forecasts_df[forecasts_df["rule_name"] == rule].sort_values("date")
        fast, slow = rule.split("_")[1], rule.split("_")[2]
        fig.add_trace(
            go.Scatter(
                x=rule_df["date"],
                y=rule_df["scaled_value"],
                name=f"{fast}/{slow}",
                line=dict(color=forecast_palette[idx % len(forecast_palette)], width=1.2),
                opacity=0.8,
                hovertemplate="<b>%{x}</b><br>" + f"{fast}/{slow}" + ": %{y:.2f}<extra></extra>",
            ),
            row=2, col=1,
        )

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

    for y_val, dash, opacity in [(0, "solid", 0.4), (20, "dot", 0.2), (-20, "dot", 0.2)]:
        fig.add_hline(y=y_val, row=2, col=1, line_dash=dash, line_color=colors.bright_green, opacity=opacity)

    fig.update_layout(
        height=height,
        plot_bgcolor=colors.dark_bg,
        paper_bgcolor=colors.dark_bg,
        font=dict(color=colors.text_gray, family="monospace"),
        hovermode="x unified",
        legend=dict(
            bgcolor="rgba(0,0,0,0.5)",
            bordercolor=colors.bright_green,
            borderwidth=1,
            font=dict(size=10),
            orientation="h",
            y=-0.02,
        ),
        margin=dict(l=60, r=20, t=40, b=20),
    )
    fig.update_xaxes(gridcolor="rgba(0, 255, 65, 0.08)", showgrid=True)
    fig.update_yaxes(gridcolor="rgba(0, 255, 65, 0.08)", showgrid=True)
    fig.update_yaxes(title_text="Forecast", range=[-22, 22], row=2, col=1)
    return fig


def position_over_time_chart(calculations_df: pd.DataFrame) -> go.Figure:
    """Line chart: desired position over time, one line per instrument."""
    fig = go.Figure()
    line_palette = [
        "#00FF41", "#58A6FF", "#FF9900", "#FF6B9D", "#C5B0D5", "#17BECF",
        "#bcbd22", "#9edae5", "#aec7e8", "#ffbb78", "#98df8a", "#ff9896",
    ]
    for idx, symbol in enumerate(sorted(calculations_df["symbol"].unique())):
        sym_df = calculations_df[calculations_df["symbol"] == symbol].sort_values("date")
        fig.add_trace(
            go.Scatter(
                x=sym_df["date"],
                y=sym_df["desired_position"],
                name=symbol,
                mode="lines+markers",
                line=dict(color=line_palette[idx % len(line_palette)], width=1.5),
                marker=dict(size=4),
                hovertemplate=(
                    f"<b>{symbol}</b><br>"
                    "<b>Date:</b> %{x}<br>"
                    "<b>Position:</b> %{y} contracts<extra></extra>"
                ),
            )
        )

    fig.add_hline(y=0, line_dash="solid", line_color=colors.bright_green, opacity=0.3)
    fig.update_layout(
        height=500,
        plot_bgcolor=colors.dark_bg,
        paper_bgcolor=colors.dark_bg,
        font=dict(color=colors.text_gray, family="monospace"),
        hovermode="x unified",
        yaxis_title="Desired Position (contracts)",
        xaxis_title="Date",
        legend=dict(
            bgcolor="rgba(0,0,0,0.5)",
            bordercolor=colors.bright_green,
            borderwidth=1,
            font=dict(size=11),
        ),
        margin=dict(l=60, r=20, t=20, b=40),
    )
    fig.update_xaxes(gridcolor="rgba(0, 255, 65, 0.08)", showgrid=True)
    fig.update_yaxes(gridcolor="rgba(0, 255, 65, 0.08)", showgrid=True)
    return fig


def latest_positions_table(calculations_df: pd.DataFrame) -> None:
    """Most recent day's recommendations as a styled table."""
    latest_date = calculations_df["date"].max()
    latest = (
        calculations_df[calculations_df["date"] == latest_date]
        .copy()
        .sort_values("combined_forecast", ascending=False)
        .reset_index(drop=True)
    )
    display = latest[
        ["symbol", "desired_position", "combined_forecast", "current_price",
         "ewma_vol", "vol_scalar", "date"]
    ].rename(columns={
        "symbol": "Symbol", "desired_position": "Contracts",
        "combined_forecast": "Forecast", "current_price": "Price",
        "ewma_vol": "Daily Vol", "vol_scalar": "Vol Scalar", "date": "As Of",
    })
    display["Contracts"] = display["Contracts"].astype(int)
    display["Forecast"] = display["Forecast"].round(2)
    display["Price"] = display["Price"].round(2)
    display["Daily Vol"] = display["Daily Vol"].round(4)
    display["Vol Scalar"] = display["Vol Scalar"].round(2)
    display["As Of"] = display["As Of"].astype(str)
    st.caption(f"As of **{latest_date if isinstance(latest_date, str) else latest_date.date()}**")
    st.dataframe(display, use_container_width=True, hide_index=True)
