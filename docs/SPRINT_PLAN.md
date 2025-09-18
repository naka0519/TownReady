# TownReady スプリント計画と進捗トラッカー

このドキュメントは、TownReady の MVP 実装に向けたスプリント計画・タスク分解・進捗管理を記録します。実装・検証の観点で随時更新してください。

## 0. 概要（現行 MVP 方針）

- 住所/属性/ハザードから“その街専用”の訓練一式を自動生成（台本/役割/導線/ポスター/60 秒 VTR/KPI）。
- アーキテクチャ: Next.js（Web）/ FastAPI（API）/ Worker（Pub/Sub Push）/ Firestore（メタ）/ GCS（生成物）/ Vertex AI（Gemini/Imagen/Veo/KB）。

## 1. 現在の達成状況（Done）

- API/Worker ヘルス: OK（`api/app.py:/health`, `workers/server.py:/health`）
- Firestore 書き込み: OK（`services/firestore_client.py` 及び `GET /health/firestore_write`）
- Pub/Sub Push 配信: OK（`workers/server.py:/pubsub/push`）
- ジョブフロー: queued → processing → done（Firestore 更新）
- Worker: タスク連鎖（plan→scenario→safety→content）・タスク単位の冪等化・任意の OIDC 検証（`_verify_push`）
- Scenario/Content: GCS 書き込み＋署名 URL（IAM SignBlob, TTL=3600s）を安定発行（`services/storage_client.py`）
- 署名 URL 再発行: 失効時の再発行エンドポイント＋最小 UI（`POST /api/jobs/{job_id}/assets/refresh`, `/view/jobs/{job_id}`）
- 最小 UI: `/view/start` からのジョブ起動、ジョブ画面でのリンク/Safety 表示/再発行ボタン
- Worker リトライ: 指数バックオフ＋ジッタ、遅延処理（`attributes.delay_ms`）とエラーログ（`task_failed`）
- Push 同期: Pub/Sub pushEndpoint/audience/SA と Worker PUSH\_\* を `infra/sync_worker_push.sh` で同期
- Web 最小(Next.js): 入力フォーム → ジョブ起動 → ジョブ詳細（ポーリング/リンク/Safety/再発行）を実装。API は Next の Route Handlers でプロキシ（`web/src/app/api/*`）、API 側は CORS 許可（`CORS_ALLOW_ORIGINS`）
 - Web UX 強化（初期）: エラー詳細表示、ダウンロード UI（download 属性/URL コピー/署名 URL の有効期限表示）を実装
 - Web UI/UX 改良（実装分）: 進捗タイムライン（plan→scenario→safety→content）表示、署名 URL 期限切れの自動再発行（60s クールダウン・トースト通知付き）、各成果リンクの QR 表示/クリップボードコピー、aria-live/role=alert などアクセシビリティ補助
- Web CI/CD（初期）: `infra/cloudbuild.web.yaml` を追加し、`infra/deploy_web.sh` でビルド/デプロイ。GitHub/CSR 向けトリガー作成スクリプト（`infra/create_web_trigger_github.sh`, `infra/create_web_trigger_csr.sh`）を追加
- Gemini 初期導入: Worker に Vertex AI (Gemini) を段階導入。`services/gemini_client.py` で JSON 厳密出力（response_mime_type=application/json）・パースフォールバック・タイムアウト/再試行を実装。`us-central1 × gemini-2.0-flash` で Plan/Scenario 生成を確認
- Web UX 強化: エラー詳細表示、ダウンロード UI（download 属性/URLコピー/署名URLの有効期限表示）を実装
 - Gemini 初期導入: Worker に Vertex AI (Gemini) を段階導入。`services/gemini_client.py` で JSON 厳密出力（response_mime_type=application/json）とフォールバックを実装。`us-central1 × gemini-2.0-flash` で Plan/Scenario 生成を確認

## 2. 直近の課題・差分（Gap）

- Contract Test の CI 組み込み（生成・検証は実施済）
- Web 最小は実装済。UX 磨き込み（エラー表示/QR/ダウンロード UI）と Web CI/CD（Cloud Build/デプロイスクリプト）が未整備
- KPI 集計（Webhook 格納・可視化）未実装
- アラート運用: リトライは実装済。Log-based Alert / Error Reporting の通知設計（優先度低）
- KB 運用改善（文書拡充・スニペット表示・自動再取込）
- Gemini 運用: モデル/リージョンの固定化（例: `us-central1 × gemini-2.0-flash`）、タイムアウト/再試行、出力スキーマ拘束の強化
- Web UI/UX モダン化: コンポーネント設計・アクセシビリティ（キーボード操作/コントラスト/ARIA）・多言語 UI・レスポンシブ最適化・PWA（任意）
- Web CI/CD 改良: 自動デプロイ（post-build step）/ 簡易スモーク（/api/generate/plan → /api/jobs 200）/ ステージング環境

## 3. フェーズ別スプリント計画（MVP→α）

### Phase 1（バックエンド堅牢化 / 連鎖 / 配布）

- 契約強化: Pydantic/JSON Schema による I/O バリデーション徹底（Contract Test）
- generate/content の修正: Pub/Sub 発行と正常なレスポンス返却
- ジョブ連鎖: Worker 内で次タスクを自動キック（停止条件/リトライ方針も定義）
- 署名 URL: GCS Signed URL 生成と TTL 運用、`assets_index.json` で集約
- Safety×KB: KBSearch 連携により issues に根拠（出典/タイトル/スニペット）付与（最小）

### Phase 2（AI 本実装 / 生成品質）

- Coordinator/Scenario のテキスト生成を Gemini で実装（プロンプト設計・制約出力）
- Imagen/Veo のダミー → 本番 API 段階移行（ジョブ化・長時間タスクの保存/参照）
- Safety のルール/チェック拡充（ハザード/配慮/屋内外/自己交差検出）

### Phase 3（体験/KPI / 改善ループ）

- Web: 入力 → ジョブ起動 → ステータス監視 → 成果 DL（署名 URL）
- Webhook（checkin/forms）→ Firestore 保存 → KPI 集計 API → ダッシュボード
- 改善提案（前回ログ/KPI からの改善点サジェスト）

## 4. Next Actions（直近の実装順）

1. Web UI/UX モダン化: デザイン/アクセシビリティ/多言語/レスポンシブ/（任意で）PWA・QR 表示
2. アラート追加: Log-based Alert（`task_failed`）/ Error Reporting の最小通知（優先度低）
3. Gemini 継続: モデル/リージョンの固定（flash）とプロンプト/Schema 拘束の強化、タイムアウト/再試行方針の明確化（フォールバック維持）
4. Imagen/Veo 本番 API: ポーリング/保存/URI 格納（段階導入）
5. KB 運用改善: 文書拡充とスニペット精度検証、定期再取込
6. Web CI/CD 改良: GitHub/CSR トリガーの本番運用化（main/PR）と post-build 自動デプロイ/スモーク

## 5. タスク分解（チェックリスト）

### Phase 1

- [x] generate/content の Pub/Sub 発行と return 修正（`api/app.py`）
- [x] Worker で次タスク発行（`workers/server.py`）
- [x] `services/storage_client.py` に署名 URL 取得を追加（配布 TTL/権限）
- [x] Safety×KB 最小連携（`services/kb_search.py` を Worker から呼び出し）
- [x] JSON Schema 生成＆Contract Test（`schemas/generate_json_schema.py` 実行／Pydantic 検証）
- [x] README/.env の整合更新（PUSH/KBS 配列）
- [x] CI 設定追加（`infra/cloudbuild.tests.yaml`）/手動実行で成功
- [x] Cloud Build トリガー作成（main push/PR 時に自動実行, TownReady-CI）
- [x] KB 設定の実環境反映（.env KB\_\* 反映／API 再デプロイ／GCS→DE 取り込み／検索ヒット確認）
- [x] 署名 URL 運用改善（TTL env 化/Content-Disposition 付与/失効時の UX: 再発行 API+UI）
- [x] Worker リトライ/バックオフ（指数＋ジッタ, `delay_ms` 適用, エラーログ追加）
- [x] E2E スモークスクリプト追加（`scripts/e2e_smoke.sh`）
- [x] KB 検索のスニペット対応（対応ライブラリで有効化）
- [x] 連鎖の最小リトライ実装（`attempts` 記録/閾値以下で再投入, `completed_order` 追加）

### Phase 2

- [ ] Gemini による Coordinator/Scenario 生成（プロンプト/出力拘束）【初期導入済（Plan/Scenario 生成の疎通確認）】
- [ ] Imagen/Veo 本番 API 連携（ポーリング/保存/URI 格納）
- [ ] Safety ルール拡充（自己交差/屋外禁止/段差）

### Phase 3

- [x] Web フロント最小（フォーム/進捗/成果 DL/再発行, Next.js + Route Handlers プロキシ）
- [ ] Web 磨き込み（UX/QR/ダウンロード UI）
- [ ] Web CI/CD（Cloud Build + デプロイスクリプト）
- [ ] Webhook→KPI 集計 API→ ダッシュボード
- [ ] 改善提案ループ（前回ログ参照）

## 6.1 検証ステップ（抜粋）

- 署名 URL（Content）: `POST /api/generate/content` → `result.*_url` が非 null → `curl -I "$URL"` が 200
- 署名 URL（Scenario）: plan 連鎖後の `assets.*_url` で `curl -I` が 200
- 連鎖完了: `completed_tasks` が `["plan","scenario","safety","content"]`
- KB 連携: safety の `issues[].kb_hits` が 0–2 件
- ログ監視: Worker の `signed_url_failed_*` が出ないこと（gcloud logging read フィルタ使用）
- KB 検索 API: `curl -sS --get "$API_URL/api/kb/search" --data-urlencode "q=横浜 避難" --data-urlencode "n=2" | jq .`（.env の KB\_\* 反映・API 再デプロイ済み、データストアに `kb/` 配下の .txt/.html/.pdf 等が取り込まれていること）
- ContractTest スクリプト: `bash scripts/contract_test.sh`（Schema 生成/Pydantic 検証/plan スモーク）
- E2E スモーク: `bash scripts/e2e_smoke.sh`（タスク 4 到達、Scenario/Content 署名 URL の HEAD が 200）
- 連鎖順/リトライ: `curl -sS "$API_URL/api/jobs/$JOB_ID" | jq '.completed_order, .attempts, .retry'`（順序配列が実行順、エラー未発生なら attempts は `{}`/retry は `null`）
- 署名 URL 再発行: `curl -sS -X POST "$API_URL/api/jobs/$JOB_ID/assets/refresh" | jq '.status,.assets_refresh_count'` → `ok`/カウント増加
- UI 最小: `curl -sS "$API_URL/view/start" | head -n5` / `curl -sS "$API_URL/view/jobs/$JOB_ID" | grep -o 'btnRefresh'`
- Push OIDC 同期: `./infra/sync_worker_push.sh --project "$GCP_PROJECT" --region "$REGION" --service townready-worker --subscription townready-jobs-push --sa "townready-api@${GCP_PROJECT}.iam.gserviceaccount.com" --verify true --set-basics-env --dotenv ./.env`
- 遅延処理: Pub/Sub publish 時 `--attribute type=content,delay_ms=5000` を付与し、処理遅延を確認
- 失敗 → バックオフ: Worker の `GCS_BUCKET` を一時不正化 → 新規ジョブで `content` 実行 →`attempts`/`retry.delay_ms` 記録と `task_failed` ログを確認
  - Web プロキシ: `curl -i -sS -X POST "$WEB_URL/api/generate/plan" -H 'Content-Type: application/json' --data-binary @tmp/plan.json` が 200/JSON。`curl -sS "$WEB_URL/api/jobs/$JOB_ID" | jq .` が取得可能
  - CORS: API に `CORS_ALLOW_ORIGINS=$WEB_URL` を設定し、ブラウザからの直接 API コールが必要な場合に許可
  - Web UI/UX（タイムライン）: `/jobs/{JOB_ID}` で plan→scenario→safety→content の各ステップが「実行中/完了/未着手」の色分けで表示される
  - Web UI/UX（自動再発行）: SIGNED_URL_TTL を短時間に設定してデプロイ → 署名 URL が (expired) 表示になった際、60 秒クールダウン付きで自動再発行され、トースト「署名 URL を自動再発行しました」が 3 秒表示される
  - Web UI/UX（QR/コピー/有効期限）: 各リンク横の「コピー」ボタンで URL がクリップボードへ保存、「QR」ボタンで QR 画像が表示、右側の `(expires in ~Xm)` が推移する。HEADで 200 を確認: `curl -sSI "$(curl -sS $API_URL/api/jobs/$JOB_ID | jq -r '.assets.script_md_url')" | head -n1`
  - Web ビルド/デプロイ（CI/CD）: `gcloud builds triggers run 'TownReady-Web-CI' --project "$GCP_PROJECT" --branch=main --substitutions _IMAGE_URI="${REGION}-docker.pkg.dev/$GCP_PROJECT/app/web:latest"` → 成功後 Cloud Run に手動/自動デプロイ
  - Web UI/UX: `/jobs/{JOB_ID}` で「リンク再発行」「download 属性」「URLコピー」「有効期限表示（expires in ~Xm）」が機能すること。フォームから開始 → 進捗/リンク表示の一連が GUI で確認できること
  - Gemini（設定）: `gcloud run services update townready-worker --region "$REGION" --update-env-vars GEMINI_ENABLED=true,GEMINI_MODEL=gemini-2.0-flash,VAI_LOCATION=us-central1`
  - Gemini（検証）: 新規ジョブ後に `curl -sS $API_URL/api/jobs/$JOB_ID | jq '.results.plan, .assets.script_md'`。Plan の `location` が消え、Scenario がテンプレから生成文へ変化。失敗時は Worker ログに `gemini_*_failed`、処理はフォールバックで継続

## 8. Web UI/UX モダン化計画（追加）

- 目的: ユーザが 1 分以内に「入力 → 生成 → ダウンロード」まで迷わず到達できる UI/UX を実現。
- 方針:
  - コンポーネント設計: 入力フォーム/進捗/成果/再発行/アラートを分離。状態管理を最小化（Polling 間隔や再試行を Settings 化）
  - アクセシビリティ: キーボード操作/ARIA/コントラスト比/フォントサイズ調整。エラーの画面内告知（role=alert）
  - 多言語: ja/en 切替（UI ラベル/説明/ボタン）。将来の追加言語に備えた辞書化
  - レスポンシブ: モバイル/タブレット/デスクトップで情報密度を調整（カード/アコーディオン）
  - PWA（任意）: ホームスクリーン追加/オフライン表示/基本キャッシュ
- 実装済み (v1):
  - 進捗タイムライン（plan→scenario→safety→content）
  - 署名 URL の自動失効検知 → 自動再発行（60s クールダウン）/トースト通知（3s）
  - 成果ダウンロード UI（download 属性/URL コピー/QR/有効期限表示）
  - アクセシビリティ補助（aria-live/role=alert/ボタン aria-label 等）

- 次の改良 (v2) TODO:
  - 署名 URL の自動失効検知 → 自動再発行/トースト通知
  - 成果ダウンロードの一括 zip（要検討: GCS 側でのアーカイブ or クライアント）
  - 進捗ビューのモダン化（タイムライン/タスク状態/リトライ表示）
  - QR 表示（成果物/ステータス共有用）

## 9. 実ユーザユースケースに基づく機能改良（追加）

- 代表シナリオ:
  - 自治会（高齢者/車椅子対応/多言語掲示）
  - 学校（学年別の役割/連絡網/ドリル直後のクイズ）
  - オフィス/商業施設（閉店時間帯/警備/館内放送）
- 改良案（例）:
  - 入力テンプレ: ユースケース選択で初期値を自動セット（役割/目標/KPI）
  - 役割テンプレ: 学校/自治会/オフィス向け CSV 雛形を切替
  - KPI 収集: QR チェックイン/ポストクイズの Webhook 連携（可視化ダッシュボード）
  - 多言語導線: シナリオ/ポスターの言語セットをユースケースで増減
  - 安全レビュー: ユースケース別ガイドラインの KB 断片を優先ヒット
- 検証:
  - ユースケース別の入力→生成→配布の所要時間（目標: 1 分以内に初回生成、10 分以内に一式）
  - 成果のダウンロード完了率/エラー率/再発行率（署名 URL の運用チューニング）
  - 事後アンケート（UI 可用性/理解度/改善点）
- CI トリガー（手動実行/ログ）:
  - 実行: `gcloud builds triggers run TownReady-CI --project "$GCP_PROJECT" --branch=main --substitutions=_API_URL="$API_URL"`
  - 一覧: `gcloud builds list --project "$GCP_PROJECT" --format='table(id,status,createTime)'`
  - ログ（Cloud Logging のみ）: `gcloud beta builds log --project "$GCP_PROJECT" --stream <BUILD_ID>`

## 6. 受け入れ基準（MVP）

- 入力 → 生成 → 配布まで 10 分以内（Imagen/Veo は段階導入可）
- Safety 出力に KB 根拠（少なくとも出典リンク/タイトル/スニペット）を含む
- 配布 URL は署名付き（期限付与）。Firestore に成果メタが保存される
- E2E スクリプトで疎通（API→ ジョブ → 結果 DL）を再現可能

## 7. 進捗ログ（更新テンプレート）

```
[YYYY-MM-DD]
- Done: （箇条書き）
- Issues: （課題/ブロッカー）
- Next: （次の着手）
```

初期エントリ:

```
[初期作成]
- Done: スプリント計画/Next Actions/チェックリストを作成
- Issues: generate/content の処理逸脱を修正対象として明記
- Next: generate/content の修正 → 連鎖実装 → 署名URL
```

更新エントリ:

```
[2025-09-13]
- Done: generate/content のPub/Sub発行と正常応答を修正; Workerの自動連鎖（plan→scenario→safety→content）＋タスク単位の冪等化を実装; Storageの署名URL生成を実装しScenario/Content出力にURL付与（ベストエフォート）
- Issues: Safety×KBの根拠アンカーは未実装; README/.env のPUSH/KBS追補未対応
- Next: Safety×KBの最小連携 → README/.env整合 → Contract Test/E2E最小疎通の追加
```

```
[2025-09-14]
- Done: 署名URLの安定発行を実装（IAM Credentials SignBlob, 必要スコープ付与, SAメール解決の明示化）。コンテンツ出力の `*_url` が 200 応答で確認済み
- Issues: TTL/ファイル名（Content-Disposition）/失効時UX の運用調整が未設計。Contract Test/E2E 手順の整備未了
- Next: Contract Test 着手 → E2Eスモーク手順の docs 追加 → 署名URL運用改善（TTL env, DL名）→ Web最小ビュー
```

```
[2025-09-15]
- Done: JSON Schema 生成と Pydantic による Contract Test（サンプルI/O）を実施。KB 検索APIをバージョン差異に対応（serving_config/data_store 両対応）し、デプロイスクリプトで KB_* 環境変数を Cloud Run へ引き渡すよう更新。GCS の `kb/` に .txt 文書を配置、Discovery Engine サービスエージェントへ `roles/storage.objectViewer` を付与し、取り込み・検索ヒットを確認。E2E スモーク/Contract Test スクリプトを追加し、署名URL 200・連鎖完了を確認
- Done(追記): Cloud Build トリガー「TownReady-CI」を作成。main への PR/push で `infra/cloudbuild.tests.yaml` を実行。Cloud Logging のみ出力でビルド成功を確認（`gcloud beta builds log --stream <BUILD_ID>`）
- Issues: KB のスニペット表示/文書拡充/再取込運用、連鎖リトライのバックオフ/通知
- Next: E2E スモークの CI 常時化（PR必須）→ KB 運用改善（スニペット/文書追加）→ リトライのバックオフ/通知

```

[2025-09-15 追加]

- Done: 署名 URL 再発行 API と最小 UI（`/view/jobs/{job_id}` の再発行ボタン, `/view/start`）を実装・検証。Worker に指数バックオフ＋ジッタ/`delay_ms`遅延処理/`task_failed` エラーログを実装。`infra/sync_worker_push.sh` で pushEndpoint/audience/SA と Worker PUSH\_\* を同期し、Cloud Run 上で E2E（署名 URL 200/再発行 OK/遅延 OK/連鎖 OK）を確認
- Issues: 通知運用（Log-based Alert/ Error Reporting）未設定、Web 最小（Next.js）未実装
- Next: Log-based Alert 設定 → Web 最小（Next.js） → Gemini/Imagen/Veo の段階導入

```
[2025-09-15 追加(2)]
- Done: Web最小（Next.js）を実装・デプロイ（フォーム→起動→詳細）。Next Route Handlers で API をプロキシ（`/api/generate/plan`, `/api/jobs/*` 等）。API 側は CORS 許可を追加。API 500 は Cloud Run 環境変数（GCP_PROJECT 等）欠落が原因で、再設定により復旧
- Issues: WebのUX（エラー表示/QR/ダウンロードUI）と CI/CD が未整備
- Next: Web 磨き込み＋CI/CD → Gemini/Imagen/Veo の段階導入 → アラート（Log-based）
```

---

更新ルール:

- タスクはチェックボックスで進捗管理し、PR/コミットで更新
- 大きな設計変更は本ドキュメントのフェーズ/受け入れ基準にも反映
- 実装後は疎通手順・確認コマンドを追記し再現性を担保

```

```
