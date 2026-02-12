"""
S3 data fetching utilities for Streamlit dashboard.

Handles fetching JSON data from S3 with intelligent caching based on
the last_updated timestamp in metadata.
"""

import logging
import os
from typing import Dict
import time
from datetime import datetime, timezone

import streamlit as st

import requests

API_URL = os.environ["API_URL"]

logger = logging.getLogger(__name__)


def get_json(endpoint: str) -> Dict:
    url = API_URL + endpoint
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = requests.get(url=url)
            if not response.ok:
                logger.info(
                    f"error making API request {response.status_code}: {response.text}"
                )
                time.sleep(2**attempt)
            else:
                return response.json()
        except:
            logger.exception("error getting data from API")

    return {"data": []}


@st.fragment(run_every="30s")
def live_utc_clock():
    now = datetime.now(timezone.utc)
    st.caption(f"**UTC:** {now.strftime('%H:%M')}")
