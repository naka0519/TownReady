#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $0 --project <GCP_PROJECT> --topic <TOPIC> [--create-pull] [--create-push --worker-url <URL> --sa <SERVICE_ACCOUNT>]

Enables Pub/Sub API, creates a topic, and optionally creates pull/push subscriptions.
USAGE
}

PROJECT=""; TOPIC=""; CREATE_PULL=false; CREATE_PUSH=false; WORKER_URL=""; SA=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2;;
    --topic)   TOPIC="$2";   shift 2;;
    --create-pull) CREATE_PULL=true; shift 1;;
    --create-push) CREATE_PUSH=true; shift 1;;
    --worker-url) WORKER_URL="$2"; shift 2;;
    --sa) SA="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ -z "$PROJECT" || -z "$TOPIC" ]]; then
  echo "[ERROR] --project and --topic are required" >&2
  usage; exit 1
fi

echo "[STEP] Set project"
gcloud config set project "$PROJECT" 1>/dev/null

echo "[STEP] Enable Pub/Sub API"
gcloud services enable pubsub.googleapis.com 1>/dev/null

echo "[STEP] Create topic ($TOPIC)"
gcloud pubsub topics create "$TOPIC" --project "$PROJECT" || true

if $CREATE_PULL; then
  echo "[STEP] Create pull subscription (${TOPIC}-pull)"
  gcloud pubsub subscriptions create "${TOPIC}-pull" \
    --topic "$TOPIC" --project "$PROJECT" || true
fi

if $CREATE_PUSH; then
  if [[ -z "$WORKER_URL" || -z "$SA" ]]; then
    echo "[ERROR] --worker-url and --sa are required when using --create-push" >&2
    exit 1
  fi
  echo "[STEP] Create push subscription (${TOPIC}-push)"
  gcloud pubsub subscriptions create "${TOPIC}-push" \
    --topic "$TOPIC" \
    --push-endpoint="${WORKER_URL}/pubsub/push" \
    --push-auth-service-account="$SA" \
    --project "$PROJECT" || true
fi

echo "[OK] Pub/Sub setup complete"

