import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from styles import Colors, apply_custom_css
from utils import get_json

apply_custom_css()
colors = Colors()

_SPX_LEVEL = 5_582.0
_STRIKES = list(range(4_000, 7_100, 100))
_EXPIRIES_DTE = [2, 7, 14, 21, 30, 45, 60, 90, 180]
_TRADING_TIMES = [
    "09:30", "10:00", "10:30", "11:00", "11:30", "12:00",
    "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00",
]


# ── Parametric IV model (used for the historical replay animation) ─────────────

def _vol_shift_for_time(time_str: str) -> float:
    """U-shaped intraday vol: +2.5% at open/close, near 0% at noon."""
    hour, minute = map(int, time_str.split(":"))
    t = hour + minute / 60.0
    return 0.025 * math.cos(math.pi * (t - 9.5) / 6.5)


def _iv_surface(seed: int = 0, vol_shift: float = 0.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    iv = np.zeros((len(_EXPIRIES_DTE), len(_STRIKES)))
    for i, dte in enumerate(_EXPIRIES_DTE):
        base = 0.14 + 0.08 * math.exp(-dte / 30) + vol_shift
        for j, K in enumerate(_STRIKES):
            lm = math.log(K / _SPX_LEVEL)
            iv[i, j] = base * (1 - 0.15 * lm + 0.12 * lm**2)
    iv += rng.normal(0, 0.003, iv.shape)
    return np.clip(iv, 0.02, 1.5)


def _surface_frames() -> list[go.Frame]:
    return [
        go.Frame(
            data=[go.Surface(
                x=_STRIKES,
                y=_EXPIRIES_DTE,
                z=_iv_surface(seed=i, vol_shift=_vol_shift_for_time(t)) * 100,
                colorscale="RdYlGn_r",
                colorbar=dict(title="IV %", tickfont=dict(color=colors.text_gray)),
                hovertemplate="Strike: %{x}<br>DTE: %{y}<br>IV: %{z:.1f}%<extra></extra>",
                cmin=10, cmax=30,
            )],
            name=t,
        )
        for i, t in enumerate(_TRADING_TIMES)
    ]


def _heatmap_frames() -> list[go.Frame]:
    return [
        go.Frame(
            data=[go.Heatmap(
                x=_STRIKES,
                y=[f"{d}D" for d in _EXPIRIES_DTE],
                z=_iv_surface(seed=i, vol_shift=_vol_shift_for_time(t)) * 100,
                colorscale="RdYlGn_r",
                colorbar=dict(title="IV %", tickfont=dict(color=colors.text_gray)),
                hovertemplate="Strike: %{x}<br>Expiry: %{y}<br>IV: %{z:.1f}%<extra></extra>",
                zmin=10, zmax=30,
            )],
            name=t,
        )
        for i, t in enumerate(_TRADING_TIMES)
    ]


def _animation_controls() -> tuple[list, list]:
    slider_steps = [
        dict(
            method="animate",
            args=[[t], {"mode": "immediate", "frame": {"duration": 0, "redraw": True}}],
            label=t,
        )
        for t in _TRADING_TIMES
    ]
    sliders = [dict(
        active=0,
        currentvalue=dict(
            prefix="Market time: ",
            visible=True,
            font=dict(color=colors.text_gray, size=13),
        ),
        pad=dict(b=10, t=55),
        steps=slider_steps,
        bgcolor="#161b22",
        font=dict(color=colors.text_gray),
        bordercolor="#374151",
    )]
    updatemenus = [dict(
        type="buttons",
        showactive=False,
        y=0,
        x=0.5,
        xanchor="center",
        yanchor="top",
        buttons=[
            dict(
                label="▶",
                method="animate",
                args=[None, {"frame": {"duration": 700, "redraw": True}, "fromcurrent": True}],
            ),
            dict(
                label="⏸",
                method="animate",
                args=[[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}],
            ),
        ],
        bgcolor="#161b22",
        font=dict(color=colors.text_gray),
        bordercolor="#374151",
    )]
    return sliders, updatemenus


# ── Fallback mock helpers (when pipeline is not running) ──────────────────────

def _mock_metrics() -> dict:
    rng = np.random.default_rng()
    return {
        "tick_rate_target": 0, "ticks_generated": 0, "ticks_processed": 0,
        "lag": 0, "iv_queue_depth": 0, "surface_queue_depth": 0,
        "bsm_p50_us": round(rng.uniform(6, 10), 1),
        "bsm_p99_us": round(rng.uniform(35, 55), 1),
        "bsm_p999_us": round(rng.uniform(90, 160), 1),
        "pipeline_p50_us": round(rng.uniform(160, 240), 1),
        "pipeline_p99_us": round(rng.uniform(700, 950), 1),
        "pipeline_p999_us": round(rng.uniform(1_500, 3_000), 1),
    }


def _mock_anomalies() -> list:
    types = ["Skew inversion", "IV spike", "Calendar spread violation"]
    rng = np.random.default_rng(int(datetime.now(timezone.utc).timestamp()) // 30)
    now = datetime.now(timezone.utc)
    rows = []
    for _ in range(8):
        t = now - timedelta(minutes=int(rng.integers(1, 120)))
        rows.append({
            "time": t.strftime("%H:%M:%S"),
            "type": str(rng.choice(types)),
            "strike": float(rng.choice(_STRIKES)),
            "dte": int(rng.choice(_EXPIRIES_DTE)),
            "value": round(float(rng.uniform(0.01, 0.09)), 4),
            "threshold": round(float(rng.uniform(0.02, 0.05)), 4),
            "detail": "mock",
        })
    return rows


# ── Page ──────────────────────────────────────────────────────────────────────

st.title(":material/candlestick_chart: Options Dashboard")
st.divider()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("SPX", f"{_SPX_LEVEL:,.1f}")
with col2:
    st.metric("Surface", f"{len(_STRIKES) * len(_EXPIRIES_DTE):,} contracts")
with col3:
    st.metric("Strikes", f"{len(_STRIKES)} ({_STRIKES[0]:.0f}–{_STRIKES[-1]:.0f})")
with col4:
    st.metric("Expiries", f"{len(_EXPIRIES_DTE)} ({_EXPIRIES_DTE[0]}–{_EXPIRIES_DTE[-1]} DTE)")

st.divider()

# Live status indicator — small fragment that refreshes without touching the charts
@st.fragment(run_every="5s")
def pipeline_status():
    raw = get_json("/options/vol-surface")
    surface_data = raw.get("data") or {}
    if surface_data:
        ts = surface_data.get("timestamp", "")
        st.caption(f"🟢 Pipeline live · last surface update {ts[11:19]} UTC · "
                   f"Live tab shows real BSM-computed surface")
    else:
        st.caption("🔴 Pipeline offline · start `python streamer/python_pipeline.py` · "
                   f"Replay uses parametric mock data")

pipeline_status()

# Vol surface tabs — no run_every here so the animation slider position is preserved
axis_style = dict(gridcolor="#1f2937", zerolinecolor="#374151")
frames_3d = _surface_frames()
frames_heat = _heatmap_frames()
sliders, updatemenus = _animation_controls()

tab_3d, tab_heat, tab_live = st.tabs([
    ":material/view_in_ar: 3D Replay",
    ":material/grid_on: Heatmap Replay",
    ":material/sensors: Live Surface",
])

with tab_3d:
    fig = go.Figure(data=frames_3d[0].data, frames=frames_3d)
    fig.update_layout(
        scene=dict(
            xaxis=dict(title="Strike", **axis_style),
            yaxis=dict(title="DTE", **axis_style),
            zaxis=dict(title="IV (%)", **axis_style),
            bgcolor="#0d1117",
        ),
        paper_bgcolor="#0d1117",
        font=dict(color=colors.text_gray),
        height=580,
        margin=dict(l=0, r=0, t=10, b=90),
        sliders=sliders,
        updatemenus=updatemenus,
    )
    st.plotly_chart(fig, use_container_width=True)

with tab_heat:
    fig = go.Figure(data=frames_heat[0].data, frames=frames_heat)
    fig.update_layout(
        xaxis_title="Strike",
        yaxis_title="Days to Expiry",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#161b22",
        font=dict(color=colors.text_gray),
        height=480,
        margin=dict(l=0, r=0, t=10, b=90),
        sliders=sliders,
        updatemenus=updatemenus,
    )
    st.plotly_chart(fig, use_container_width=True)

with tab_live:
    st.caption("Current vol surface from the Python pipeline — refreshes every 5s")

    @st.fragment(run_every="5s")
    def live_surface():
        raw = get_json("/options/vol-surface")
        surface_data = raw.get("data") or {}
        if not surface_data:
            st.info("Pipeline not running. Start `python streamer/python_pipeline.py` to see live data.")
            return
        strikes = surface_data["strikes"]
        expiries_dte = surface_data["expiries_dte"]
        iv_grid = np.array(surface_data["iv_grid"]) * 100
        fig = go.Figure(go.Surface(
            x=strikes,
            y=expiries_dte,
            z=iv_grid,
            colorscale="RdYlGn_r",
            colorbar=dict(title="IV %", tickfont=dict(color=colors.text_gray)),
            hovertemplate="Strike: %{x}<br>DTE: %{y}<br>IV: %{z:.1f}%<extra></extra>",
            cmin=10, cmax=30,
        ))
        fig.update_layout(
            scene=dict(
                xaxis=dict(title="Strike", **axis_style),
                yaxis=dict(title="DTE", **axis_style),
                zaxis=dict(title="IV (%)", **axis_style),
                bgcolor="#0d1117",
            ),
            paper_bgcolor="#0d1117",
            font=dict(color=colors.text_gray),
            height=540,
            margin=dict(l=0, r=0, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True, key="live_vol_surface")

    live_surface()

st.divider()


@st.fragment(run_every="5s")
def bottom_panels():
    lat_col, anomaly_col = st.columns([1, 2])

    raw_metrics = get_json("/options/pipeline-metrics")
    m = raw_metrics.get("data") or {}
    live = bool(m)
    if not live:
        m = _mock_metrics()

    with lat_col:
        st.subheader(":material/speed: Pipeline Latency")
        st.caption("Python asyncio baseline" if live else "Mock — pipeline offline")

        if live:
            st.caption("**Throughput**")
            c1, c2 = st.columns(2)
            c1.metric("Target", f"{m['tick_rate_target']:,}/s")
            c2.metric("Lag", f"{m['lag']:,} ticks",
                      delta=None if m["lag"] == 0 else f"{m['lag']:,} behind",
                      delta_color="inverse")
            st.caption("**Queue depths**")
            c3, c4 = st.columns(2)
            c3.metric("IV queue", m["iv_queue_depth"])
            c4.metric("Surface queue", m["surface_queue_depth"])

        st.caption("**BSM inversion**")
        c5, c6, c7 = st.columns(3)
        c5.metric("p50", f"{m['bsm_p50_us']} μs")
        c6.metric("p99", f"{m['bsm_p99_us']} μs")
        c7.metric("p999", f"{m['bsm_p999_us']} μs")

        st.caption("**End-to-end pipeline**")
        c8, c9, c10 = st.columns(3)
        c8.metric("p50", f"{m['pipeline_p50_us']} μs")
        c9.metric("p99", f"{m['pipeline_p99_us']} μs")
        c10.metric("p999", f"{m['pipeline_p999_us']} μs")

    raw_anomalies = get_json("/options/anomalies")
    anomaly_data = raw_anomalies.get("data") or []
    if not anomaly_data:
        anomaly_data = _mock_anomalies()

    with anomaly_col:
        st.subheader(":material/warning: Anomaly Log")
        df = pd.DataFrame(anomaly_data)
        display_cols = ["time", "type", "strike", "dte", "value", "threshold", "detail"]
        df = df[[c for c in display_cols if c in df.columns]]
        df.columns = [c.title() for c in df.columns]
        st.dataframe(df, use_container_width=True, hide_index=True)


bottom_panels()
