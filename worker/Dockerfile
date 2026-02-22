FROM python:3.13-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code and install
COPY setup.py .
COPY app/ ./app/
RUN pip install -e .

CMD ["celery", "-A", "app.main", "worker", "--loglevel=info"]