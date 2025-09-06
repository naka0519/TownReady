# syntax=docker/dockerfile:1.7
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

###
# This Dockerfile expects build context at the repo root.
# Example:
#   gcloud builds submit --tag $IMAGE_URI --file GCP_AI_Agent_hackathon/api/Dockerfile .
###

COPY GCP_AI_Agent_hackathon/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy full project under package root for stable imports
COPY GCP_AI_Agent_hackathon /app/GCP_AI_Agent_hackathon

EXPOSE 8080

CMD ["uvicorn", "GCP_AI_Agent_hackathon.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
