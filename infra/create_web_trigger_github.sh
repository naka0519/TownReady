#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $0 --project <GCP_PROJECT> --region <REGION> --owner <GITHUB_OWNER> --repo <GITHUB_REPO> [--branch <BRANCH>] [--name <TRIGGER_NAME>] [--repo-name <AR_REPO>]

Creates a Cloud Build trigger (GitHub) for the Web service using infra/cloudbuild.web.yaml.
The trigger builds web/ and pushes to Artifact Registry, then you can deploy via deploy_web.sh or another pipeline.

Requires that the GitHub App integration for Cloud Build is installed for the repository.

Defaults:
  BRANCH: main
  TRIGGER_NAME: TownReady-Web-CI
  AR_REPO: app
USAGE
}

PROJECT=""; REGION=""; OWNER=""; REPO=""; BRANCH="main"; NAME="TownReady-Web-CI"; AR_REPO="app"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2;;
    --region)  REGION="$2";  shift 2;;
    --owner)   OWNER="$2";   shift 2;;
    --repo)    REPO="$2";    shift 2;;
    --branch)  BRANCH="$2";  shift 2;;
    --name)    NAME="$2";    shift 2;;
    --repo-name) AR_REPO="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ -z "$PROJECT" || -z "$REGION" || -z "$OWNER" || -z "$REPO" ]]; then
  echo "[ERROR] --project, --region, --owner, --repo are required" >&2
  usage; exit 1
fi

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/web:latest"

echo "[STEP] Set project"
gcloud config set project "$PROJECT" 1>/dev/null

echo "[STEP] Enable Cloud Build and Artifact Registry"
gcloud services enable cloudbuild.googleapis.com artifactregistry.googleapis.com 1>/dev/null

echo "[STEP] Ensure Artifact Registry repo: ${AR_REPO}"
gcloud artifacts repositories create "$AR_REPO" --repository-format=docker --location="$REGION" || true

echo "[STEP] Create/Update trigger: ${NAME}"
set +e
gcloud builds triggers create github \
  --project "$PROJECT" \
  --name "$NAME" \
  --repo-name "$REPO" \
  --repo-owner "$OWNER" \
  --branch-pattern "$BRANCH" \
  --build-config "infra/cloudbuild.web.yaml" \
  --substitutions "_IMAGE_URI=${IMAGE_URI}" \
  --included-files "web/**,infra/cloudbuild.web.yaml,web/Dockerfile" \
  --verbosity warning
CREATE_RC=$?
set -e

if [[ $CREATE_RC -ne 0 ]]; then
  echo "[WARN] Trigger creation failed. Attempting to update existing trigger (if any)..."
  TRIGGER_ID=$(gcloud builds triggers list --project "$PROJECT" --format="value(id)" --filter="name=$NAME" | head -n1 || true)
  if [[ -n "${TRIGGER_ID:-}" ]]; then
    gcloud builds triggers update "$TRIGGER_ID" --project "$PROJECT" --substitutions "_IMAGE_URI=${IMAGE_URI}" 1>/dev/null || true
  else
    echo "[ERROR] Trigger not created and no existing trigger named '$NAME' was found."
    echo "[HINT] Ensure Cloud Build GitHub App is installed and authorized for repo: $OWNER/$REPO"
    echo "       Console: Cloud Build → トリガー → 連携を追加（GitHub App）→ リポジトリ選択"
    exit 1
  fi
fi

echo "[OK] Trigger ready: ${NAME}"
echo "[HINT] Run trigger manually:"
echo "  gcloud builds triggers run '${NAME}' --project '$PROJECT' --branch='$BRANCH' --substitutions _IMAGE_URI='${IMAGE_URI}'"
