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
CAR_CEILING_MARGIN = 0.80
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

def _donut_chart(labels: list[str], values: list[float], title: str, height: int = 300) -> go.Figure:
    palette = [
        "#2d6a4f", "#1d4e89", "#7b4f2e", "#5c3566", "#2e5a6b",
        "#6b5c2e", "#3d5a3e", "#4a3728", "#2e4057", "#5a3d4a",
    ]
    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker=dict(colors=palette[:len(labels)], line=dict(color=colors.dark_bg, width=2)),
        textinfo="label+percent",
        textfont=dict(size=10, color=_GRAY, family="monospace"),
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(
        height=height,
        title=dict(text=title, font=dict(size=12, color=_GRAY, family="monospace"), x=0.5),
        paper_bgcolor=colors.dark_bg,
        plot_bgcolor=colors.dark_bg,
        font=dict(color=_GRAY, family="monospace"),
        legend=dict(font=dict(size=9), bgcolor="rgba(0,0,0,0)", x=1.0, y=0.5),
        margin=dict(l=10, r=10, t=40, b=10),
        showlegend=False,
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
            delta_str = f"Floor: {_pct(CUSHION_FLOOR)}"
            st.metric(
                "Cushion Ratio",
                _pct(cushion),
                delta=delta_str,
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
        # IRA: show SPAN or buying power instead of cushion
        bp = acct.get("equity_buying_power")
        with cols[2]:
            st.metric("Buying Power", _dollar(bp))

    # ── Capital at risk + vol targeting charts ──
    active_positions = [p for p in acct.get("positions", []) if p.get("is_active")]

    car_labels = [p["underlying_symbol"] for p in active_positions if p.get("capital_at_risk") is not None]
    car_values = [p["capital_at_risk"] for p in active_positions if p.get("capital_at_risk") is not None]

    all_positions = acct.get("positions", [])
    vol_labels = [p["underlying_symbol"] for p in all_positions if p.get("vol_contribution") is not None]
    vol_values = [p["vol_contribution"] for p in all_positions if p.get("vol_contribution") is not None]

    total_car = acct.get("total_capital_at_risk", 0)
    car_ratio = acct.get("capital_at_risk_ratio")
    car_denom = "Cash" if atype == "MARGIN" else "Net Liq"
    car_ceiling = CAR_CEILING_MARGIN if atype == "MARGIN" else None

    chart_cols = st.columns(2)
    with chart_cols[0]:
        if car_labels:
            fig = _donut_chart(car_labels, car_values, f"Capital at Risk by Position")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No active positions with capital at risk data.")
        ratio_str = _pct(car_ratio)
        if car_ratio is not None and car_ceiling is not None and car_ratio > car_ceiling:
            ratio_str = f":red[{ratio_str}]"
        elif car_ratio is not None and car_ceiling is not None and car_ratio > car_ceiling * 0.90:
            ratio_str = f":orange[{ratio_str}]"
        st.markdown(f"**Total:** {_dollar(total_car)} &nbsp;|&nbsp; **{car_denom} %:** {ratio_str}")

    with chart_cols[1]:
        if vol_labels:
            fig = _donut_chart(vol_labels, vol_values, "Vol Contribution by Position")
            st.plotly_chart(fig, use_container_width=True)
            vol_pct = acct.get("vol_as_pct_of_account")
            st.markdown(f"**Portfolio vol %:** {_pct(vol_pct)}")
        else:
            st.info("Greeks not available — vol targeting requires delta + IV from broker.")

    # ── Positions table ──
    st.markdown("**Active Positions**")
    _render_positions_table(acct_num, active_positions)

    excluded = [p for p in acct.get("positions", []) if not p.get("is_active")]
    if excluded:
        with st.expander(f"Excluded (buy-and-hold) — {len(excluded)} positions"):
            _render_positions_table(acct_num, excluded)


def _render_positions_table(acct_num: str, positions: list[dict]) -> None:
    if not positions:
        st.caption("No positions.")
        return

    rows = []
    for p in positions:
        parsed_occ = None
        itype = p["instrument_type"]
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
            display_type = f"Short {parsed_occ['type']}" if p["direction"] == "Short" else f"Long {parsed_occ['type']}"
        elif "Future" in itype:
            display_type = f"{p['direction']} Future"

        rows.append({
            "Symbol": p["underlying_symbol"],
            "Type": display_type,
            "Qty": f"{p['direction']} {p['quantity']:.0f}",
            "Close": f"${p['close_price']:,.2f}" if p.get("close_price") else "—",
            "Delta": f"{p['delta']:.2f}" if p.get("delta") is not None else "—",
            "IV": f"{p['implied_volatility']*100:.1f}%" if p.get("implied_volatility") else "—",
            "Capital at Risk": f"${p['capital_at_risk']:,.0f}" if p.get("capital_at_risk") else "—",
            "Stop Defined": "✓" if p.get("stop_defined") else "✗",
            "Stop Mode": p.get("stop_mode", "—"),
            "_symbol_full": p["symbol"],
        })

    df = pd.DataFrame(rows)
    display_df = df.drop(columns=["_symbol_full"])
    st.dataframe(display_df, use_container_width=True, hide_index=True, height=(len(df) + 1) * 36 + 4)


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
