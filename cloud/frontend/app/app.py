import streamlit as st
from styles import apply_custom_css

# Configure page
st.set_page_config(
    page_title="Stock Analysis Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply custom CSS
apply_custom_css()

# Define the pages
home_page = st.Page("pages/home.py", title="Home", icon=":material/home:")
charts_page = st.Page(
    "pages/charts.py",
    title="What's Hot",
    icon=":material/show_chart:",
)
status_page = st.Page(
    "pages/status.py", title="ETL Status", icon=":material/database_upload:"
)

# Set up navigation
pg = st.navigation([home_page, charts_page, status_page])

# Run the selected page
pg.run()
