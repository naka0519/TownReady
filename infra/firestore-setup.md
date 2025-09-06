# Firestore 設定手順（Native モード, multi-database）

TownReady の API は Firestore Native モードを使用し、データベースIDを `.env` の `FIRESTORE_DB` から参照します。
初期値は `townready` です（`(default)` ではありません）。

## 前提
- `gcloud` CLI セットアップ済み（`gcloud auth login` または `gcloud auth application-default login`）
- プロジェクト/Billing 有効
- `.env` に `GCP_PROJECT`, `REGION`, `FIRESTORE_DB` が設定済み

## 変数例
```bash
export GCP_PROJECT="townready"
export REGION="asia-northeast1"
export FIRESTORE_DB="townready"  # multi-database の DB ID
```

## 有効化とデータベース作成
```bash
# プロジェクト設定
gcloud config set project "$GCP_PROJECT"

# API 有効化
gcloud services enable firestore.googleapis.com

# データベース作成（Native モード, 指定DB ID）
gcloud firestore databases create \
  --database="$FIRESTORE_DB" \
  --location="$REGION" \
  --type=firestore-native
```

既に存在する場合はエラーになりますが問題ありません（スキップ可）。

## 権限（サービスアカウント）
Cloud Run の実行サービスアカウント、またはローカル開発用SAに Firestore へのアクセス権を付与します。

```bash
# 例: Cloud Run 用の実行 SA（例。実際のSAに置換）
SA="townready-api@${GCP_PROJECT}.iam.gserviceaccount.com"

# 役割付与（読み書き）
gcloud projects add-iam-policy-binding "$GCP_PROJECT" \
  --member="serviceAccount:${SA}" \
  --role="roles/datastore.user"

# 読み取りのみの検証用途なら
# gcloud projects add-iam-policy-binding "$GCP_PROJECT" \
#   --member="serviceAccount:${SA}" \
#   --role="roles/datastore.viewer"
```

## 動作確認（任意）
```bash
# jobs/health にドキュメント作成
python - <<'PY'
from google.cloud import firestore
import os
proj=os.environ['GCP_PROJECT']; dbid=os.environ.get('FIRESTORE_DB','(default)')
client=firestore.Client(project=proj, database=dbid)
ref=client.collection('jobs').document('health')
ref.set({'status':'ok'})
print('OK: wrote jobs/health in', proj, dbid)
PY
```

---

## 自動化スクリプト
`infra/setup_firestore.sh` で上記を自動化できます。

```bash
./infra/setup_firestore.sh \
  --project "$GCP_PROJECT" \
  --region "$REGION" \
  --database "$FIRESTORE_DB" \
  --sa "townready-api@${GCP_PROJECT}.iam.gserviceaccount.com"
```

