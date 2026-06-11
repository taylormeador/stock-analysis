"""
Macro market overview — price grid, headlines, economic calendar.
Refreshes every minute via st.fragment.
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


def _fmt_price(v: float) -> str:
    if v >= 10_000:
        return f"{v:,.0f}"
    if v >= 1_000:
        return f"{v:,.1f}"
    if v >= 100:
        return f"{v:,.2f}"
    if v >= 10:
        return f"{v:,.3f}"
    return f"{v:,.4f}"


def _relative_time(created: str) -> str:
    """Parse RFC-2822 or ISO datetime string → '2h ago'."""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(created).astimezone(timezone.utc)
    except Exception:
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            return ""
    delta = datetime.now(timezone.utc) - dt
    mins = int(delta.total_seconds() / 60)
    if mins < 60:
        return f"{mins}m ago"
    if mins < 1440:
        return f"{mins // 60}h ago"
    return f"{mins // 1440}d ago"


def _mini_chart(chart_data: list, change_pct: float | None) -> go.Figure | None:
    if not chart_data:
        return None
    times  = [d["t"] for d in chart_data]
    closes = [d["c"] for d in chart_data]
    up = (change_pct or 0) >= 0
    line_color = _GREEN if up else _RED
    fill_color = "rgba(0,200,83,0.08)" if up else "rgba(204,51,0,0.08)"
    fig = go.Figure(go.Scatter(
        x=times, y=closes,
        mode="lines",
        line=dict(color=line_color, width=1.5),
        fill="tozeroy", fillcolor=fill_color,
        hovertemplate="%{x|%b %d %H:%M}<br>%{y:,.4g}<extra></extra>",
    ))
    fig.update_layout(
        height=130,
        plot_bgcolor=colors.dark_bg, paper_bgcolor=colors.dark_bg,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=0, b=0),
    )
    return fig


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
    st.markdown(f"**{sym['label']}** &nbsp; {price_str} &nbsp; {pct_str}")
    fig = _mini_chart(sym.get("chart", []), change)
    if fig:
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.caption("no data")


def _render_prices(symbols: list) -> None:
    i = 0
    groups_seen = []
    while i < len(symbols):
        group = symbols[i]["group"]
        if group not in groups_seen:
            groups_seen.append(group)
            st.markdown(f"##### {group.upper()}")
        row_syms = symbols[i:i+4]
        cols = st.columns(4)
        for col, sym in zip(cols, row_syms):
            with col:
                _render_symbol(sym)
        i += 4


def _render_news(articles: list) -> None:
    st.markdown("##### HEADLINES")
    if not articles:
        st.caption("No headlines available — check BENZINGA_API_KEY.")
        return
    for a in articles:
        age = _relative_time(a.get("created", ""))
        title = a.get("title", "")
        url   = a.get("url", "")
        imp   = a.get("importance", 0)
        # Importance 4-5 gets a visual callout
        prefix = "🔴 " if imp >= 4 else "▸ "
        age_part = f"&nbsp; *{age}*" if age else ""
        if url:
            st.markdown(f"{prefix}[{title}]({url}){age_part}")
        else:
            st.markdown(f"{prefix}**{title}**{age_part}")


def _render_calendar(events: list) -> None:
    st.markdown("##### UPCOMING EVENTS")
    if not events:
        st.caption("No calendar data — check FRED_API_KEY.")
        return
    for ev in events:
        try:
            dt = datetime.strptime(ev["date"], "%Y-%m-%d")
            date_label = dt.strftime("%b %d")
        except Exception:
            date_label = ev["date"]
        event_name = ev["event"]
        category   = ev.get("category", "macro")
        if category == "fomc":
            st.markdown(f"**{date_label}** &nbsp; :orange[{event_name}]")
        else:
            st.markdown(f"**{date_label}** &nbsp; {event_name}")


# ── Page ──────────────────────────────────────────────────────────────────────

st.title(":material/public: Market Overview")


@st.fragment(run_every="1m")
def _overview() -> None:
    prices_resp   = get_json("/market/overview")
    news_resp     = get_json("/market/news")
    calendar_resp = get_json("/market/calendar")

    prices_data = prices_resp.get("data") or {}
    symbols     = prices_data.get("symbols", [])
    fetched_at  = prices_data.get("fetched_at")
    news        = news_resp.get("data") or []
    calendar    = calendar_resp.get("data") or []

    if not symbols:
        st.warning("Market data unavailable — API may be starting up.")
        return

    ts = fetched_at[:19].replace("T", " ") + " UTC" if fetched_at else "unknown"
    st.caption(f"Updated: {ts}")

    _render_prices(symbols)

    st.divider()

    left, right = st.columns([3, 2])
    with left:
        _render_news(news)
    with right:
        _render_calendar(calendar)


_overview()
