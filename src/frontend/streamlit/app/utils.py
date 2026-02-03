"""
S3 data fetching utilities for Streamlit dashboard.

Handles fetching JSON data from S3 with intelligent caching based on
the last_updated timestamp in metadata.
"""

import logging
import os
from typing import Dict
import time

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
