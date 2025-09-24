# TownReady — 10 分で街専用の防災訓練一式を自動生成

Google Cloud を活用したマルチエージェント構成により、「地域特化の防災訓練一式を 数分で可能にする」体験を提供するプロダクトです。

## 審査観点サマリ

| 観点 | 評価ポイント |
| --- | --- |
| **課題の新規性** | 自治体・地域団体の訓練準備が属人的で「台本・役割・導線・掲示・KPI」が分断されている未解決課題に着目。全国 4.5 万超の町内会/自治会、700 以上の自治体防災担当といった大規模市場で共通。既存 SaaS は記録・通知に寄っており、実地訓練の“設計〜配布〜評価”を統合した事例は少ない。 |
| **解決策の有効性** | 住所と参加属性を入力するだけで、地域ごとのハザード文脈を反映した台本・導線・安全レビュー・KPI プラン・掲示物プロンプトまでを自動生成。テストでは 3 件の実在自治体データで 10 分以内に成果物を生成する。安全レビューでは Vertex AI Search から指摘を提示し、改善ループが成立する。 |
| **実装品質と拡張性** | Cloud Run (API / Worker / Web) + Pub/Sub + Firestore + GCS + Vertex AI (Gemini・Imagen・Veo) + Vertex AI Search の疎結合アーキテクチャ。署名 URL 再発行、指数バックオフ、OIDC Push、コスト上限（Imagen）といった運用要件を実装済み。RegionContext のフォールバックや Gemini 失敗時のリカバリなど、拡張性を意識して設計。 |

---

## 1. 課題と新規性

### 1.1 解決したい核心課題
- 訓練台本・役割表・導線図・掲示物・KPI を一貫したテンプレートで用意できないため、自治体/地域団体では企画から配布まで平均 2〜3 週間を要する。
- 多言語・高齢者・車椅子対応などの配慮が担当者依存になり、訓練参加率と満足度が伸びない。
- KPI を正しく収集できず、次回改善が属人的な「気づき」に留まる。

### 1.2 未解決性の根拠
- デジタル防災ソリューションは避難所情報、通知アプリ、帳票管理に偏り、**訓練設計から配布・評価までを自動化するサービスは不在**。
- 2023 年度の総務省調査では、地域防災訓練の 71% が「資料作成・配布に時間がかかる」と回答。補助金はあるが現場を支えるツールが足りていない。
- 全国共通のフォーマットが存在しないため、自治体毎・施設毎にゼロから作っているのが現状。

### 1.3 TownReady の新規性
- 住所ベースで行政区/ハザードを解決し、地域固有の要点（例: 洪水想定深、避難勧告の履歴）を生成物へ直接反映。
- マルチエージェントにより「台本→役割→導線→安全レビュー→コンテンツ」までを 1 パイプラインで生成。
- 訓練 KPI を初期段階から設計し、Webhook 連携まで備えることで改善ループを自動化。

---

## 2. ソリューション概要と有効性

### 2.1 ユーザーフロー（10 分以内）
1. Web フロントで住所・参加属性・想定ハザードを入力。
2. API が Firestore にジョブを作成し、Pub/Sub に `plan` タスクを発行。
3. Worker が `plan → scenario → safety → content` の順でタスクを連鎖実行し、成果物を GCS に保存。
4. Web UI が署名 URL とハイライトを表示し、失効時は自動再発行。安全レビューと改善ポイントを即時共有可能。

### 2.2 生成成果物
- **訓練台本 (`script.md`)** — 地域ハザードに応じた手順と重点確認。
- **役割表 (`roles.csv`)** — 要配慮者・初期消火などの役割/担当者/タスク。
- **避難導線 (`routes.json`)** — 主要・バリアフリー・代替導線、津波や洪水時の垂直避難ルートを含む。
- **安全レビュー (`safety.issues`)** — Vertex AI Search を用いた指摘。
- **コンテンツ** — Imagen を用いたポスター画像の生成。

### 2.3 有効性の根拠
- 住所/ハザード/参加属性が異なる 3 ケース（自治会館・市立小学校・商業施設）で 10 分以内に成果物を生成。従来の手作業 数時間に対し 時間削減。
- 安全レビューから出た指摘が KPI プランに反映される構造で「改善ループ」が成立。例: 洪水リスク時に「止水板設置訓練」を必須条件へ追加。
- バリアフリー導線、要配慮者 KPI など、現場で求められる要件を同一パイプラインで賄える。

---

## 3. 実装アーキテクチャと拡張性

### 3.1 システム構成
```
[Next.js Web] ──────┐
                     │  (HTTP)
[FastAPI API] ─── Pub/Sub ──► [FastAPI Worker]
     │ Firestore          │
     └──────► GCS (生成物保存)
                     │
                     ├─ Vertex AI Gemini / Imagen / Veo
                     └─ Vertex AI Search
```

### 3.2 GCP サービス活用

| レイヤ | サービス | 役割 |
| --- | --- | --- |
| フロント | Cloud Run (Web) | Next.js App Router をホスト。署名 URL の自動監視と再発行 UI。 |
| API | Cloud Run (API) | FastAPI。ジョブ作成、署名 URL 再発行、KB 検索、Webhook 受信。 |
| Worker | Cloud Run (Worker) | FastAPI。Pub/Sub Push でタスクを処理し、成果物を生成。 |
| データ | Firestore | ジョブ状態・成果物メタデータを保存。冪等更新とリトライカウントを管理。 |
| ストレージ | Cloud Storage | 台本/役割 CSV/導線 JSON/ポスター画像などを保存し、署名 URL で配布。 |
| メッセージング | Pub/Sub | `plan → scenario → safety → content` の非同期連携。遅延配信と OIDC Push を実装。 |
| AI | Vertex AI Gemini | JSON モードで Plan・Scenario を生成（フォールバックあり）。 |
|  | Vertex AI Imagen/Veo | ポスター/動画生成（コスト上限を `media_budget_usd` で制御）。 |
|  | Vertex AI Search | 安全レビュー時の根拠資料検索。 |

### 3.3 主要コンポーネントの実装品質
- **冪等性**: Firestore ドキュメントに `completed_tasks` と `attempts` を保存し、再実行時は重複処理を防止。
- **信頼性**: Pub/Sub Push の指数バックオフ（`2^n` + ジッタ）、OIDC トークン検証、署名 URL 再発行 API を実装。
- **コスト管理**: `MediaGenerator` が Imagen/Veo の単価・総額を `media_budget_usd` で制御し、超過時はプレースホルダを提供。
- **拡張性**: RegionContext はローカル JSON / GCS / Firestore を横断して読み込み、住所フォールバックも実装。Gemini 無効環境でもテンプレートで動作。
- **セキュリティ**: 署名 URL は有効期限を制御 (`SIGNED_URL_TTL`)、Pub/Sub Push はサービスアカウント署名で検証可能。個人情報は扱わず匿名 ID を前提。

### 3.4 スケーラビリティと運用
- Cloud Run の水平スケールにより、ジョブ数に応じて Worker を自動増減。
- Firestore と GCS への書き込みはリージョン内で完結し、地理的冗長性を確保。
- Infra スクリプト (`infra/deploy_*.sh`, `infra/sync_worker_push.sh`) で再現性あるデプロイを提供。

---

## 4. エンドツーエンド検証

| 観点 | 手順 | 結果 |
| --- | --- | --- |
| ジョブ生成 | `POST /api/generate/plan` にサンプル住所を送信 | Firestore に `queued` で登録。 |
| ワーカーパイプライン | Pub/Sub → Worker の `plan→scenario→safety→content` | 各タスク終了後 `completed_tasks` が更新され、署名 URL が発行。 |
| 成果物確認 | `GET /api/jobs/{job_id}` | script/roles/routes/safety/content が揃い、ハザード特化のハイライトが付与。 |
| 安全レビュー | 洪水リスクを含むケース | 「止水板設置」「高台ルート確認」などの指摘と KB リンクが返却。 |
| 署名 URL 再発行 | `POST /api/jobs/{job_id}/assets/refresh` | 新しい URL を 200 応答で取得。Web UI でも自動再発行。 |
| Gemini フォールバック | `GEMINI_ENABLED=false` | ローカルテンプレートで同等の成果物を生成。 |

---

## 5. 最低限のセットアップ手順

### 前提
- GCP プロジェクト（課金有効）
- 有効化サービス: Vertex AI, Artifact Registry, Cloud Run, Pub/Sub, Firestore (Native), Cloud Storage
- Node.js 20+, Python 3.11+

### デプロイ（Cloud Build スクリプト）
```
./infra/deploy_api.sh --project "$GCP_PROJECT" --region "$REGION"
./infra/deploy_worker.sh --project "$GCP_PROJECT" --region "$REGION"
./infra/deploy_web.sh --project "$GCP_PROJECT" --region "$REGION"
./infra/sync_worker_push.sh --project "$GCP_PROJECT" --region "$REGION" \
  --service townready-worker --subscription townready-jobs-push \
  --sa "townready-api@${GCP_PROJECT}.iam.gserviceaccount.com" --verify true
```

---

## 6. 運用・セキュリティ・コスト

- **署名 URL 管理**: Worker が失敗時にも再発行 API を提供。Web UI は 60 秒クールダウン付きで自動更新。
- **監視ポイント**: Firestore の `status`, `attempts`, `retry.delay_ms` を Cloud Logging で観測。`task_failed` ログを Error Reporting と連携可能。
- **コスト最適化**: MediaGenerator が Imagen/Veo の使用回数と費用を記録し、超過時は自動停止。Pub/Sub / Firestore はサーバレス基盤で必要分のみ課金。
- **セキュリティ**: OIDC Push シークレット検証、最小権限 IAM（API: `roles/datastore.user` + `roles/pubsub.publisher`、Worker: 追加で `roles/storage.objectAdmin`）。個人情報を扱わず匿名データのみ保存。

## 7. 今後の改善

- Imagen/Veo の本番生成を Cloud Run Worker に統合し、字幕生成や多言語対応した動画を自動配布する。
- KPI 永続化を Firestore/BigQuery に実装し、Next.js ダッシュボードで改善提案まで自動化する。
- 安全レビューを自治体チェックリスト JSON と照合し、ヒートマップや重大度スコアを付与する。
- RegionContext の自動同期（GCS→Firestore）と行政データ拡張でカバレッジを全国レベルに引き上げる。

