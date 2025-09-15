#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env ]]; then set -a; source .env; set +a; fi

API_URL=${API_URL:?"API_URL is required (set in .env)"}

echo "[E2E] Kick plan job"
cat <<'JSON' > /tmp/plan.json
{"location":{"address":"横浜市瀬谷区＊＊＊","lat":35.47,"lng":139.49},
 "participants":{"total":120,"children":25,"elderly":18,"wheelchair":3,"languages":["ja","en"]},
 "hazard":{"types":["earthquake","fire"],"drill_date":"2025-10-12","indoor":true,"nighttime":false},
 "constraints":{"max_duration_min":45,"limited_outdoor":true},
 "kb_refs":["kb://yokohama_guideline","kb://shelter_rules"]}
JSON

JOB_ID=$(curl -sS -X POST -H 'Content-Type: application/json' -d @/tmp/plan.json "$API_URL/api/generate/plan" | jq -r .job_id)
test -n "$JOB_ID" || { echo "[E2E] ERROR: job_id empty"; exit 1; }
echo "[E2E] job_id=$JOB_ID"

echo "[E2E] Wait for chaining (up to 40s)"
for i in {1..20}; do
  curl -sS "$API_URL/api/jobs/$JOB_ID" | tee /tmp/job.json >/dev/null
  CNT=$(jq -r '(.completed_tasks|length)//0' /tmp/job.json)
  echo "[E2E] tasks=$CNT"
  [[ "$CNT" -ge 4 ]] && break
  sleep 2
done

echo "[E2E] Verify signed URLs"
jq -e '.assets.script_md_url and .assets.routes_json_url' /tmp/job.json >/dev/null || {
  echo "[E2E] ERROR: scenario assets URLs missing"; exit 1; }

echo "[E2E] HEAD scenario script_md_url"
URL=$(jq -r '.assets.script_md_url' /tmp/job.json); curl -sI "$URL" | head -n1

echo "[E2E] HEAD content poster_prompts_url"
URL2=$(jq -r '.results.content.poster_prompts_url // empty' /tmp/job.json)
if [[ -n "$URL2" ]]; then curl -sI "$URL2" | head -n1; else echo "[E2E] WARN: content URL missing"; fi

echo "[E2E] Done"

