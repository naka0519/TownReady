#!/usr/bin/env bash
set -euo pipefail

echo "[ContractTest] Loading env (.env) if present"
if [[ -f .env ]]; then set -a; source .env; set +a; fi

echo "[ContractTest] Generate JSON Schemas"
python -m schemas.generate_json_schema >/dev/null

echo "[ContractTest] Validate sample GenerateBaseRequest payload"
python - <<'PY'
from pathlib import Path
from pydantic import ValidationError
import json
try:
    from GCP_AI_Agent_hackathon.schemas import GenerateBaseRequest
except Exception:
    import sys
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from schemas import GenerateBaseRequest  # type: ignore

payload_dir = Path("scripts/payloads")
paths = sorted(payload_dir.glob("*.json"))
if not paths:
    raise SystemExit("No payload samples found in scripts/payloads")

for path in paths:
    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        GenerateBaseRequest.model_validate(data)
        print(f"OK: {path.name}")
    except ValidationError as exc:
        print(f"ERROR: {path}: validation failed\n{exc}")
        raise SystemExit(1)
PY

if [[ -n "${API_URL:-}" ]]; then
  echo "[ContractTest] API smoke (plan)"
  mkdir -p tmp
  SAMPLE_JSON=$(ls scripts/payloads/*.json | head -n1)
  cp "$SAMPLE_JSON" tmp/ct_plan.json
  JOB_ID=$(curl -sS -X POST -H 'Content-Type: application/json' \
    -d @tmp/ct_plan.json "$API_URL/api/generate/plan" | jq -r .job_id)
  test -n "$JOB_ID" || { echo "[ContractTest] ERROR: job_id empty"; exit 1; }
  echo "[ContractTest] job_id=$JOB_ID"
  # Fetch job doc once
  curl -sS "$API_URL/api/jobs/$JOB_ID" | jq -e '.job_id and (.status|tostring) and (.payload|type=="object")' >/dev/null
  echo "[ContractTest] API smoke OK"
else
  echo "[ContractTest] Skipped API smoke (API_URL not set)"
fi

echo "[ContractTest] Done"
