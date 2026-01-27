FROM python:3.11-slim

WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy setup.py and app directory
COPY setup.py .
COPY app/ ./app/

# Install the package
RUN pip install -e .

CMD ["celery", "-A", "app.main", "worker", "--loglevel=info"]