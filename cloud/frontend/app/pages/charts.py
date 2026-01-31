import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
import requests
import os
import logging
import pandas as pd

from utils import fetch_s3_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


logger.info("getting data")

json_response = fetch_s3_json("dashboard/whats_hot.json")
if not json_response:
    logger.info("No data in S3 for key")

df = pd.DataFrame(json_response["data"])  # type: ignore
st.table(df)
