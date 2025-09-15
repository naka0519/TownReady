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
- Safety×KB: 最小連携（issues に `kb_hits` 付与）
- README/.env: `PUBSUB_TOPIC`/`PUSH_*`/`KB_SEARCH_*` を追記

## 2. 直近の課題・差分（Gap）

- Contract Test の CI 組み込み（生成・検証は実施済）
- フロント未実装（フォーム → 投入 → 進捗 → 成果 DL→KPI）
- KPI 集計（Webhook 格納・可視化）未実装
- 署名 URL の運用調整（TTL 設定/ファイル名付与/失効ハンドリング）
- 連鎖のエラー/リトライ/アラート設計の明確化
- KB 運用改善（文書拡充・スニペット表示・自動再取込）

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

1. CI トリガー作成: Cloud Build で `infra/cloudbuild.tests.yaml` を main への push/PR で自動実行
2. リトライ/アラート強化: 最小実装にバックオフ・通知（Error Reporting/Log-based Alert）を追加
3. Web 最小: 入力フォーム → ジョブ起動 → 進捗 →DL（署名 URL/QR）
4. Gemini 着手: Coordinator/Scenario の本文生成（制約出力/多言語）
5. Imagen/Veo 本番 API: ポーリング/保存/URI 格納（段階導入）
6. KB 運用改善: 文書拡充（kb/ 配下）、スニペット反映の確認、定期再取込の運用化

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
- [ ] 署名 URL 運用改善（TTL env 化/Content-Disposition 付与/失効時の UX）
- [x] E2E スモークスクリプト追加（`scripts/e2e_smoke.sh`）
- [x] KB 検索のスニペット対応（対応ライブラリで有効化）
- [x] 連鎖の最小リトライ実装（`attempts` 記録/閾値以下で再投入, `completed_order` 追加）

### Phase 2

- [ ] Gemini による Coordinator/Scenario 生成（プロンプト/出力拘束）
- [ ] Imagen/Veo 本番 API 連携（ポーリング/保存/URI 格納）
- [ ] Safety ルール拡充（自己交差/屋外禁止/段差）

### Phase 3

- [ ] Web フロント最小（フォーム/進捗/成果 DL）
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

---

更新ルール:
- タスクはチェックボックスで進捗管理し、PR/コミットで更新
- 大きな設計変更は本ドキュメントのフェーズ/受け入れ基準にも反映
- 実装後は疎通手順・確認コマンドを追記し再現性を担保
```
