# E2E スモーク手順（MVP）

この手順は、API → ジョブ投入 → Worker 処理 → Firestore 反映 → 署名 URL で成果を取得、までの最小疎通を確認します。

## 前提

- Cloud Run に API/Worker をデプロイ済み
- Pub/Sub Push サブスクが Worker の `/pubsub/push` に紐付いている
- GCS バケットと Firestore が設定済み、`.env` に `GCP_PROJECT/REGION/GCS_BUCKET/FIRESTORE_DB/PUBSUB_TOPIC` などが設定済み
- 署名 URL を使うために、Worker 実行 SA に以下が付与済み
  - `roles/iam.serviceAccountTokenCreator`
  - バケットに `roles/storage.objectAdmin`
  - API 有効化: `iamcredentials.googleapis.com`

```bash
set -a; source .env; set +a
export SERVICE_API="townready-api"
export SERVICE_WORKER="townready-worker"
```

## 1) API/Backend ヘルス

```bash
curl -sS "$API_URL/health" | jq .
curl -sS "$API_URL/health/firestore" | jq .
curl -sS "$WORKER_URL/health" | jq .
```

## 2) Content 単体ジョブ（署名 URL 確認）

```bash
cat <<'JSON' > /tmp/content.json
{"assets": {}, "languages": ["ja","en"]}
JSON

JOB_ID=$(curl -sS -X POST -H 'Content-Type: application/json' \
  -d @/tmp/content.json "$API_URL/api/generate/content" | jq -r .job_id); echo "$JOB_ID"

for i in {1..10}; do
  curl -sS "$API_URL/api/jobs/$JOB_ID" | tee /tmp/job.json >/dev/null
  jq -r '.status,.result.type,.completed_tasks' /tmp/job.json
  jq -e 'select(.result.type=="content")' /tmp/job.json >/dev/null && break
  sleep 2
done

jq '.result | {poster_prompts_url,video_prompt_url,video_shotlist_url}' /tmp/job.json
URL=$(jq -r '.result.poster_prompts_url // empty' /tmp/job.json); [ -n "$URL" ] && curl -sI "$URL"
```

期待: `*_url` が非 null, `curl -I` が 200

## 3) 連鎖（plan→scenario→safety→content）完了

```bash
cat <<'JSON' > /tmp/plan.json
{"location":{"address":"横浜市戸塚区戸塚町上倉田町７６９−１","lat":35.398961,"lng":139.537466},
 "participants":{"total":120,"children":25,"elderly":18,"wheelchair":3,"languages":["ja","en"]},
 "hazard":{"types":["earthquake","fire"],"drill_date":"2025-10-12","indoor":true,"nighttime":false},
 "constraints":{"max_duration_min":45,"limited_outdoor":true},
 "kb_refs":["kb://yokohama_guideline","kb://shelter_rules"]}
JSON

JOB_ID=$(curl -sS -X POST -H 'Content-Type: application/json' -d @/tmp/plan.json "$API_URL/api/generate/plan" | jq -r .job_id)
for i in {1..20}; do
  curl -sS "$API_URL/api/jobs/$JOB_ID" | tee /tmp/job.json >/dev/null
  echo -n "tasks="; jq -r '.completed_tasks' /tmp/job.json
  CNT=$(jq -r '(.completed_tasks|length)//0' /tmp/job.json)
  [ "$CNT" -ge 4 ] && break
  sleep 2
done
jq '.assets | {script_md_url,roles_csv_url,routes_json_url}' /tmp/job.json
```

期待: `completed_tasks` に `["plan","scenario","safety","content"]`、`assets.*_url` の `curl -I` が 200

## 4) ログ監視（Worker の署名/連鎖）

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="'"$SERVICE_WORKER"'" AND resource.labels.location="'"$REGION"'"' \
  --project "$GCP_PROJECT" --limit=100 \
  --format='table(severity,timestamp,resource.labels.revision_name,textPayload,jsonPayload.message)'

# /pubsub/push リクエストログ
gcloud logging read \
  'logName="projects/'"$GCP_PROJECT"'/logs/run.googleapis.com%2Frequests"
   AND resource.type="cloud_run_revision"
   AND resource.labels.service_name="'"$SERVICE_WORKER"'"
   AND resource.labels.location="'"$REGION"'"
   AND httpRequest.requestMethod="POST"
   AND httpRequest.requestUrl:"/pubsub/push"' \
  --project "$GCP_PROJECT" --limit=50 \
  --format='table(severity,timestamp,httpRequest.requestMethod,httpRequest.status,httpRequest.requestUrl,resource.labels.revision_name)'
```

---

## 付録（ローカル代替）

- API: `uvicorn api.app:app --port 8080`
- Worker: `uvicorn workers.server:app --port 8081` / `PUSH_VERIFY=false`
- 手動 Push: `curl -X POST localhost:8081/pubsub/push -d '{"message":{"data":"<base64>"}}'`
