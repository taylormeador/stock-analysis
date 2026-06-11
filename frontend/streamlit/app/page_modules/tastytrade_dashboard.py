"""
Tastytrade account risk monitoring dashboard.
Password-gated — requires DASHBOARD_PASSWORD env var.
"""
import os
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from styles import apply_custom_css, colors
from utils import get_json

apply_custom_css()

# ── Auth gate ─────────────────────────────────────────────────────────────────

def _check_password() -> bool:
    if st.session_state.get("tt_authenticated"):
        return True

    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.title(":material/lock:")
        pw = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Password")
        if st.button("Login", use_container_width=True):
            expected = os.environ.get("DASHBOARD_PASSWORD", "")
            if pw == expected:
                st.session_state["tt_authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    return False

if not _check_password():
    st.stop()

# ── Constants ─────────────────────────────────────────────────────────────────

CUSHION_FLOOR = 0.35
LEVERAGE_SOFT_CAP = 1.75

_GREEN = colors.bright_green
_RED = "#CC3300"
_ORANGE = colors.orange
_GRAY = colors.text_gray

# ── Helper formatting ─────────────────────────────────────────────────────────

def _dollar(v):
    if v is None:
        return "—"
    return f"${v:,.0f}"

def _pct(v, decimals=1):
    if v is None:
        return "—"
    return f"{v * 100:.{decimals}f}%"

def _ratio(v, decimals=2):
    if v is None:
        return "—"
    return f"{v:.{decimals}f}x"

# ── Chart builders ────────────────────────────────────────────────────────────

def _vol_bar_chart(positions: list[dict], title: str) -> go.Figure:
    rows = [
        {"label": p["underlying_symbol"], "vol": p["vol_contribution"]}
        for p in positions
        if p.get("vol_contribution") is not None
    ]
    if not rows:
        return None

    df = pd.DataFrame(rows).sort_values("vol")
    fig = go.Figure(go.Bar(
        x=df["vol"],
        y=df["label"],
        orientation="h",
        marker_color=_GREEN,
        text=[f"${v:,.0f}" for v in df["vol"]],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Ann. Dollar Vol: $%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=max(220, len(df) * 32 + 60),
        title=dict(text=title, font=dict(size=12, color=_GRAY, family="monospace"), x=0),
        plot_bgcolor=colors.dark_bg,
        paper_bgcolor=colors.dark_bg,
        font=dict(color=_GRAY, family="monospace"),
        xaxis=dict(
            title="Annualized Dollar Vol",
            gridcolor="rgba(0,255,65,0.08)",
            showgrid=True,
            zeroline=False,
            tickprefix="$",
        ),
        yaxis=dict(showgrid=False),
        margin=dict(l=60, r=80, t=40, b=30),
    )
    return fig

# ── Per-account render ────────────────────────────────────────────────────────

def _render_account(acct: dict) -> None:
    acct_num = acct["account_number"]
    atype = acct["account_type"].upper()
    net_liq = acct["net_liq"]
    cash = acct["cash_balance"]

    st.subheader(f":material/account_balance: {atype} — {acct_num}")

    # ── Top metrics row ──
    cols = st.columns(4 if atype == "MARGIN" else 3)

    with cols[0]:
        st.metric("Net Liq", _dollar(net_liq))

    with cols[1]:
        st.metric("Cash Balance", _dollar(cash))

    if atype == "MARGIN":
        cushion = acct.get("cushion_ratio")
        with cols[2]:
            st.metric(
                "Cushion Ratio",
                _pct(cushion),
                delta=f"Floor: {_pct(CUSHION_FLOOR)}",
                delta_color="off",
                help="Maintenance Excess / Net Liq. Floor: 35%.",
            )
        lev = acct.get("leverage_ratio")
        with cols[3]:
            st.metric(
                "Leverage",
                _ratio(lev),
                help=f"Notional delta exposure / Net Liq. Soft cap: {LEVERAGE_SOFT_CAP}x.",
            )
    else:
        bp = acct.get("equity_buying_power")
        with cols[2]:
            st.metric("Buying Power", _dollar(bp))

    # ── Vol bar chart (all positions) ──
    all_positions = acct.get("positions", [])
    fig = _vol_bar_chart(all_positions, "Annualized Dollar Vol by Position")
    if fig:
        st.plotly_chart(fig, use_container_width=True, key=f"vol_{acct_num}")
        total_vol = acct.get("total_vol_contribution")
        vol_pct = acct.get("vol_as_pct_of_account")
        st.markdown(f"**Portfolio vol:** {_dollar(total_vol)} annualized &nbsp;|&nbsp; **% Net Liq:** {_pct(vol_pct)}")
    else:
        st.info("Vol data unavailable — requires delta + vol estimates.")

    # ── Positions table ──
    active_positions = [p for p in all_positions if p.get("is_active")]
    st.markdown("**Active Positions**")
    _render_positions_table(active_positions)

    excluded = [p for p in all_positions if not p.get("is_active")]
    if excluded:
        with st.expander(f"Excluded (buy-and-hold) — {len(excluded)} positions"):
            _render_positions_table(excluded)


def _render_positions_table(positions: list[dict]) -> None:
    if not positions:
        st.caption("No positions.")
        return

    rows = []
    for p in positions:
        itype = p["instrument_type"]
        direction = p["direction"]
        qty_sign = "+" if direction == "Long" else "-"

        parsed_occ = None
        if "Option" in itype:
            m = re.match(r"^([A-Z0-9./]+)\s*(\d{6})([CP])(\d{8})$", p["symbol"].strip())
            if m:
                parsed_occ = {
                    "type": "Put" if m.group(3) == "P" else "Call",
                    "strike": int(m.group(4)) / 1000,
                    "expiry": m.group(2),
                }

        display_type = itype
        if parsed_occ:
            display_type = f"Short {parsed_occ['type']}" if direction == "Short" else f"Long {parsed_occ['type']}"
        elif "Future" in itype:
            display_type = f"{direction} Future"

        rows.append({
            "Symbol": p["underlying_symbol"],
            "Type": display_type,
            "Qty": f"{qty_sign}{p['quantity']:.0f}",
            "Close": f"${p['close_price']:,.2f}" if p.get("close_price") else "—",
            "Delta": f"{p['delta']:+.2f}" if p.get("delta") is not None else "—",
            "Notional": f"${p['notional_value']:,.0f}" if p.get("notional_value") else "—",
            "Vol %": _pct(p.get("vol_pct_used"), decimals=1),
            "Vol $": f"${p['vol_contribution']:,.0f}" if p.get("vol_contribution") is not None else "—",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True, height=(len(df) + 1) * 36 + 4)


# ── Main page with polling fragment ──────────────────────────────────────────

st.title(":material/monitoring: Account Monitor")
st.divider()


@st.fragment(run_every="30s")
def _dashboard() -> None:
    response = get_json("/tastytrade/dashboard")
    data = response.get("data") or {}
    accounts = data.get("accounts", [])
    fetched_at = data.get("fetched_at")

    if not accounts:
        st.warning(
            ":material/sync_problem: No data yet — the Tastytrade worker hasn't run, "
            "or credentials are not configured."
        )
        return

    ts_display = fetched_at[:19].replace("T", " ") + " UTC" if fetched_at else "unknown"
    st.caption(f"Last fetched: {ts_display}")

    for acct in accounts:
        _render_account(acct)
        st.divider()


_dashboard()
