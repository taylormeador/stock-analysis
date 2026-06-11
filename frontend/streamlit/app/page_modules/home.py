"""
Macro market overview — price grid, headlines, economic calendar.
Refreshes every minute. Cache on data + figures eliminates flicker.
"""
from datetime import datetime, timezone

import plotly.graph_objects as go
import streamlit as st
from styles import apply_custom_css, colors
from utils import get_json

apply_custom_css()

_GREEN = colors.bright_green
_RED = "#CC3300"
_GRAY = colors.text_gray


# ── Formatting ────────────────────────────────────────────────────────────────

def _fmt_price(v: float) -> str:
    if v >= 10_000: return f"{v:,.0f}"
    if v >= 1_000:  return f"{v:,.1f}"
    if v >= 100:    return f"{v:,.2f}"
    if v >= 10:     return f"{v:,.3f}"
    return f"{v:,.4f}"


def _relative_time(created: str) -> str:
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(created).astimezone(timezone.utc)
    except Exception:
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            return ""
    mins = int((datetime.now(timezone.utc) - dt).total_seconds() / 60)
    if mins < 60:   return f"{mins}m ago"
    if mins < 1440: return f"{mins // 60}h ago"
    return f"{mins // 1440}d ago"


# ── Cached data fetchers ──────────────────────────────────────────────────────
# TTLs are set just above the Redis cache TTLs so we always get fresh data
# while keeping fragment re-runs nearly instantaneous (no API round-trips).

@st.cache_data(ttl=58, show_spinner=False)
def _fetch_prices():
    return get_json("/market/overview")

@st.cache_data(ttl=595, show_spinner=False)
def _fetch_news():
    return get_json("/market/news")

@st.cache_data(ttl=3595, show_spinner=False)
def _fetch_calendar():
    return get_json("/market/calendar")


# ── Cached figure builder ─────────────────────────────────────────────────────
# Keyed on immutable inputs so the same chart data never gets rebuilt.

@st.cache_data(show_spinner=False)
def _build_chart(chart_tuple: tuple, change_pct: float | None) -> go.Figure:
    if not chart_tuple:
        return None
    times  = [t for t, _ in chart_tuple]
    closes = [c for _, c in chart_tuple]

    y_min = min(closes)
    y_max = max(closes)
    pad   = (y_max - y_min) * 0.05 if y_max != y_min else abs(y_min) * 0.001

    up         = (change_pct or 0) >= 0
    line_color = _GREEN if up else _RED
    fill_color = "rgba(0,200,83,0.10)" if up else "rgba(204,51,0,0.10)"

    fig = go.Figure()
    # Invisible baseline so fill is anchored to the data range, not y=0
    fig.add_trace(go.Scatter(
        x=times, y=[y_min - pad] * len(times),
        mode="lines", line=dict(width=0, color="rgba(0,0,0,0)"),
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=times, y=closes,
        mode="lines",
        line=dict(color=line_color, width=1.5),
        fill="tonexty", fillcolor=fill_color,
        hovertemplate="%{x|%b %d %H:%M}<br>%{y:,.4g}<extra></extra>",
        showlegend=False,
    ))
    fig.update_layout(
        height=65,
        plot_bgcolor=colors.dark_bg,
        paper_bgcolor=colors.dark_bg,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, range=[y_min - pad, y_max + pad]),
        margin=dict(l=0, r=0, t=0, b=0),
    )
    return fig


# ── Render helpers ────────────────────────────────────────────────────────────

def _render_symbol(sym: dict) -> None:
    price  = sym.get("last_price")
    change = sym.get("change_pct")
    price_str = _fmt_price(price) if price is not None else "—"
    if change is None:
        pct_str = "—"
    elif change >= 0:
        pct_str = f":green[+{change:.2f}%]"
    else:
        pct_str = f":red[{change:.2f}%]"

    st.markdown(f"**{sym['label']}** {price_str} {pct_str}")

    chart_tuple = tuple((d["t"], d["c"]) for d in sym.get("chart", []))
    fig = _build_chart(chart_tuple, change)
    if fig:
        # Stable key per symbol → React updates the chart in-place instead of
        # unmounting/remounting it, which eliminates the flash on refresh.
        key = "mkt_" + sym["symbol"].replace("^", "").replace("=", "").replace("-", "").replace(".", "")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=key)
    else:
        st.caption("—")


def _render_prices(symbols: list) -> None:
    i = 0
    groups_seen = []
    while i < len(symbols):
        group = symbols[i]["group"]
        if group not in groups_seen:
            groups_seen.append(group)
            st.caption(group.upper())
        cols = st.columns(4)
        for col, sym in zip(cols, symbols[i:i+4]):
            with col:
                _render_symbol(sym)
        i += 4


def _render_news(articles: list) -> None:
    st.markdown("**HEADLINES**")
    if not articles:
        st.caption("No headlines — check BENZINGA_API_KEY.")
        return
    col1, col2 = st.columns(2)
    for i, a in enumerate(articles):
        age    = _relative_time(a.get("created", ""))
        title  = a.get("title", "")
        url    = a.get("url", "")
        imp    = a.get("importance", 0)
        prefix  = "🔴 " if imp >= 4 else "▸ "
        age_str = f" *{age}*" if age else ""
        line = f"{prefix}[{title}]({url}){age_str}" if url else f"{prefix}**{title}**{age_str}"
        with (col1 if i % 2 == 0 else col2):
            st.markdown(line)


def _render_calendar(events: list) -> None:
    st.markdown("**UPCOMING EVENTS**")
    if not events:
        st.caption("No calendar data — check FRED_API_KEY.")
        return
    for ev in events:
        try:
            label = datetime.strptime(ev["date"], "%Y-%m-%d").strftime("%b %d")
        except Exception:
            label = ev["date"]
        name = ev["event"]
        category = ev.get("category")
        if category == "fomc":
            st.markdown(f"**{label}** &nbsp; :orange[{name}]")
        elif category == "earnings":
            st.markdown(f"**{label}** &nbsp; :blue[{name}]")
        else:
            st.markdown(f"**{label}** &nbsp; {name}")


# ── Page ──────────────────────────────────────────────────────────────────────

st.title(":material/public: Market Overview")


@st.fragment(run_every="1m")
def _overview() -> None:
    prices_data = (_fetch_prices().get("data") or {})
    symbols     = prices_data.get("symbols", [])
    fetched_at  = prices_data.get("fetched_at")
    news        = _fetch_news().get("data") or []
    calendar    = _fetch_calendar().get("data") or []

    if not symbols:
        st.warning("Market data unavailable — API may be starting up.")
        return

    ts = fetched_at[:19].replace("T", " ") + " UTC" if fetched_at else "unknown"
    st.caption(f"Updated: {ts}")

    chart_col, cal_col = st.columns([5, 1])
    with chart_col:
        _render_prices(symbols)
    with cal_col:
        _render_calendar(calendar)

    st.divider()
    _render_news(news)


_overview()
