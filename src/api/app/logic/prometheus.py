import requests
import logging
import httpx
from datetime import datetime, timedelta
import asyncio


logger = logging.getLogger(__name__)

PROMETHEUS_URL = "http://10.0.10.127:9090"


async def get_worker_status():
    """Get current worker availability from Prometheus"""
    query = "celery_worker_up"
    response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
    data = response.json()

    # Parse results - returns worker names and their status (1=up, 0=down)
    # Result structure: data["data"]["result"] is list of {metric: {...}, value: [timestamp, value]}

    return data


async def get_task_throughput():
    """Get tasks processed in last hour"""
    query = "sum(increase(celery_task_runtime_seconds_count[1h]))"
    response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
    return response.json()


async def get_prometheus_targets():
    """Get health of all Prometheus scrape targets"""
    response = requests.get(f"{PROMETHEUS_URL}/api/v1/targets")
    targets = response.json()["data"]["activeTargets"]

    # Each target has: scrapeUrl, health (up/down), lastScrape, lastError
    return targets


async def get_worker_status_history():
    """Get worker availability over last 24 hours"""
    query = "celery_worker_up"
    now = datetime.now()
    start = now - timedelta(hours=24)

    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query_range",
        params={
            "query": query,
            "start": start.timestamp(),
            "end": now.timestamp(),
            "step": "5m",  # Data point every 5 minutes
        },
    )
    return response.json()


async def get_tasks_processed_last_24h():
    """How many tasks did each worker complete in last 24h?"""
    query = "sum by (hostname) (increase(celery_task_succeeded_total[24h]))"

    response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
    data = response.json()["data"]

    task_counts = {}
    for result in data["result"]:
        hostname = result["metric"]["hostname"]
        task_count = int(round(float(result["value"][1])))
        task_counts[hostname] = task_count

    return task_counts


async def get_task_failure_rate():
    """What % of tasks are failing?"""
    query = "sum(rate(celery_task_failed_total[24h])) / sum(rate(celery_task_received_total[24h])) * 100"

    response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
    data = response.json()["data"]

    # This will look like:
    # {'status': 'success', 'data': {'resultType': 'vector', 'result': [{'metric': {}, 'value': [1770770873.034, '0.057707230258682796']}]}}
    failure_rate = data["result"][0]["value"][1]
    if failure_rate:
        return round(float(failure_rate), 2)

    return None


async def get_active_workers():
    async with httpx.AsyncClient(timeout=5.0) as client:
        worker_query = "celery_worker_up"
        worker_response = await client.get(
            url=f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": worker_query},
        )
        worker_data = worker_response.json()

    # Count workers that are up (value = 1)
    active_workers = sum(
        1
        for result in worker_data.get("data", {}).get("result", [])
        if float(result["value"][1]) == 1.0
    )

    return active_workers


async def get_queue_depth():
    # Get total queue depth across all queues
    async with httpx.AsyncClient(timeout=5.0) as client:
        queue_query = "sum(celery_queue_length)"
        queue_response = await client.get(
            f"{PROMETHEUS_URL}/api/v1/query", params={"query": queue_query}
        )
        queue_data = queue_response.json()

    queue_depth = 0
    results = queue_data.get("data", {}).get("result", [])
    if results:
        queue_depth = int(float(results[0]["value"][1]))

    return queue_depth


async def get_tasks_per_hour():
    # Get tasks processed in last hour (for "tasks/hour" metric)
    async with httpx.AsyncClient(timeout=5.0) as client:
        throughput_query = "sum(increase(celery_task_succeeded_total[1h]))"
        throughput_response = await client.get(
            f"{PROMETHEUS_URL}/api/v1/query", params={"query": throughput_query}
        )
        throughput_data = throughput_response.json()

    tasks_per_hour = 0
    results = throughput_data.get("data", {}).get("result", [])
    if results:
        tasks_per_hour = int(float(results[0]["value"][1]))

    return tasks_per_hour


async def get_success_rate():
    async with httpx.AsyncClient(timeout=5.0) as client:
        failure_query = """
            sum(rate(celery_task_failed_total[1h])) / 
            sum(rate(celery_task_received_total[1h])) * 100
        """
        failure_response = await client.get(
            f"{PROMETHEUS_URL}/api/v1/query", params={"query": failure_query}
        )
        failure_data = failure_response.json()

    failure_rate = 0.0
    results = failure_data.get("data", {}).get("result", [])
    if results:
        failure_rate = float(results[0]["value"][1])

    success_rate = 100.0 - failure_rate if failure_rate > 0 else 100.0

    return success_rate


async def get_celery_stats():
    """Get Celery worker and queue stats from Prometheus."""
    tasks = [
        get_active_workers(),
        get_queue_depth(),
        get_tasks_per_hour(),
        get_success_rate(),
    ]
    try:
        results = await asyncio.gather(*tasks)
        return {
            "active_workers": results[0],
            "total_workers": 3,
            "queue_depth": results[1],
            "tasks_per_hour": results[2],
            "success_rate": round(results[3], 1),
        }

    except Exception as e:
        logger.error(f"Failed to get Prometheus metrics: {e}")
        return {
            "active_workers": 0,
            "total_workers": 3,
            "queue_depth": 0,
            "tasks_per_hour": 0,
            "success_rate": 0.0,
        }


async def main():
    targets = await get_prometheus_targets()
    task_throughput = await get_task_throughput()
    worker_status = await get_worker_status()
    worker_status_history = await get_worker_status_history()
    num_tasks_processed = await get_tasks_processed_last_24h()
    failure_rate = await get_task_failure_rate()

    breakpoint()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
