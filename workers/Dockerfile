# syntax=docker/dockerfile:1.7
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install system deps (if any)
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . /app

EXPOSE 8080

CMD ["uvicorn", "GCP_AI_Agent_hackathon.workers.server:app", "--host", "0.0.0.0", "--port", "8080"]

