#!/bin/bash
# start_gpu_worker.sh

set -a
source ~/repos/stock-analysis/src/worker/.env
set +a

# Activate virtual environment
source ~/repos/stock-analysis/.venv/bin/activate

pip install -e .

# Start Celery worker for GPU queue
celery -A app.main worker \
  --queues=gpu \
  --pool=threads \
  --concurrency=4 \
  --loglevel=info \
  --hostname=stock-analysis-celery-worker-gpu
