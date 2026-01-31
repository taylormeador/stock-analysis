"""
S3 data fetching utilities for Streamlit dashboard.

Handles fetching JSON data from S3 with intelligent caching based on
the last_updated timestamp in metadata.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict

import requests
import streamlit as st

logger = logging.getLogger(__name__)

# S3 Configuration
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "stock-analysis-data-1993")
S3_REGION = os.getenv("S3_REGION", "us-east-2")
S3_BASE_URL = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com"


def fetch_s3_json(s3_key: str) -> Dict[str, Any] | None:
    """Fetch JSON data from S3."""
    try:
        url = f"{S3_BASE_URL}/{s3_key}"
        response = requests.get(url, timeout=10)
        if not response.ok:
            logger.error(f"Failed to fetch {s3_key}: {response.status_code}")
            return None

        data = response.json()
        logger.info(f"Fetched {s3_key} from S3")
        return data

    except Exception as e:
        logger.error(f"Error fetching {s3_key}: {e}")
        return None
