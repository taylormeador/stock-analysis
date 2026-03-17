from enum import Enum
from datetime import datetime, timezone
import logging
import os
import json

import redis
from sqlalchemy import update, insert

import app.database.db as db
from app.database.models import etl_task_status

logger = logging.getLogger(__name__)

REDIS_URL = os.environ["REDIS_URL"]
redis_client = redis.Redis.from_url(REDIS_URL)

format = "%Y-%m-%d %H:%M:%S"


class Status(Enum):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    RETRYING = "Retrying"
    FAILED = "Failed"
    COMPLETE = "Complete"


class TaskStatusTracker:
    """Conveneience object for tracking status of ETL runs in the db and Redis.

    start_task() should be called after instantiation, in the task function.
    fail_task() should always be called in the except block of the task function, and wherever else applicable.
    """

    def __init__(self, task_id: str, component_name: str, task_description: str):
        self.redis_client = redis_client
        self.task_id = task_id
        self.component_name = component_name
        self.task_description = task_description
        self.redis_key = f"ETLStatusTracker:{self.task_id}"
        self.values = {
            "task_id": task_id,
            "component_name": component_name,
            "task_description": task_description,
        }

    def _persist(self):
        stmt = (
            update(etl_task_status)
            .where(etl_task_status.c.task_id == self.task_id)
            .values(self.values)
        )
        with db.get_connection() as conn:
            conn.execute(stmt)
            conn.commit()

    def update_progress(self, percent_complete: float, persist: bool = True):
        """This is a float 0-1.0 representing % complete."""
        percent_complete = min(percent_complete, 1.0)
        self.values["progress"] = str(percent_complete)

        self.redis_client.set(self.redis_key, json.dumps(self.values), ex=60)
        if persist:
            self._persist()

    def update_status_message(self, message: str):
        self.values["status_message"] = message

        self.redis_client.set(self.redis_key, json.dumps(self.values), ex=60)
        self._persist()

    def update_status(self, status: Status):
        self.values["status"] = status.value
        self._persist()

    def start_task(self):
        self.values["status"] = Status.IN_PROGRESS.value
        self.values["start_time"] = datetime.now(timezone.utc).strftime(format)
        self.values["progress"] = "0.1"
        self.values["status_message"] = "Task started"

        self.redis_client.set(self.redis_key, json.dumps(self.values), ex=60)
        stmt = insert(etl_task_status).values(self.values)
        with db.get_connection() as conn:
            conn.execute(stmt)
            conn.commit()

    def complete_task(self):
        self.values["progress"] = "1"
        self.values["status"] = Status.COMPLETE.value
        self.values["end_time"] = datetime.now(timezone.utc).strftime(format)

        self.redis_client.set(self.redis_key, json.dumps(self.values), ex=60)
        self._persist()

    def fail_task(self, error_message: str | None = None):
        self.values["status"] = Status.FAILED.value
        self.values["end_time"] = datetime.now(timezone.utc).strftime(format)
        if error_message:
            self.values["status_message"] = error_message

        self.redis_client.set(self.redis_key, json.dumps(self.values), ex=60)
        self._persist()
