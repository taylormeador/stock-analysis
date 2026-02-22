"""
Prometheus metrics HTTP server for Celery workers.

This starts a simple HTTP server on port 9090 (configurable) that exposes
Prometheus metrics for scraping. The server runs in a background thread
so it doesn't interfere with Celery task processing.
"""

import logging
import os
from threading import Thread

from prometheus_client import start_http_server, REGISTRY

logger = logging.getLogger(__name__)


METRICS_PORT = int(os.environ["CELERY_METRICS_PORT"])


def start_metrics_server():
    """
    Start the Prometheus metrics HTTP server.

    This should be called when the Celery worker starts up.
    The server runs in a daemon thread so it shuts down with the worker.
    """
    try:
        # Start HTTP server on specified port
        # This is non-blocking - runs in background thread
        start_http_server(METRICS_PORT, registry=REGISTRY)
        logger.info(f"Prometheus metrics server started on port {METRICS_PORT}")
        logger.info(f"Metrics available at http://localhost:{METRICS_PORT}/metrics")

    except OSError as e:
        if "Address already in use" in str(e):
            logger.warning(
                f"Metrics server port {METRICS_PORT} already in use. "
                "This is expected if running multiple workers. Only one worker "
                "will expose metrics on this port."
            )
        else:
            logger.error(f"Failed to start metrics server: {e}")
            raise


# Alternative: Start in a separate thread with more control
def start_metrics_server_thread():
    """
    Start metrics server in a controlled daemon thread.
    Use this if you need more control over the server lifecycle.
    """

    def _start_server():
        try:
            start_http_server(METRICS_PORT, registry=REGISTRY)
            logger.info(f"Metrics server running on port {METRICS_PORT}")
        except Exception as e:
            logger.error(f"Metrics server error: {e}")

    thread = Thread(target=_start_server, daemon=True, name="PrometheusMetricsServer")
    thread.start()
    logger.info("Metrics server thread started")


# Celery worker initialization
# Add this to your celery config or main.py:
"""
from celery import signals
from app.utils.celery_metrics_server import start_metrics_server

@signals.worker_ready.connect
def start_prometheus_server(**kwargs):
    '''Start Prometheus metrics server when worker is ready.'''
    start_metrics_server()
"""
