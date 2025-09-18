# Cloud Run Worker デプロイ手順

この手順で FastAPI ワーカー（`workers/server.py`）を Cloud Run にデプロイし、Pub/Sub Push サブスクリプションから受信できるようにします。

## 前提

- Artifact Registry がプロジェクトに存在
- サービスアカウント: `townready-api@${GCP_PROJECT}.iam.gserviceaccount.com`（実行および Push 認証に利用）
- `.env` に `GCP_PROJECT`,`REGION`,`PUBSUB_TOPIC` が設定済み

## 変数

```bash
export GCP_PROJECT="townready"
export REGION="asia-northeast1"
export REPO="app"  # Artifact Registry のリポジトリ名
export IMAGE="townready-worker"
export IMAGE_URI="${REGION}-docker.pkg.dev/${GCP_PROJECT}/${REPO}/${IMAGE}:latest"
export SERVICE="townready-worker"
export SA="townready-api@${GCP_PROJECT}.iam.gserviceaccount.com"
```

## Artifact Registry（初回のみ）

```bash
gcloud services enable artifactregistry.googleapis.com
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" || true
```

## ビルド & プッシュ

```bash
gcloud builds submit --tag "$IMAGE_URI" workers/
```

## Cloud Run へデプロイ

```bash
gcloud run deploy "$SERVICE" \
  --image="$IMAGE_URI" \
  --region="$REGION" \
  --service-account="$SA" \
  --allow-unauthenticated \
  --port=8080

# 出力のURLをメモ: https://<service>-<hash>-an.a.run.app
```

セキュリティを高める場合は `--no-allow-unauthenticated` を指定し、Push サブスクリプション作成時に `--push-auth-service-account` を併用します。

## Push サブスクリプション作成

`infra/pubsub-setup.md` の手順を参照。`WORKER_URL` を Cloud Run の URL に置換し、以下を実行します。

```bash
export TOPIC="${PUBSUB_TOPIC:-townready-jobs}"
export WORKER_URL="https://townready-worker-rxazeqylpq-an.a.run.app"  # 例: https://townready-worker-xxxxx-an.a.run.app

gcloud pubsub subscriptions create "${TOPIC}-push" \
  --topic "$TOPIC" \
  --push-endpoint="${WORKER_URL}/pubsub/push" \
  --push-auth-service-account="$SA" \
  --project "$GCP_PROJECT" || true
```

## 動作確認

1. 直接 Publish して Ack/Firestore 更新を確認

```bash
cat <<MSG | gcloud pubsub topics publish "$TOPIC" --attribute=type=plan --message=-
{"job_id":"test-123","task":"plan"}
MSG

# Firestoreの jobs/test-123 が done になっていることを確認
```

2. API 経由（推奨）

```bash
curl -s http://localhost:8080/api/generate/plan \
  -H 'Content-Type: application/json' \
  -d @- <<'JSON'
{
  "location": { "address": "横浜市戸塚区戸塚町", "lat": 35.401, "lng": 139.532 },
  "participants": {"total": 120, "children": 25, "elderly": 18, "wheelchair": 3, "languages": ["ja","en"]},
  "hazard": {"types": ["earthquake","fire"], "drill_date": "2025-10-12", "indoor": true, "nighttime": false},
  "constraints": {"max_duration_min": 45, "limited_outdoor": true},
  "kb_refs": ["kb://yokohama_guideline", "kb://shelter_rules"]
}
JSON

# レスポンスの job_id を使用して確認
curl -s "http://localhost:8080/api/jobs/<job_id>"
```
