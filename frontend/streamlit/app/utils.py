import logging
import os
from typing import Dict
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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


def put_json(endpoint: str, payload: dict) -> Dict:
    url = API_URL + endpoint
    try:
        response = requests.put(url=url, json=payload)
        if response.ok:
            return response.json()
        logger.info(f"PUT error {response.status_code}: {response.text}")
    except:
        logger.exception("error putting to API")
    return {}


def post_json(endpoint: str, payload: dict) -> Dict:
    url = API_URL + endpoint
    try:
        response = requests.post(url=url, json=payload)
        if response.ok:
            return response.json()
        logger.info(f"POST error {response.status_code}: {response.text}")
    except:
        logger.exception("error posting to API")
    return {"data": None}


@st.fragment(run_every="30s")
def live_clock():
    now = datetime.now(timezone.utc)
    st.caption(f"**UTC:** {now.strftime('%H:%M')}")

    now = datetime.now(ZoneInfo("America/New_York"))
    st.caption(f"**Eastern:** {now.strftime('%H:%M')}")

    now = datetime.now(ZoneInfo("America/Denver"))
    st.caption(f"**Denver:** {now.strftime('%H:%M')}")

    now = datetime.now(ZoneInfo("Antarctica/South_Pole"))
    st.caption(f"**South Pole:** {now.strftime('%H:%M')}")
