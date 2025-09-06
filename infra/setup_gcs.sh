#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $0 --project <GCP_PROJECT> --region <REGION> --bucket <BUCKET_NAME> [--sa <SERVICE_ACCOUNT_EMAIL>]

Creates a regional GCS bucket with uniform bucket-level access and optionally binds Storage roles to a service account.

Example:
  $0 --project your-project --region asia-northeast1 \
     --bucket your-project-townready-assets-asia-northeast1 \
     --sa townready-api@your-project.iam.gserviceaccount.com
USAGE
}

PROJECT=""; REGION=""; BUCKET=""; SA=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2;;
    --region)  REGION="$2";  shift 2;;
    --bucket)  BUCKET="$2";  shift 2;;
    --sa)      SA="$2";      shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ -z "$PROJECT" || -z "$REGION" || -z "$BUCKET" ]]; then
  echo "[ERROR] --project, --region, --bucket are required" >&2
  usage; exit 1
fi

echo "[INFO] Project: $PROJECT"
echo "[INFO] Region : $REGION"
echo "[INFO] Bucket : gs://$BUCKET"
[[ -n "$SA" ]] && echo "[INFO] Service Account: $SA" || true

echo "[STEP] Set gcloud project"
gcloud config set project "$PROJECT" 1>/dev/null

echo "[STEP] Enable Storage API"
gcloud services enable storage.googleapis.com 1>/dev/null

echo "[STEP] Create bucket (if not exists)"
if ! gcloud storage buckets describe "gs://$BUCKET" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://$BUCKET" \
    --location="$REGION" \
    --uniform-bucket-level-access
else
  echo "[INFO] Bucket already exists. Skipping create."
fi

if [[ -n "$SA" ]]; then
  echo "[STEP] Bind roles/storage.objectAdmin to $SA"
  gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
    --member="serviceAccount:$SA" \
    --role="roles/storage.objectAdmin" 1>/dev/null
fi

echo "[OK] GCS bucket is ready: gs://$BUCKET"

