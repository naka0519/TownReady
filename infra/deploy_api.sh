#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $0 --project <GCP_PROJECT> --region <REGION> --repo <REPO> --image <IMAGE> --service <SERVICE> --sa <SERVICE_ACCOUNT>

Builds the API container, pushes to Artifact Registry, and deploys to Cloud Run.

Environment variables passed to the service (if set in current shell):
  GCP_PROJECT, REGION, FIRESTORE_DB, GCS_BUCKET, PUBSUB_TOPIC,
  KB_DATASET, KB_SEARCH_LOCATION, KB_SEARCH_COLLECTION, KB_SEARCH_DATASTORE
USAGE
}

PROJECT=""; REGION=""; REPO="app"; IMAGE="townready-api"; SERVICE="townready-api"; SA=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2;;
    --region)  REGION="$2";  shift 2;;
    --repo)    REPO="$2";    shift 2;;
    --image)   IMAGE="$2";   shift 2;;
    --service) SERVICE="$2"; shift 2;;
    --sa)      SA="$2";      shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ -z "$PROJECT" || -z "$REGION" || -z "$SA" ]]; then
  echo "[ERROR] --project, --region, --sa are required" >&2
  usage; exit 1
fi

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${IMAGE}:latest"

echo "[STEP] gcloud project: $PROJECT"
gcloud config set project "$PROJECT" 1>/dev/null

echo "[STEP] Enable Artifact Registry"
gcloud services enable artifactregistry.googleapis.com 1>/dev/null

echo "[STEP] Ensure repository: $REPO"
gcloud artifacts repositories create "$REPO" --repository-format=docker --location="$REGION" || true

echo "[STEP] Build & Push: $IMAGE_URI"
gcloud builds submit --config infra/cloudbuild.api.yaml --substitutions _IMAGE_URI="$IMAGE_URI" .

# Collect env vars from current shell if present
ENV_SET=()
add_env() { [[ -n "${!1-}" ]] && ENV_SET+=("$1=${!1}"); }
add_env GCP_PROJECT
add_env REGION
add_env FIRESTORE_DB
add_env GCS_BUCKET
add_env PUBSUB_TOPIC
# add_env KB_DATASET
# add_env KB_SEARCH_LOCATION
# add_env KB_SEARCH_COLLECTION
# add_env KB_SEARCH_DATASTORE

SET_ENV_FLAG=()
if (( ${#ENV_SET[@]} > 0 )); then
  JOINED_STR=$(IFS=, ; printf '%s' "${ENV_SET[*]}")
  SET_ENV_FLAG=("--set-env-vars" "${JOINED_STR}")
  echo "[INFO] Passing env vars: ${JOINED_STR}"
else
  echo "[INFO] No env vars from shell to set on service"
fi

echo "[STEP] Deploy to Cloud Run: $SERVICE"
gcloud run deploy "$SERVICE" \
  --image="$IMAGE_URI" \
  --region="$REGION" \
  --service-account="$SA" \
  --allow-unauthenticated \
  "${SET_ENV_FLAG[@]}"

URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')
echo "[OK] Deployed: $URL"

echo "[HINT] Verify: curl -i \"$URL/health\""
