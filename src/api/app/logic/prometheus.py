# Add to requirements.txt: requests

import requests
from datetime import datetime, timedelta

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
