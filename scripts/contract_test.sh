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

sample = {
  "location": {"address": "横浜市瀬谷区＊＊＊", "lat": 35.47, "lng": 139.49},
  "participants": {"total": 120, "children": 25, "elderly": 18, "wheelchair": 3, "languages": ["ja", "en"]},
  "hazard": {"types": ["earthquake", "fire"], "drill_date": "2025-10-12", "indoor": True, "nighttime": False},
  "constraints": {"max_duration_min": 45, "limited_outdoor": True},
  "kb_refs": ["kb://yokohama_guideline", "kb://shelter_rules"]
}
try:
    _ = GenerateBaseRequest.model_validate(sample)
    print("OK: GenerateBaseRequest is valid")
except ValidationError as e:
    print("ERROR: validation failed\n", e)
    raise SystemExit(1)
PY

if [[ -n "${API_URL:-}" ]]; then
  echo "[ContractTest] API smoke (plan)"
  cat > tmp/ct_plan.json <<'JSON'
{
  "location": { "address": "横浜市瀬谷区＊＊＊", "lat": 35.47, "lng": 139.49 },
  "participants": {"total": 120, "children": 25, "elderly": 18, "wheelchair": 3, "languages": ["ja","en"]},
  "hazard": {"types": ["earthquake","fire"], "drill_date": "2025-10-12", "indoor": true, "nighttime": false},
  "constraints": {"max_duration_min": 45, "limited_outdoor": true},
  "kb_refs": ["kb://yokohama_guideline", "kb://shelter_rules"]
}
JSON
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
