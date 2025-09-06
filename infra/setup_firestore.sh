#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $0 --project <GCP_PROJECT> --region <REGION> --database <FIRESTORE_DB> [--sa <SERVICE_ACCOUNT_EMAIL>]

Creates a Firestore database (Native mode) with the given database ID and grants IAM roles to a service account.

Example:
  $0 --project townready --region asia-northeast1 --database townready \
     --sa townready-api@townready.iam.gserviceaccount.com
USAGE
}

PROJECT=""; REGION=""; DATABASE=""; SA=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)  PROJECT="$2"; shift 2;;
    --region)   REGION="$2";  shift 2;;
    --database) DATABASE="$2"; shift 2;;
    --sa)       SA="$2";       shift 2;;
    -h|--help)  usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ -z "$PROJECT" || -z "$REGION" || -z "$DATABASE" ]]; then
  echo "[ERROR] --project, --region, --database are required" >&2
  usage; exit 1
fi

echo "[INFO] Project : $PROJECT"
echo "[INFO] Region  : $REGION"
echo "[INFO] Database: $DATABASE"
[[ -n "$SA" ]] && echo "[INFO] Service Account: $SA" || true

echo "[STEP] Set gcloud project"
gcloud config set project "$PROJECT" 1>/dev/null

echo "[STEP] Enable Firestore API"
gcloud services enable firestore.googleapis.com 1>/dev/null

echo "[STEP] Create Firestore database (if not exists)"
if ! gcloud firestore databases describe --database="$DATABASE" >/dev/null 2>&1; then
  gcloud firestore databases create \
    --database="$DATABASE" \
    --location="$REGION" \
    --type=firestore-native
else
  echo "[INFO] Database already exists. Skipping create."
fi

if [[ -n "$SA" ]]; then
  echo "[STEP] Grant roles/datastore.user to $SA"
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$SA" \
    --role="roles/datastore.user" 1>/dev/null
fi

echo "[OK] Firestore database is ready: projects/$PROJECT/databases/$DATABASE"

