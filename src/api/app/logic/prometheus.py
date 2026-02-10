import requests
from datetime import datetime, timedelta, timezone

PROM_URL = "http://10.0.10.127:9090"  # <-- change this

QUERY = "flower_worker_online"

# Time range: last 24 hours
end = datetime.now(timezone.utc)
start = end - timedelta(hours=24)

params = {
    "query": QUERY,
    "start": start.timestamp(),
    "end": end.timestamp(),
    "step": 60,  # 1-minute resolution; adjust as needed
}

resp = requests.get(
    f"{PROM_URL}/api/v1/query_range",
    params=params,
    timeout=30,
)

resp.raise_for_status()
data = resp.json()
print(data)

if data["status"] != "success":
    raise RuntimeError(data)

# Extract values
results = data["data"]["result"]

for series in results:
    metric_labels = series["metric"]
    values = series["values"]  # list of [timestamp, value]

    print("Labels:", metric_labels)
    print("Sample points:", len(values))
    print("First point:", values[0])
    print("Last point:", values[-1])
