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
        "ticks_received": 0, "ticks_processed": 0,
        "lag": 0, "iv_queue_depth": 0, "surface_queue_depth": 0,
        "bsm_p50_us": round(rng.uniform(6, 10), 1),
        "bsm_p99_us": round(rng.uniform(35, 55), 1),
        "bsm_p999_us": round(rng.uniform(90, 160), 1),
        "anomaly_p50_us": round(rng.uniform(50, 120), 1),
        "anomaly_p99_us": round(rng.uniform(400, 800), 1),
        "anomaly_p999_us": round(rng.uniform(1_000, 2_500), 1),
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

@st.fragment(run_every="5s")
def header_metrics():
    surface_data = (get_json("/options/vol-surface").get("data") or {})
    metrics_data = (get_json("/options/pipeline-metrics").get("data") or {})

    strikes = surface_data.get("strikes") or []
    expiries = surface_data.get("expiries_dte") or []
    spx = surface_data.get("spx_level") or metrics_data.get("spx_level")
    n_contracts = metrics_data.get("n_contracts")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("SPX", f"{spx:,.1f}" if spx else "—")
    with col2:
        st.metric("Surface", f"{n_contracts:,} contracts" if n_contracts else "—")
    with col3:
        if strikes:
            st.metric("Strikes", f"{len(strikes)} ({min(strikes):,.0f}–{max(strikes):,.0f})")
        else:
            st.metric("Strikes", "—")
    with col4:
        if expiries:
            st.metric("Expiries", f"{len(expiries)} ({min(expiries)}–{max(expiries)} DTE)")
        else:
            st.metric("Expiries", "—")

header_metrics()

st.divider()

@st.fragment(run_every="5s")
def pipeline_status():
    raw = get_json("/options/pipeline-metrics")
    m = raw.get("data") or {}
    if m:
        ts_str = m.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str)
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            if age <= 15:
                st.caption(f"🟢 Pipeline live · metrics updated {ts_str[11:19]} UTC")
                return
        except (ValueError, TypeError):
            pass
    st.caption("🔴 Pipeline offline · start `python streamer/benchmark/python_pipeline.py` · "
               "Replay tabs use parametric mock data")

pipeline_status()

axis_style = dict(gridcolor="#1f2937", zerolinecolor="#374151")
frames_3d = _surface_frames()
frames_heat = _heatmap_frames()
sliders, updatemenus = _animation_controls()

tab_live, tab_3d, tab_heat, tab_bench = st.tabs([
    ":material/sensors: Live Surface",
    ":material/view_in_ar: 3D Replay",
    ":material/grid_on: Heatmap Replay",
    ":material/bar_chart: Benchmark Results",
])

with tab_3d:
    st.caption("Parametric intraday IV replay — animates a mock surface through trading hours")
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
    st.caption("Parametric intraday IV replay — heatmap view")
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
    st.caption("BSM-computed vol surface from live ThetaData quotes — refreshes every 5s")

    @st.fragment(run_every="5s")
    def live_surface():
        raw = get_json("/options/vol-surface")
        surface_data = raw.get("data") or {}
        if not surface_data or not surface_data.get("strikes"):
            st.info("Pipeline not running. Start `python streamer/benchmark/python_pipeline.py` to see live data.")
            return
        raw_strikes = np.array(surface_data["strikes"], dtype=float)
        expiries_dte = surface_data["expiries_dte"]
        raw_grid = np.array(surface_data["iv_grid"], dtype=float) * 100
        spx = surface_data.get("spx_level") or raw_strikes[len(raw_strikes) // 2]

        # Clip to SPX ± 25% so sparse wings don't extrapolate into walls
        lo, hi = spx * 0.75, spx * 1.25
        s_min = round(max(raw_strikes.min(), lo) / 25) * 25
        s_max = round(min(raw_strikes.max(), hi) / 25) * 25
        strikes = np.arange(s_min, s_max + 25, 25)

        iv_grid = np.full((len(expiries_dte), len(strikes)), np.nan)
        for i in range(len(expiries_dte)):
            row = raw_grid[i]
            valid = row != 0
            if valid.sum() >= 2:
                valid_strikes = raw_strikes[valid]
                row_lo, row_hi = valid_strikes.min(), valid_strikes.max()
                in_range = (strikes >= row_lo) & (strikes <= row_hi)
                iv_grid[i, in_range] = np.interp(
                    strikes[in_range], valid_strikes, row[valid]
                )

        # Auto-range colorscale from the data (p5–p95) so 0-DTE doesn't dominate
        valid_vals = iv_grid[~np.isnan(iv_grid)]
        cmin = float(np.percentile(valid_vals, 5)) if len(valid_vals) else 10
        cmax = float(np.percentile(valid_vals, 95)) if len(valid_vals) else 60

        fig = go.Figure(go.Surface(
            x=strikes,
            y=expiries_dte,
            z=iv_grid,
            colorscale="RdYlGn_r",
            colorbar=dict(title="IV %", tickfont=dict(color=colors.text_gray)),
            hovertemplate="Strike: %{x}<br>DTE: %{y}<br>IV: %{z:.1f}%<extra></extra>",
            cmin=cmin, cmax=cmax,
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

with tab_bench:
    st.caption("Results from `benchmark_runs` — each row is one `bench.py` run")

    @st.fragment(run_every="30s")
    def benchmark_results():
        raw = get_json("/options/benchmark-runs")
        runs = raw.get("data") or []
        if not runs:
            st.info("No benchmark runs yet. Run `python streamer/benchmark/bench.py --version-tag <tag>`.")
            return

        df = pd.DataFrame(runs)
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
        df["ticks/sec"] = (df["ticks_processed"] / df["duration_s"]).round(0).astype(int)

        display_cols = [
            "created_at", "version_tag", "duration_s", "ticks_processed", "ticks/sec",
            "bsm_p50_us", "bsm_p99_us",
            "anomaly_p50_us", "anomaly_p99_us",
            "pipeline_p50_us", "pipeline_p99_us", "pipeline_p999_us",
        ]
        df = df[[c for c in display_cols if c in df.columns]]
        df.columns = [c.replace("_", " ").title() for c in df.columns]
        st.dataframe(df, use_container_width=True, hide_index=True)

        chart_df = pd.DataFrame(runs)
        chart_df["ticks_per_sec"] = chart_df["ticks_processed"] / chart_df["duration_s"]

        by_version = (
            chart_df.groupby("version_tag", sort=False)
            .agg(
                mean_throughput=("ticks_per_sec", "mean"),
                min_throughput=("ticks_per_sec", "min"),
                max_throughput=("ticks_per_sec", "max"),
                mean_p999=("pipeline_p999_us", "mean"),
                min_p999=("pipeline_p999_us", "min"),
                max_p999=("pipeline_p999_us", "max"),
                n_runs=("ticks_per_sec", "count"),
            )
            .reset_index()
        )

        chart_layout = dict(
            paper_bgcolor="#0d1117",
            plot_bgcolor="#161b22",
            font=dict(color=colors.text_gray),
            height=340,
            margin=dict(l=0, r=0, t=40, b=10),
            xaxis=dict(gridcolor="#1f2937"),
            yaxis=dict(gridcolor="#1f2937"),
        )

        col_a, col_b = st.columns(2)

        with col_a:
            fig = go.Figure(go.Bar(
                x=by_version["version_tag"],
                y=by_version["mean_throughput"].round(0),
                error_y=dict(
                    type="data",
                    symmetric=False,
                    array=(by_version["max_throughput"] - by_version["mean_throughput"]).round(0),
                    arrayminus=(by_version["mean_throughput"] - by_version["min_throughput"]).round(0),
                    color="#6b7280",
                ),
                marker_color="#3b82f6",
                text=by_version["mean_throughput"].apply(lambda v: f"{v:,.0f}"),
                textposition="outside",
                customdata=by_version["n_runs"],
                hovertemplate="%{x}<br>%{y:,.0f} ticks/sec<br>%{customdata} run(s)<extra></extra>",
            ))
            fig.update_layout(title="Throughput (ticks/sec)", yaxis_title="ticks / sec", **chart_layout)
            st.plotly_chart(fig, use_container_width=True, key="bench_throughput")

        with col_b:
            fig = go.Figure(go.Bar(
                x=by_version["version_tag"],
                y=(by_version["mean_p999"] / 1000).round(1),
                error_y=dict(
                    type="data",
                    symmetric=False,
                    array=((by_version["max_p999"] - by_version["mean_p999"]) / 1000).round(1),
                    arrayminus=((by_version["mean_p999"] - by_version["min_p999"]) / 1000).round(1),
                    color="#6b7280",
                ),
                marker_color="#f59e0b",
                text=(by_version["mean_p999"] / 1000).apply(lambda v: f"{v:,.1f}"),
                textposition="outside",
                customdata=by_version["n_runs"],
                hovertemplate="%{x}<br>%{y:,.1f} ms p999<br>%{customdata} run(s)<extra></extra>",
            ))
            fig.update_layout(title="End-to-end p999 latency", yaxis_title="ms", **chart_layout)
            st.plotly_chart(fig, use_container_width=True, key="bench_p999")

    benchmark_results()

st.divider()


def _fmt_lat(us: float) -> str:
    if us >= 1_000_000:
        return f"{us / 1_000_000:.2f}s"
    if us >= 1_000:
        return f"{us / 1_000:.1f}ms"
    return f"{us:.1f}μs"


@st.fragment(run_every="5s")
def bottom_panels():
    raw_metrics = get_json("/options/pipeline-metrics")
    m = raw_metrics.get("data") or {}
    live = bool(m)
    if not live:
        m = _mock_metrics()

    st.subheader(":material/speed: Pipeline Latency")
    st.caption("Python asyncio baseline" if live else "Mock — pipeline offline")

    if live:
        c1, c2, c3 = st.columns(3)
        c1.metric("Lag", f"{m['lag']:,} ticks")
        c2.metric("IV queue", m["iv_queue_depth"])
        c3.metric("Surface queue", m["surface_queue_depth"])

    lat_df = pd.DataFrame([
        {
            "Stage": "BSM inversion",
            "p50": _fmt_lat(m["bsm_p50_us"]),
            "p99": _fmt_lat(m["bsm_p99_us"]),
            "p999": _fmt_lat(m["bsm_p999_us"]),
        },
        {
            "Stage": "Anomaly detection",
            "p50": _fmt_lat(m.get("anomaly_p50_us", 0)),
            "p99": _fmt_lat(m.get("anomaly_p99_us", 0)),
            "p999": _fmt_lat(m.get("anomaly_p999_us", 0)),
        },
        {
            "Stage": "End-to-end",
            "p50": _fmt_lat(m["pipeline_p50_us"]),
            "p99": _fmt_lat(m["pipeline_p99_us"]),
            "p999": _fmt_lat(m["pipeline_p999_us"]),
        },
    ])
    st.dataframe(lat_df, use_container_width=True, hide_index=True)

    st.divider()

    raw_anomalies = get_json("/options/anomalies")
    anomaly_data = raw_anomalies.get("data") or []
    if not anomaly_data:
        anomaly_data = _mock_anomalies()

    st.subheader(":material/warning: Anomaly Log")
    df = pd.DataFrame(anomaly_data)
    display_cols = ["time", "type", "strike", "dte", "value", "threshold", "detail"]
    df = df[[c for c in display_cols if c in df.columns]]
    df.columns = [c.title() for c in df.columns]
    st.dataframe(df, use_container_width=True, hide_index=True)


bottom_panels()
