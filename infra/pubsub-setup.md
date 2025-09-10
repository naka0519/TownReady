# Pub/Sub 設定手順（jobs トピック / push or pull）

TownReady では、API で受けたリクエストを Pub/Sub に発行し、ワーカーが処理します。

## 変数

```bash
export GCP_PROJECT="townready"
export REGION="asia-northeast1"
export TOPIC="townready-jobs"  # .env の PUBSUB_TOPIC と一致させる
```

## 有効化とトピック作成

```bash
gcloud config set project "$GCP_PROJECT"
gcloud services enable pubsub.googleapis.com

gcloud pubsub topics create "$TOPIC" --project "$GCP_PROJECT" || true
```

## サブスクリプション

- Pull 型（ローカル検証向け）

```bash
gcloud pubsub subscriptions create "${TOPIC}-pull" \
  --topic "$TOPIC" \
  --project "$GCP_PROJECT" || true
```

- Push 型（Cloud Run ワーカー向け）
  注意: Push サブスクリプションの作成は、Cloud Run ワーカーの本番 URL が確定してから実施します（後程対応）。下記の`WORKER_URL`が用意できたタイミングで実行してください。

```bash
# WORKER_URL は Cloud Run でデプロイしたワーカーURL（例: https://<service>-<hash>-an.a.run.app）
# 注意: 末尾にパスを付けない（/pubsub/push は付けない）。疎通確認は /health で行う。
export WORKER_URL="https://townready-worker-rxazeqylpq-an.a.run.app"
# ヘルスチェック: 200 が返れば OK
curl -i "$WORKER_URL/health"

gcloud pubsub subscriptions create "${TOPIC}-push" \
  --topic "$TOPIC" \
  --push-endpoint="${WORKER_URL}/pubsub/push" \
  --push-auth-service-account="townready-api@${GCP_PROJECT}.iam.gserviceaccount.com" \
  --project "$GCP_PROJECT" || true
```

### トラブルシューティング

- `curl -fsS "$WORKER_URL/health"` が `404` の場合、多くは `WORKER_URL` に `/pubsub/push` を含めてしまっているのが原因です。`WORKER_URL` はベース URL のみにしてください。
- `GET ${WORKER_URL}/pubsub/push` は `405 Method Not Allowed` が正常です（Push 配信は `POST`）。

````

TODO

- [ ] Push サブスクリプション作成後、実運用トピックへメッセージが届くことを`jobs`の状態更新で確認

## 動作確認

```bash
# メッセージ発行（サンプル）
cat <<MSG | gcloud pubsub topics publish "$TOPIC" --attribute=type=plan --message=-
{"job_id":"test-123","task":"plan"}
MSG

# Pull型で受信（Pullサブスクリプションの場合）
gcloud pubsub subscriptions pull "${TOPIC}-pull" --auto-ack --limit=1
````

---

## 自動化スクリプト

`infra/setup_pubsub.sh` に同等の処理があります。

```bash
./infra/setup_pubsub.sh \
  --project "$GCP_PROJECT" \
  --topic "$TOPIC" \
  --create-pull \
  --create-push --worker-url "$WORKER_URL" --sa "townready-api@${GCP_PROJECT}.iam.gserviceaccount.com"
```
