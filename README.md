# README.md

## TownReady – あなたの街専用の防災訓練一式を 10 分で

**TownReady** は、住所・施設・参加者属性・想定災害を入力するだけで、

- 訓練台本（Markdown）
- 役割表（CSV）
- 避難導線ポスター（Imagen 生成 / A4, 多言語）
- 60 秒の注意喚起・手順 VTR（Veo 生成 / 字幕付き）
- 訓練 KPI（参加率・到達時間・理解度）設計と改善提案

を自動生成する、**マルチエージェント × マルチモーダル**の GCP アプリです。

実装の詳細進捗は `docs/SPRINT_PLAN.md` に集約しています。

### 価値提案（1 行）

> **「あなたの街専用の“訓練一式”を、地図 → 台本 → 掲示 → 短尺動画まで自動生成し、次回は“改善案”から始められる。」**

---

## 特長

- **地域特化生成**: 住所/GeoJSON/施設情報に基づく“その場所”の台本・導線図。
- **多言語・配慮**: 日本語/英語を標準。字幕・ピクトグラム・高コントラスト。
- **エビデンス付き**: Vertex AI Search の知識ベースを根拠として参照。
- **効果測定**: QR チェックイン/アンケート連携で KPI を可視化 → 次回改善案。
- **10 分で一式**: Cloud Run バックエンド＋非同期ジョブで高速生成。

---

## アーキテクチャ（MVP）

- **フロント**: Next.js (SSR) → Cloud Run
- **バック**: FastAPI (Python) → Cloud Run
- **ジョブ**: Pub/Sub + ワーカー（非同期処理）
- **データ**: Firestore（案件/ジョブ/メタ）、GCS（生成物）
- **AI**: Vertex AI（Gemini / Imagen / Veo）、Vertex AI Search（KB）

```
[Next.js] ⇄ [FastAPI] → Pub/Sub → [Worker]
   │                         │
   │                         ├─ Vertex AI (Gemini/Imagen/Veo)
   │                         └─ Vertex AI Search (KB)
   └─ GCS(画像/動画)・Firestore(メタ)・署名URL
```

---

## ディレクトリ構成

```
.
├─ api/                 # FastAPI エンドポイント
├─ workers/             # Pub/Sub ワーカー（非同期処理）
├─ web/                 # Next.js フロント
├─ schemas/             # Pydantic モデル / JSON Schema
├─ services/            # Firestore/GCS/PubSub/Gemini/KB クライアント
├─ docs/                # プロダクト仕様・運用ドキュメント
├─ kb/                  # 知識ベース（Markdown/URLカタログ）
├─ infra/               # デプロイスクリプト / Cloud Build 設定
├─ .env.example         # 環境変数のサンプル
└─ README.md
```

---

## API（実装済み抜粋）

- `POST /api/generate/plan` — プラン生成をジョブ化し Pub/Sub へ発行
- `POST /api/generate/scenario` — シナリオ生成をジョブ化
- `POST /api/review/safety` — 安全レビューをジョブ化
- `POST /api/generate/content` — コンテンツ生成をジョブ化
- `GET  /api/jobs/{job_id}` — ジョブ状態取得
- `POST /api/jobs/{job_id}/assets/refresh` — 署名URLの再発行
- `GET  /api/kb/search` — 知識ベース検索
- `POST /webhook/forms` — アンケート集計受信
- `POST /webhook/checkin` — 参加者チェックイン受信

**Request 例**

```json
{
  "location": { "address": "横浜市瀬谷区＊＊＊", "lat": 35.47, "lng": 139.49 },
  "participants": {
    "total": 120,
    "children": 25,
    "elderly": 18,
    "wheelchair": 3,
    "languages": ["ja", "en"]
  },
  "hazard": {
    "types": ["earthquake", "fire"],
    "drill_date": "2025-10-12",
    "indoor": true,
    "nighttime": false
  },
  "constraints": { "max_duration_min": 45, "limited_outdoor": true },
  "kb_refs": ["kb://yokohama_guideline", "kb://shelter_rules"]
}
```

---

## エージェント設計（要点）

- **Coordinator**: 入力 → 要件分解 → シナリオ候補 → ハンドオフ。
- **Scenario**: 台本(MD)/役割(CSV)/導線(GeoJSON)を生成。
- **Safety**: ガイドライン適合チェック（根拠アンカー必須）。
- **Content**: ポスター(Imagen)・60 秒 VTR(Veo)・多言語素材の生成。

### 共通スキーマ（抜粋）

```json
{
  "Location": {
    "address": "string",
    "lat": "number",
    "lng": "number",
    "site_map_url": "string",
    "geojson": "object"
  },
  "Participants": {
    "total": "int",
    "children": "int",
    "elderly": "int",
    "wheelchair": "int",
    "languages": ["string"]
  },
  "HazardSpec": {
    "types": ["earthquake", "fire", "flood", "tsunami", "landslide"],
    "drill_date": "date",
    "indoor": "bool",
    "nighttime": "bool"
  },
  "Assets": {
    "script_md": "string",
    "roles_csv": "string",
    "routes": [
      {
        "name": "string",
        "points": [{ "lat": 0, "lng": 0, "label": "A" }],
        "accessibility_notes": "string"
      }
    ],
    "poster_prompts": ["string"],
    "video_prompt": "string",
    "video_shotlist": [{}],
    "languages": ["string"]
  },
  "KPIPlan": {
    "targets": {
      "attendance_rate": 0.6,
      "avg_evac_time_sec": 300,
      "quiz_score": 0.7
    },
    "collection": ["checkin", "route_time", "post_quiz", "issue_log"]
  }
}
```

---

## セットアップ

### 前提

- GCP プロジェクト / Billing 有効
- Vertex AI, Artifact Registry, Cloud Run, Pub/Sub, Firestore, GCS 有効化
- Node.js 20+, Python 3.11+

### 環境変数（`.env` サンプル）

```
GCP_PROJECT=your-project
REGION=asia-northeast1
FIRESTORE_DB=townready
GCS_BUCKET=gs://your-bucket
VAI_LOCATION=asia-northeast1
GEMINI_MODEL=gemini-1.5-pro
GEMINI_ENABLED=false
KB_DATASET=kb_default
PUBSUB_TOPIC=townready-jobs
# Vertex AI Search (KB)
KB_SEARCH_LOCATION=global
KB_SEARCH_COLLECTION=default_collection
KB_SEARCH_DATASTORE=${KB_DATASET}
# Optional (Push OIDC 検証)
# PUSH_VERIFY=true
# PUSH_AUDIENCE=https://<WORKER_URL>/pubsub/push
# PUSH_SERVICE_ACCOUNT=townready-api@your-project.iam.gserviceaccount.com
# 署名URL/リトライ
SIGNED_URL_TTL=3600
RETRY_MAX_ATTEMPTS=3
```

### ローカル起動（例）

```bash
# API
cd api && uvicorn app:app --reload --port 8080
# Web
cd web && npm i && npm run dev -- --port 3000
# Worker（任意）
cd workers && uvicorn server:app --reload --port 8081
```

### デプロイ（Cloud Run, 例）

```bash
# API
gcloud builds submit --tag asia-northeast1-docker.pkg.dev/$GCP_PROJECT/app/api:latest api/
gcloud run deploy townready-api \
  --image=asia-northeast1-docker.pkg.dev/$GCP_PROJECT/app/api:latest \
  --region=$REGION --allow-unauthenticated

# Web
gcloud builds submit --tag asia-northeast1-docker.pkg.dev/$GCP_PROJECT/app/web:latest web/
gcloud run deploy townready-web \
  --image=asia-northeast1-docker.pkg.dev/$GCP_PROJECT/app/web:latest \
  --region=$REGION --allow-unauthenticated
```

---

### デプロイ（スクリプト利用, 推奨）

```bash
# Worker（Artifact Registry build + Cloud Run deploy）
./infra/deploy_worker.sh \
  --project "$GCP_PROJECT" --region "$REGION" \
  --sa "townready-api@${GCP_PROJECT}.iam.gserviceaccount.com"

# API（Artifact Registry build + Cloud Run deploy）
./infra/deploy_api.sh \
  --project "$GCP_PROJECT" --region "$REGION" \
  --sa "townready-api@${GCP_PROJECT}.iam.gserviceaccount.com"

# Pub/Sub Push と Worker OIDC の URL 同期（status.url に揃える）
./infra/sync_worker_push.sh \
  --project "$GCP_PROJECT" --region "$REGION" \
  --service townready-worker \
  --subscription townready-jobs-push \
  --sa "townready-api@${GCP_PROJECT}.iam.gserviceaccount.com" \
  --verify true --set-basics-env --dotenv ./.env
```

同期スクリプトは Cloud Run の `status.url` を唯一の正として、Pub/Sub の `pushEndpoint`/`audience` と Worker の `PUSH_*` を同一 URL にそろえます。

### 動作確認（MVP・ジョブフロー）

```bash
# 1) プラン生成をキック（例）
curl -sS -X POST \
  -H 'Content-Type: application/json' \
  -d @- https://<YOUR_API_SERVICE>/api/generate/plan <<'JSON'
{
  "location": { "address": "横浜市瀬谷区＊＊＊", "lat": 35.47, "lng": 139.49 },
  "participants": { "total": 120, "children": 25, "elderly": 18, "wheelchair": 3, "languages": ["ja", "en"] },
  "hazard": { "types": ["earthquake", "fire"], "drill_date": "2025-10-12", "indoor": true, "nighttime": false },
  "constraints": { "max_duration_min": 45, "limited_outdoor": true },
  "kb_refs": ["kb://yokohama_guideline", "kb://shelter_rules"]
}
JSON

# => {"job_id":"...","status":"queued"}

# 2) ジョブ状態を確認
curl -sS https://<YOUR_API_SERVICE>/api/jobs/<job_id>

# Worker のヘルス確認（Cloud Run URL）
curl -i https://<YOUR_WORKER_SERVICE>/health   # 200 で OK
```

Push 配信（Pub/Sub → Worker）は Cloud Run URL の `/pubsub/push`（POST）へ設定します。

※ ヘルスチェックは `/health` を利用してください（`/healthz` は環境により 404 になる場合があります）。

### いま実装されているジョブ処理（概要）

- plan: 入力からシナリオ候補・KPI プラン・受け入れ条件を生成（Firestore 保存）
- scenario: 台本(Markdown)/役割(CSV)/ルート(JSON)を生成し GCS に保存（`assets.*_uri`/`*_url` 付与）
- safety: ルールベースの安全指摘を返却（KB 検索のヒットを添付）
- content: ポスター/動画用プロンプトとショットリストを生成し GCS に保存（署名URL付与）
- 全タスクは Pub/Sub 経由で Worker が処理（冪等・自動連鎖・指数バックオフ）
- Push OIDC 検証（任意）: `PUSH_VERIFY=true` で有効化

### IAM（最低限）

- API 実行 SA: `roles/datastore.user`, `roles/pubsub.publisher`
- Worker 実行 SA: `roles/datastore.user`, `roles/storage.objectAdmin`（対象バケット）, `roles/iam.serviceAccountTokenCreator`

### トラブルシューティング

- ジョブが `queued` のまま: Pub/Sub の `pushEndpoint`/`audience` と Worker の `PUSH_AUDIENCE` を同一 URL に。`./infra/sync_worker_push.sh` を実行
- 手動 `curl $WORKER_URL/pubsub/push` が `ack_error: unauthorized`: `PUSH_VERIFY=true` では正常。切り分けで一時 `PUSH_VERIFY=false` に
- Firestore 書込エラー: API の環境変数（`GCP_PROJECT`/`FIRESTORE_DB`）と SA 権限を確認
- GCS にファイルが出ない: 保存対象は scenario/content。Worker の `GCS_BUCKET` と権限を確認

## セキュリティ & プライバシー

- 名簿等の**個人情報は収集せず**、チェックインは匿名 ID/集計単位で保存。
- GCS/Firestore の**リージョン内保管**、アクセスは最小権限（IAM）。
- 生成物に**注意書きと根拠**を付与。レビュー未通過のシナリオは配布不可。

---

## ライセンス

- 仮: Apache-2.0（検討中）

---

## 開発ロードマップ（MVP → α）

1. Schema & Contract / JSON 出力強制
2. Coordinator/Scenario/Safety/Content の順で実装
3. Imagen/Veo を**ダミー → 本番 API**に段階的切替
4. KPI ダッシュボード・改善提案の自動化

---

# docs/TownReady_Spec.md

## 1. 背景と課題

- 訓練の**企画工数が高い**（台本・役割・導線・掲示の個別作成）。
- **参加と学習定着が弱い**（若年層/多言語/視覚教材不足）。
- **評価 → 改善のループ不全**（ログ・KPI が残らない）。

## 2. ターゲット（初期アーリーアダプター）

- 表彰実績や実証に前向きな **自治会・地域ネットワーク**。
- 多言語/体験型訓練を重視する **自治体 防災担当**。
- 教育効果を検証したい **学校・大学**。
- 年数回訓練を回す **ビル/エリア管理**。

## 3. JTBD

- **状況**: 年 1–数回の訓練を企画、参加属性・場所が毎回変わる。
- **動機**: 現場で迷わない訓練を短時間で作り、参加率と理解度を上げたい。
- **障害**: 手作業/多言語/配慮/根拠・KPI 不足。
- **完了定義**: “地域専用の一式”＋“KPI 測定”＋“次回改善案”。

## 4. ソリューション概要

- **4 エージェント連携**（Coordinator/Scenario/Safety/Content）
- **Imagen**: A4 ポスター多言語生成 / **Veo**: 60 秒 VTR 生成
- **KB**: ガイドライン・避難所・施設情報を Vertex AI Search に格納
- **KPI**: 参加率/到達時間/理解度 → 改善提案

## 5. 非機能要件（MVP）

- **速度**: 入力 → 生成 ≤10 分
- **正確性**: 出典リンク・KB アンカー必須、自治体様式互換
- **安全性**: PII 最小化、監査ログ、レビュー未通過は配布不可

## 6. エージェント I/O（詳細）

### 6.1 Coordinator（入力 →PlanSpec）

- 入力: Location / Participants / Hazard / constraints / kb_refs
- 出力: PlanSpec（シナリオ候補、KPIPlan、必須要件、ハンドオフ）
- 事前検証: 欠損項目、時間超過、屋外制限等

### 6.2 Scenario（PlanSpec→ScenarioBundle）

- 台本(Markdown) / 役割(CSV) / 導線(GeoJSON)
- ルート: 車椅子・子ども対応、分刻みタイムライン

### 6.3 Safety（ScenarioBundle→SafetyReview）

- severity / issue / fix / 根拠(KB アンカー)
- patched（差し替え済み）を返却

### 6.4 Content（patched→ContentPackage）

- ポスター（A4, 言語別, 注意書き）
- 60 秒 VTR（字幕日英、ショットリストに沿う）
- script.md / roles.csv / geojson のエクスポート

#### 6.x JSON 例

```json
{
  "scenarios": [
    {
      "id": "S1",
      "title": "地震→火災",
      "objectives": ["一次避難導線確認", "初期消火"],
      "languages": ["ja", "en"]
    }
  ],
  "acceptance": {
    "must_include": ["要配慮者ルート", "多言語掲示", "役割表CSV"],
    "kpi_plan": {
      "targets": {
        "attendance_rate": 0.6,
        "avg_evac_time_sec": 300,
        "quiz_score": 0.7
      },
      "collection": ["checkin", "route_time", "post_quiz"]
    }
  },
  "handoff": { "to": "Scenario Agent", "with": { "scenario_id": "S1" } }
}
```

## 7. API 詳細（OpenAPI 抜粋）

```yaml
POST /api/generate/plan:
  requestBody: { application/json: {} }
  responses:
    "200": { application/json: { job_id: string, status: string } }
POST /api/generate/scenario:
POST /api/review/safety:
POST /api/generate/content:
GET  /api/jobs/{job_id}:
POST /webhook/forms:
POST /webhook/checkin:
```

## 8. データモデル（Firestore）

- `workspaces/{ws}/drills/{drill}`: 入力、言語、ハザード
- `jobs/{job}`: タイプ、ステータス、出力 URI
- `assets/{drill}`: `poster_*`, `video_*`, `script_md`, `roles_csv`
- `metrics/{drill}`: `checkins[]`, `quiz[]`, `issue_log[]`

## 9. セキュリティ/プライバシー/運用

- **データ最小化**: 個人名を扱わない。匿名 ID。
- **IAM 最小権限**: サービス間は SA ごとにスコープ限定。
- **監査/レート制限**: 生成 API はプロジェクト/WS 単位のクォータ管理。
- **アセット署名 URL**: 配布期限を短く。

## 10. テスト戦略

- **Contract Test**: JSON Schema で I/O バリデーション。
- **静的検証**: ルート自己交差/屋外禁止/段差注意を事前検出。
- **E2E**: 入力 → 一式生成 →DL→Webhook 取込 → 改善提案まで。

## 11. デモシナリオ（90 秒）

1. 住所と属性を入力 → 3 つのシナリオ候補
2. “地震 → 火災”を選択 → 台本/ルート自動生成
3. Safety が赤入れ → 一括反映
4. クリックで**ポスター/60 秒 VTR**生成 → DL & 印刷
5. 訓練後に QR チェックイン/フォーム受信 → KPI & 改善提案

## 12. ロードマップ

- α: 多言語(ja/en), 地震/火災, A4 ポスター, 60 秒 VTR
- β: 浸水/土砂対応、視覚支援、エリア横断テンプレ、外部 SaaS 連携

## 13. ライセンス/クレジット

- 仮: Apache-2.0
- 生成物の権利表示は出力に自動付与（注意書き含む）
