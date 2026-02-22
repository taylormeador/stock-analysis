"""
Prometheus metrics instrumentation for Celery tasks.

This module provides detailed task-level metrics including:
- Task execution times (histogram)
- Task success/failure counts (counter)
- Currently running tasks (gauge)
- Task-specific labels for granular filtering
"""

import logging
import time
from functools import wraps
from typing import Callable

from celery import signals
from prometheus_client import Counter, Histogram, Gauge, Info

logger = logging.getLogger(__name__)

# Task execution time histogram with buckets appropriate for your tasks
# Adjust buckets based on your actual task durations
TASK_DURATION = Histogram(
    "celery_task_duration_seconds",
    "Time spent executing Celery tasks",
    labelnames=["task_name", "status"],
    buckets=(0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600, 1800, 3600),  # up to 1 hour
)

# Task execution counter
TASK_COUNTER = Counter(
    "celery_task_total",
    "Total number of Celery tasks executed",
    labelnames=["task_name", "status"],
)

# Currently running tasks
TASKS_RUNNING = Gauge(
    "celery_tasks_running",
    "Number of currently executing tasks",
    labelnames=["task_name"],
)

# Task info (last execution time, etc.)
TASK_INFO = Info(
    "celery_task_last_run",
    "Information about last task execution",
    labelnames=["task_name"],
)

# Task retry counter
TASK_RETRIES = Counter(
    "celery_task_retries_total",
    "Total number of task retries",
    labelnames=["task_name", "exception_type"],
)

# Records processed counter (for tasks that process batches)
RECORDS_PROCESSED = Counter(
    "celery_task_records_processed_total",
    "Total number of records processed by tasks",
    labelnames=["task_name", "record_type"],
)


def track_task_metrics(func: Callable) -> Callable:
    """
    Decorator to automatically track Prometheus metrics for a Celery task.

    Usage:
        @app.task
        @track_task_metrics
        def my_task():
            # Your task code
            pass
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        task_name = func.__name__

        # Increment running tasks gauge
        TASKS_RUNNING.labels(task_name=task_name).inc()

        start_time = time.time()
        status = "success"

        try:
            result = func(*args, **kwargs)
            return result

        except Exception as e:
            status = "failed"
            # Track the specific exception type
            TASK_RETRIES.labels(
                task_name=task_name, exception_type=type(e).__name__
            ).inc()
            raise

        finally:
            # Record execution time
            duration = time.time() - start_time
            TASK_DURATION.labels(task_name=task_name, status=status).observe(duration)

            # Increment counter
            TASK_COUNTER.labels(task_name=task_name, status=status).inc()

            # Decrement running tasks gauge
            TASKS_RUNNING.labels(task_name=task_name).dec()

            # Update last run info
            TASK_INFO.labels(task_name=task_name).info(
                {
                    "last_run_time": str(time.time()),
                    "last_duration": str(duration),
                    "last_status": status,
                }
            )

            logger.info(
                f"Task {task_name} completed in {duration:.2f}s with status {status}"
            )

    return wrapper


def track_records_processed(task_name: str, count: int, record_type: str = "default"):
    """
    Manually track the number of records processed by a task.

    Call this from within your task:
        track_records_processed('scrape_reddit', len(comments), 'comments')
    """
    RECORDS_PROCESSED.labels(task_name=task_name, record_type=record_type).inc(count)


# Celery signal handlers for additional metrics
@signals.task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **kwargs):
    """Track task retries via Celery signals."""
    task_name = sender.name if sender else "unknown"
    exception_type = type(reason).__name__ if reason else "unknown"

    TASK_RETRIES.labels(task_name=task_name, exception_type=exception_type).inc()

    logger.warning(f"Task {task_name} ({task_id}) retrying due to {exception_type}")


# Optional: Track task state changes
TASK_STATE_CHANGES = Counter(
    "celery_task_state_changes_total",
    "Total number of task state changes",
    labelnames=["task_name", "state"],
)


@signals.task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Track when tasks start."""
    task_name = sender.name if sender else "unknown"
    TASK_STATE_CHANGES.labels(task_name=task_name, state="started").inc()


@signals.task_success.connect
def task_success_handler(sender=None, **kwargs):
    """Track successful task completion."""
    task_name = sender.name if sender else "unknown"
    TASK_STATE_CHANGES.labels(task_name=task_name, state="success").inc()


@signals.task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """Track task failures."""
    task_name = sender.name if sender else "unknown"
    TASK_STATE_CHANGES.labels(task_name=task_name, state="failed").inc()


# Example usage patterns:

"""
# Pattern 1: Decorator approach (recommended for most tasks)
from app.utils.celery_prometheus_metrics import track_task_metrics

@app.task
@track_task_metrics
def my_scraping_task():
    # Your code here
    results = scrape_data()
    
    # Manually track records processed
    track_records_processed('my_scraping_task', len(results), 'posts')
    
    return results


# Pattern 2: Manual tracking for more control
from app.utils.celery_prometheus_metrics import (
    TASK_DURATION, TASK_COUNTER, TASKS_RUNNING
)

@app.task
def my_complex_task():
    task_name = 'my_complex_task'
    
    TASKS_RUNNING.labels(task_name=task_name).inc()
    start = time.time()
    
    try:
        # Your code
        status = 'success'
    except Exception:
        status = 'failed'
        raise
    finally:
        duration = time.time() - start
        TASK_DURATION.labels(task_name=task_name, status=status).observe(duration)
        TASK_COUNTER.labels(task_name=task_name, status=status).inc()
        TASKS_RUNNING.labels(task_name=task_name).dec()
"""
