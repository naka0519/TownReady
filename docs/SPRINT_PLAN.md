# TownReady スプリント計画と進捗トラッカー

このドキュメントは、TownReady のMVP実装に向けたスプリント計画・タスク分解・進捗管理を記録します。実装・検証の観点で随時更新してください。

## 0. 概要（現行MVP方針）
- 住所/属性/ハザードから“その街専用”の訓練一式を自動生成（台本/役割/導線/ポスター/60秒VTR/KPI）。
- アーキテクチャ: Next.js（Web）/ FastAPI（API）/ Worker（Pub/Sub Push）/ Firestore（メタ）/ GCS（生成物）/ Vertex AI（Gemini/Imagen/Veo/KB）。

## 1. 現在の達成状況（Done）
- API/Worker ヘルス: OK（`api/app.py:/health`, `workers/server.py:/health`）
- Firestore 書き込み: OK（`services/firestore_client.py` 及び `GET /health/firestore_write`）
- Pub/Sub Push 配信: OK（`workers/server.py:/pubsub/push`）
- ジョブフロー: queued → processing → done（Firestore 更新）
- Worker: タスク連鎖（plan→scenario→safety→content）・タスク単位の冪等化・任意のOIDC検証（`_verify_push`）
- Scenario/Content: GCS 書き込み＋署名URL（IAM SignBlob, TTL=3600s）を安定発行（`services/storage_client.py`）
- Safety×KB: 最小連携（issues に `kb_hits` 付与）
- README/.env: `PUBSUB_TOPIC`/`PUSH_*`/`KB_SEARCH_*` を追記

## 2. 直近の課題・差分（Gap）
- Contract Test のCI組み込み（生成・検証は実施済）
- フロント未実装（フォーム→投入→進捗→成果DL→KPI）
- KPI 集計（Webhook格納・可視化）未実装
- 署名URLの運用調整（TTL設定/ファイル名付与/失効ハンドリング）
- 連鎖のエラー/リトライ/アラート設計の明確化
- KB 運用改善（文書拡充・スニペット表示・自動再取込）

## 3. フェーズ別スプリント計画（MVP→α）

### Phase 1（バックエンド堅牢化 / 連鎖 / 配布）
- 契約強化: Pydantic/JSON Schema によるI/Oバリデーション徹底（Contract Test）
- generate/content の修正: Pub/Sub 発行と正常なレスポンス返却
- ジョブ連鎖: Worker 内で次タスクを自動キック（停止条件/リトライ方針も定義）
- 署名URL: GCS Signed URL 生成とTTL運用、`assets_index.json` で集約
- Safety×KB: KBSearch 連携により issues に根拠（出典/タイトル/スニペット）付与（最小）

### Phase 2（AI本実装 / 生成品質）
- Coordinator/Scenario のテキスト生成を Gemini で実装（プロンプト設計・制約出力）
- Imagen/Veo のダミー→本番API段階移行（ジョブ化・長時間タスクの保存/参照）
- Safety のルール/チェック拡充（ハザード/配慮/屋内外/自己交差検出）

### Phase 3（体験/KPI / 改善ループ）
- Web: 入力→ジョブ起動→ステータス監視→成果DL（署名URL）
- Webhook（checkin/forms）→ Firestore 保存 → KPI 集計API → ダッシュボード
- 改善提案（前回ログ/KPIからの改善点サジェスト）

## 4. Next Actions（直近の実装順）
1) Contract Test をCIへ組み込み（JSON Schema 生成＋Pydantic 検証を自動化）
2) E2E最小: 入力→連鎖→成果（署名URL）までのスモークを docs/スクリプト化
3) 連鎖のエラー/リトライ設計: 失敗時の停止・再投入・通知ポリシー確立
4) Web最小: 進捗/成果DLビュー（署名URL直リンク/QR）
5) Gemini着手: Coordinator/Scenario の本文生成（制約出力/多言語）
6) KB 運用改善: 文書拡充（kb/ 配下）、スニペット設定、定期再取込の運用化

## 5. タスク分解（チェックリスト）

### Phase 1
- [x] generate/content の Pub/Sub 発行と return 修正（`api/app.py`）
- [x] Worker で次タスク発行（`workers/server.py`）
- [x] `services/storage_client.py` に署名URL取得を追加（配布TTL/権限）
- [x] Safety×KB 最小連携（`services/kb_search.py` を Worker から呼び出し）
- [x] JSON Schema 生成＆Contract Test（`schemas/generate_json_schema.py` 実行／Pydantic 検証）
 - [x] README/.env の整合更新（PUSH/KBS 配列）
 - [ ] Contract Test のCI組み込み
 - [x] KB 設定の実環境反映（.env KB_* 反映／API 再デプロイ／GCS→DE 取り込み／検索ヒット確認）
 - [ ] 署名URL運用改善（TTL env 化/Content-Disposition 付与/失効時のUX）

### Phase 2
- [ ] Gemini による Coordinator/Scenario 生成（プロンプト/出力拘束）
- [ ] Imagen/Veo 本番API連携（ポーリング/保存/URI格納）
- [ ] Safety ルール拡充（自己交差/屋外禁止/段差）

### Phase 3
- [ ] Web フロント最小（フォーム/進捗/成果DL）
- [ ] Webhook→KPI集計API→ダッシュボード
- [ ] 改善提案ループ（前回ログ参照）

## 6.1 検証ステップ（抜粋）
- 署名URL（Content）: `POST /api/generate/content` → `result.*_url` が非 null → `curl -I "$URL"` が 200
- 署名URL（Scenario）: plan 連鎖後の `assets.*_url` で `curl -I` が 200
- 連鎖完了: `completed_tasks` が `["plan","scenario","safety","content"]`
- KB連携: safety の `issues[].kb_hits` が 0–2 件
- ログ監視: Worker の `signed_url_failed_*` が出ないこと（gcloud logging read フィルタ使用）
 - KB検索API: `curl -sS --get "$API_URL/api/kb/search" --data-urlencode "q=横浜 避難" --data-urlencode "n=2" | jq .`（.env の KB_* 反映・API 再デプロイ済み、データストアに `kb/` 配下の .txt/.html/.pdf 等が取り込まれていること）

## 6. 受け入れ基準（MVP）
- 入力→生成→配布まで10分以内（Imagen/Veoは段階導入可）
- Safety出力にKB根拠（少なくとも出典リンク/タイトル/スニペット）を含む
- 配布URLは署名付き（期限付与）。Firestoreに成果メタが保存される
- E2Eスクリプトで疎通（API→ジョブ→結果DL）を再現可能

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
- Done: JSON Schema 生成と Pydantic による Contract Test（サンプルI/O）を実施。KB 検索APIをバージョン差異に対応（serving_config/data_store 両対応）し、デプロイスクリプトで KB_* 環境変数を Cloud Run へ引き渡すよう更新。GCS の `kb/` に .txt 文書を配置、Discovery Engine サービスエージェントへ `roles/storage.objectViewer` を付与し、取り込み・検索ヒットを確認
- Issues: Contract Test のCI組み込み、KB のスニペット表示/文書拡充/再取込運用
- Next: CI 組み込み → E2Eスモーク → KB 運用改善（スニペット/文書追加）

---

更新ルール:
- タスクはチェックボックスで進捗管理し、PR/コミットで更新
- 大きな設計変更は本ドキュメントのフェーズ/受け入れ基準にも反映
- 実装後は疎通手順・確認コマンドを追記し再現性を担保
[2025-09-15]
- Done: JSON Schema 生成と Pydantic による Contract Test（サンプルI/O）を実施。KB 検索APIをバージョン差異に対応（serving_config/data_store 両対応）し、デプロイスクリプトで KB_* 環境変数を Cloud Run へ引き渡すよう更新
- Issues: 実環境の KB_* 変数未反映・データストア未取り込みの可能性。CI 組み込みは未了
- Next: `.env` に KB_* を追記→API再デプロイ→KB検索疎通確認／Contract Test のCI組み込み／E2Eスモーク整備
