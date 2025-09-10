#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $0 --project <GCP_PROJECT> --region <REGION> --repo <REPO> --image <IMAGE> --service <SERVICE> --sa <SERVICE_ACCOUNT>

Builds the worker container, pushes to Artifact Registry, and deploys to Cloud Run.
USAGE
}

PROJECT=""; REGION=""; REPO="app"; IMAGE="townready-worker"; SERVICE="townready-worker"; SA=""
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

echo "[STEP] Enable Artifact Registry"
gcloud services enable artifactregistry.googleapis.com 1>/dev/null

echo "[STEP] Ensure repository: $REPO"
gcloud artifacts repositories create "$REPO" --repository-format=docker --location="$REGION" || true

echo "[STEP] Build & Push: $IMAGE_URI"
#gcloud builds submit --tag "$IMAGE_URI" workers/
gcloud builds submit --config infra/cloudbuild.worker.yaml --substitutions _IMAGE_URI="$IMAGE_URI" .

echo "[STEP] Deploy to Cloud Run: $SERVICE"
gcloud run deploy "$SERVICE" \
  --image="$IMAGE_URI" \
  --region="$REGION" \
  --service-account="$SA" \
  --allow-unauthenticated \
  --port=8080

echo "[OK] Deployed. Check the service URL above."

