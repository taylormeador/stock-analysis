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
whats_hot = st.Page(
    page="page_modules/whats_hot.py",
    title="What's Hot",
    icon=":material/show_chart:",
)
status_page = st.Page(
    page="page_modules/status.py",
    title="ETL Status",
    icon=":material/database_upload:",
)
hacker_page = st.Page(
    page="page_modules/hacker.py",
    title="Terminal",
    icon=":material/terminal:",
)

pg = st.navigation([home_page, whats_hot, status_page, hacker_page])
pg.run()
