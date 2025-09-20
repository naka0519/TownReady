#!/usr/bin/env bash
# Sync kb/region_context/*.json to GCS bucket defined in .env (GCS_BUCKET)
set -euo pipefail

if [[ ! -f .env ]]; then
  echo "[ERROR] .env not found in current directory" >&2
  exit 1
fi

set -a; source .env; set +a

if [[ -z "${GCS_BUCKET:-}" ]]; then
  echo "[ERROR] GCS_BUCKET is not set" >&2
  exit 1
fi

SRC_DIR=${REGION_CONTEXT_DIR_LOCAL:-kb/region_context}
DEST_DIR=${REGION_CONTEXT_DIR:-$GCS_BUCKET/region_context}

echo "[INFO] Syncing $SRC_DIR -> $DEST_DIR"
if [[ $DEST_DIR == gs://* ]]; then
  gsutil -m rsync -c -d "$SRC_DIR" "$DEST_DIR"
else
  mkdir -p "$DEST_DIR"
  rsync -av --delete "$SRC_DIR/" "$DEST_DIR/"
fi

echo "[INFO] Done"
