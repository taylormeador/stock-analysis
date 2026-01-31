import json
import logging
import os
from typing import Any, Dict

import boto3
import redis
from botocore.exceptions import ClientError
from celery import Task


logger = logging.getLogger(__name__)


class SingleInstanceTask(Task):
    def __call__(self, *args, **kwargs):
        lock_id = f"{self.name}-lock"
        redis_client = redis.Redis.from_url(os.environ["REDIS_URL"])
        lock_acquired = redis_client.set(lock_id, "locked", ex=300, nx=True)
        if not lock_acquired:
            logger.info(f"Task {self.name} already running, skipping")
            return None

        try:
            return super().__call__(*args, **kwargs)
        finally:
            redis_client.delete(lock_id)


# AWS Configuration
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION", "us-east-2")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# S3 client
s3_client = boto3.client(
    "s3",
    region_name=S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)


def write_to_s3(data: Dict[str, Any], s3_key: str) -> bool:
    """
    Write JSON data to S3.

    Args:
        data: Dictionary to write as JSON
        s3_key: S3 object key (e.g., "dashboard/ticker_data.json")

    Returns:
        True if successful, False otherwise
    """
    try:
        json_str = json.dumps(data)

        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json_str,
            ContentType="application/json",
        )

        logger.info(f"Uploaded to s3://{S3_BUCKET}/{s3_key}")
        return True

    except ClientError as e:
        logger.error(f"Failed to upload to S3: {e}")
        return False
