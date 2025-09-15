#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Sync Pub/Sub push config and Worker OIDC settings to the current Cloud Run URL.

Usage:
  $0 \\
    --project <GCP_PROJECT> \\
    --region <REGION> \\
    --service <WORKER_SERVICE_NAME> \\
    --subscription <PUSH_SUBSCRIPTION_NAME> \\
    --sa <PUSH_AUTH_SERVICE_ACCOUNT> \\
    [--verify <true|false>] [--set-basics-env] [--dotenv <PATH_TO_.env>]

Options:
  --project       GCP project ID (required)
  --region        Region, e.g., asia-northeast1 (required)
  --service       Cloud Run worker service name (default: townready-worker)
  --subscription  Pub/Sub push subscription name (required)
  --sa            Service account email used by Pub/Sub push OIDC (required)
  --verify        Enable worker-side OIDC verification (default: true)
  --set-basics-env  Also set basics env on the worker (GCP_PROJECT, REGION, FIRESTORE_DB, GCS_BUCKET, PUBSUB_TOPIC)
  --dotenv        Optional path to .env to source before running

This script will:
  1) Read the current Cloud Run service URL (status.url)
  2) Point the Pub/Sub push endpoint + audience to <status.url>/pubsub/push
  3) Update the worker's PUSH_* env vars to the same audience + SA (and basics if requested)

Examples:
  $0 --project townready --region asia-northeast1 \
     --service townready-worker --subscription townready-jobs-push \
     --sa townready-api@townready.iam.gserviceaccount.com --verify true --set-basics-env
USAGE
}

PROJECT=""; REGION=""; SERVICE="townready-worker"; SUB=""; SA=""; VERIFY="true"; SET_BASICS=false; DOTENV=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)      PROJECT="$2"; shift 2;;
    --region)       REGION="$2"; shift 2;;
    --service)      SERVICE="$2"; shift 2;;
    --subscription) SUB="$2"; shift 2;;
    --sa)           SA="$2"; shift 2;;
    --verify)       VERIFY="$2"; shift 2;;
    --set-basics-env) SET_BASICS=true; shift 1;;
    --dotenv)       DOTENV="$2"; shift 2;;
    -h|--help)      usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

if [[ -n "$DOTENV" ]]; then
  if [[ -f "$DOTENV" ]]; then
    set -a; # export all sourced vars
    # shellcheck disable=SC1090
    source "$DOTENV"
    set +a
  else
    echo "[WARN] --dotenv provided but file not found: $DOTENV" >&2
  fi
fi

if [[ -z "$PROJECT" || -z "$REGION" || -z "$SUB" || -z "$SA" ]]; then
  echo "[ERROR] --project, --region, --subscription, --sa are required" >&2
  usage; exit 1
fi

echo "[STEP] gcloud project: $PROJECT"
gcloud config set project "$PROJECT" 1>/dev/null

echo "[STEP] Resolve current Worker URL (status.url)"
WORKER_URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(status.url)')
if [[ -z "$WORKER_URL" ]]; then
  echo "[ERROR] Could not resolve worker URL for service: $SERVICE" >&2
  exit 1
fi
echo "[INFO] WORKER_URL=$WORKER_URL"

AUDIENCE="${WORKER_URL}/pubsub/push"

echo "[STEP] Update Pub/Sub push endpoint + audience"
gcloud pubsub subscriptions modify-push-config "$SUB" \
  --project "$PROJECT" \
  --push-endpoint="$AUDIENCE" \
  --push-auth-service-account="$SA" \
  --push-auth-token-audience="$AUDIENCE" 1>/dev/null
echo "[OK] Subscription updated: $SUB"

echo "[STEP] Update Worker env (PUSH_*)"
ENV_SET=(
  "PUSH_VERIFY=$VERIFY"
  "PUSH_AUDIENCE=$AUDIENCE"
  "PUSH_SERVICE_ACCOUNT=$SA"
)

if $SET_BASICS; then
  echo "[INFO] Including basics env from current shell (if set)"
  add_env() { [[ -n "${!1-}" ]] && ENV_SET+=("$1=${!1}"); }
  add_env GCP_PROJECT
  add_env REGION
  add_env FIRESTORE_DB
  add_env GCS_BUCKET
  add_env PUBSUB_TOPIC
fi

JOINED=$(IFS=, ; printf '%s' "${ENV_SET[*]}")
gcloud run services update "$SERVICE" \
  --project "$PROJECT" --region "$REGION" \
  --set-env-vars "$JOINED" 1>/dev/null
echo "[OK] Worker env updated"

echo "[STEP] Verify settings"
echo "[INFO] Subscription pushConfig:"
gcloud pubsub subscriptions describe "$SUB" --project "$PROJECT" --format='yaml(pushConfig)'
echo "[INFO] Worker env (subset):"
gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(spec.template.spec.containers[0].env)'

echo "[DONE] Sync complete"

