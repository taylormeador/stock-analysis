import streamlit as st

# Define the pages
home_page = st.Page("pages/home.py", title="Home", icon=":material/home:")
charts_page = st.Page(
    "pages/charts.py",
    title="Charts",
    icon=":material/show_chart:",
)
status_page = st.Page(
    "pages/status.py", title="ETL Status", icon=":material/database_upload:"
)

# Set up navigation
pg = st.navigation([home_page, charts_page, status_page])

# Run the selected page
pg.run()
