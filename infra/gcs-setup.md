# GCS 設定手順（TownReady）

以下は GCS バケットを作成し、アプリが生成物を保存できるようにする最小手順です。

## 前提

- `gcloud` CLI がセットアップ済み（ログインと初期化済み）
- プロジェクト/Billing 有効
- `.env` の `GCP_PROJECT` と `REGION` を使用

## 変数例

```bash
export GCP_PROJECT="townready"
export REGION="asia-northeast1"
# 例: プロジェクトに紐づく一意な名前を推奨
export BUCKET_NAME="${GCP_PROJECT}-townready-assets-${REGION}"
```

## 有効化と作成

```bash
# プロジェクト設定
gcloud config set project "$GCP_PROJECT"

# API 有効化（Storage）
gcloud services enable storage.googleapis.com

# バケット作成（Uniform access, Regional）
gcloud storage buckets create "gs://${BUCKET_NAME}" \
  --location="${REGION}" \
  --uniform-bucket-level-access
```

## 権限（サービスアカウント）

Cloud Run の実行サービスアカウント、またはローカルのサービスアカウントに最低限のオブジェクト操作権限を付与します。

```bash
# 例: Cloud Run 実行 SA
auth_sa="townready-api@${GCP_PROJECT}.iam.gserviceaccount.com"  # 例。実際のSAに置換

# オブジェクト管理（アップロード/閲覧）
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="serviceAccount:${auth_sa}" \
  --role="roles/storage.objectAdmin"

# 読み取りのみで十分なら（将来の閲覧用途）
# gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
#   --member="serviceAccount:${auth_sa}" \
#   --role="roles/storage.objectViewer"
```

## `.env` 反映

`.env` または環境に以下を設定します。

```bash
GCS_BUCKET=gs://${BUCKET_NAME}
```

## 動作確認

```bash
# 1. ダミーオブジェクト作成
printf 'hello' | gcloud storage cp - "gs://${BUCKET_NAME}/healthcheck/ok.txt"
# 2. 一覧
gcloud storage ls "gs://${BUCKET_NAME}/healthcheck/"
```

---

## 付録: 自動化スクリプト

`infra/setup_gcs.sh` に同等の処理を用意しています。

```bash
./infra/setup_gcs.sh \
  --project "$GCP_PROJECT" \
  --region "$REGION" \
  --bucket "$BUCKET_NAME" \
  --sa "townready-api@${GCP_PROJECT}.iam.gserviceaccount.com"
```
