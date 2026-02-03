FROM python:3.13-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app ./app

# The command is overridden in docker-compose for development
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]