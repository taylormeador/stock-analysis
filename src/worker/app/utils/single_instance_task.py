import logging
import os

import redis
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
