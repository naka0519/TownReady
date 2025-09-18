#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $0 --project <GCP_PROJECT> --region <REGION> --csr-repo <CSR_REPO> [--branch <BRANCH>] [--name <TRIGGER_NAME>] [--repo-name <AR_REPO>]

Creates a Cloud Build trigger (Cloud Source Repositories) for the Web service using infra/cloudbuild.web.yaml.

Defaults:
  BRANCH: main
  TRIGGER_NAME: TownReady-Web-CI
  AR_REPO: app
USAGE
}

PROJECT=""; REGION=""; CSR_REPO=""; BRANCH="main"; NAME="TownReady-Web-CI"; AR_REPO="app"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2;;
    --region)  REGION="$2";  shift 2;;
    --csr-repo) CSR_REPO="$2"; shift 2;;
    --branch)  BRANCH="$2";  shift 2;;
    --name)    NAME="$2";    shift 2;;
    --repo-name) AR_REPO="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ -z "$PROJECT" || -z "$REGION" || -z "$CSR_REPO" ]]; then
  echo "[ERROR] --project, --region, --csr-repo are required" >&2
  usage; exit 1
fi

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/web:latest"

echo "[STEP] Set project"
gcloud config set project "$PROJECT" 1>/dev/null

echo "[STEP] Enable Cloud Build and Artifact Registry"
gcloud services enable cloudbuild.googleapis.com artifactregistry.googleapis.com 1>/dev/null

echo "[STEP] Ensure Artifact Registry repo: ${AR_REPO}"
gcloud artifacts repositories create "$AR_REPO" --repository-format=docker --location="$REGION" || true

echo "[STEP] Create/Update trigger: ${NAME} (CSR)"
gcloud builds triggers create cloud-source-repositories \
  --project "$PROJECT" \
  --name "$NAME" \
  --repo "$CSR_REPO" \
  --branch-pattern "$BRANCH" \
  --build-config "infra/cloudbuild.web.yaml" \
  --substitutions "_IMAGE_URI=${IMAGE_URI}" \
  --included-files "web/**,infra/cloudbuild.web.yaml,web/Dockerfile" \
  --verbosity warning || {
    echo "[INFO] Trigger may already exist. Updating substitutions..."
    TRIGGER_ID=$(gcloud builds triggers list --project "$PROJECT" --format="value(id)" --filter="name=$NAME" | head -n1)
    if [[ -n "$TRIGGER_ID" ]]; then
      gcloud builds triggers update "$TRIGGER_ID" --project "$PROJECT" --substitutions "_IMAGE_URI=${IMAGE_URI}" 1>/dev/null || true
    fi
  }

echo "[OK] Trigger created: ${NAME}"
echo "[HINT] Run trigger manually:"
echo "  gcloud builds triggers run '${NAME}' --project '$PROJECT' --branch='$BRANCH' --substitutions _IMAGE_URI='${IMAGE_URI}'"

