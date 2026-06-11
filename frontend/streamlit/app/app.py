import streamlit as st
from styles import apply_custom_css

# Configure page
st.set_page_config(
    page_title="CurveFitter9000",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_custom_css()

# Define the pages
home_page = st.Page(
    page="page_modules/home.py",
    title="Home",
    icon=":material/home:",
)
# whats_hot = st.Page(
#     page="page_modules/whats_hot.py",
#     title="What's Hot",
#     icon=":material/mode_heat:",
# )
backtest_page = st.Page(
    page="page_modules/backtest/backtest_page.py",
    title="Backtest",
    icon=":material/stacked_line_chart:",
)
analysis_page = st.Page(
    page="page_modules/portfolio_forecasts.py",
    title="Analysis",
    icon=":material/stacked_line_chart:",
)
status_page = st.Page(
    page="page_modules/etl_status.py",
    title="ETL Status",
    icon=":material/database_upload:",
)
hacker_page = st.Page(
    page="page_modules/hacker.py",
    title="Terminal",
    icon=":material/terminal:",
)
# options_dashboard = st.Page(
#     page="page_modules/options_dashboard.py",
#     title="Options Dashboard",
#     icon=":material/candlestick_chart:",
# )
account_monitor = st.Page(
    page="page_modules/tastytrade_dashboard.py",
    title="Account Monitor",
    icon=":material/monitoring:",
)

pg = st.navigation([home_page, analysis_page, account_monitor, status_page, hacker_page])
pg.run()
