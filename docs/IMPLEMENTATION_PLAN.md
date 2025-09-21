# TownReady 実装計画 & タスク管理

本ドキュメントは TownReady プロジェクトの優先順位・フェーズ別実装計画・タスク進捗を整理する。審査方針に合わせ、**新規性 > 解決策の有効性 > 実装品質と拡張性** の順で優先度を定義する。

## 1. プロジェクト方針
- 地域固有データと複数ユースケースを織り込んだマルチエージェント生成基盤を構築し、未解決課題に対する解像度を高める。
- KPI 設計から改善提案までのサイクルを自動化し、訓練準備〜検証を 10 分以内で完了できる体験を提供する。
- 生成 AI・Pub/Sub ワークフローを安全かつ運用可能な水準に引き上げ、Cloud Run で継続運用できる品質を担保する。

## 2. 優先度とアウトカム
| 優先度 | 重点アウトカム | 成功指標 (例) |
| --- | --- | --- |
| 新規性 (P0) | 地域・施設ごとに明確に差別化された訓練一式の自動生成 | シナリオ内に地域独自の導線・危険箇所・推奨機材が反映されるケース比 80% 以上 |
| 解決策の有効性 (P1) | 生成物が訓練現場で即利用可能で、安全レビュー・改善提案が具体的 | KPI データ反映後の再提案採用率 60% / 安全指摘に根拠リンク付き応答率 90% |
| 実装品質と拡張性 (P2) | 安定運用・自動テスト・監視が整備される | E2E パイプライン成功率 95% / 主要機能のCIカバレッジ 80% |

## 3. フェーズ別ロードマップ
- [ ] **地域データ連携基盤**: RegionContext の多地域化と GCS 自動同期、サイズ最適化、テスト整備を完了させる。
- [ ] **Plan/Scenario 生成強化**: Gemini プロンプトの精緻化とフォールバック改善（生成段階でハザードハイライト・複線ルート・タイムライン等を返すよう修正）。
- [ ] **ユースケースプリセット**: 自治会・学校・観光地などのテンプレ入力を UI に追加し、ジョブ起動時に適用。
- [ ] **知識ベース拡充自動化**: `kb/` 配下の更新を Discovery Engine に自動反映する同期スクリプトを整備。

### フェーズB: 解決策の有効性向上 (P1)
- [~] **Scenario 出力の構造化**: GeoJSON に複数導線・タイムライン・資機材チェックを付与し、Markdown と整合性検証を追加。（成果物反映済み。テスト・多地域展開は A-1/A-2 と連携して継続）
- [ ] **高度安全レビュー**: 生成物の静的解析と KB スコアリングを組み合わせた指摘エンジンを実装。自治体チェックリスト JSON で網羅判定。
- [ ] **KPI 永続化 & ダッシュボード**: Webhook を Firestore/BigQuery に保存し、Next.js 側に KPI 可視化＋再提案ロジックを実装。
- [ ] **Imagen/Veo 本生成**: 生成 API 呼び出しと署名 URL 配布、字幕生成、コスト制御をワークフローに統合。

### フェーズC: 品質と拡張性 (P2)
- [ ] **信頼性改善**: Pub/Sub publish 失敗のリトライ/通知、Firestore 更新のトランザクション化、Error Reporting 連携。
- [ ] **CI/CD 強化**: Contract・E2E・Imagen/Veo テストを Cloud Build に組み込み、Gemini 有効/無効のマトリクスを自動検証。
- [ ] **観測性ダッシュボード**: 署名 URL 再発行・キュー遅延・失敗率を Cloud Monitoring で可視化。
- [ ] **拡張アーキテクチャ**: Webhook を Cloud Tasks 化、KPI/改善提案を BigQuery/Looker Studio に輸出。

## 4. カンバン (着手状況)
| ID | フェーズ | タスク | 担当 | 状況 | 予定完了 |
| --- | --- | --- | --- | --- | --- |
| A-1 | A | 地域データ連携基盤 | TBD | 進行中 | TBD |
| A-2 | A | Plan/Scenario 生成強化 | TBD | 未着手 | TBD |
| A-3 | A | ユースケースプリセット実装 | TBD | 未着手 | TBD |
| A-4 | A | KB 同期自動化 | TBD | 未着手 | TBD |
| B-1 | B | Scenario 出力構造化 | TBD | 未着手 | TBD |
| B-2 | B | 高度安全レビュー | TBD | 未着手 | TBD |
| B-3 | B | KPI 永続化/可視化 | TBD | 未着手 | TBD |
| B-4 | B | Imagen/Veo 本生成 | TBD | 未着手 | TBD |
| C-1 | C | 信頼性改善セット | TBD | 未着手 | TBD |
| C-2 | C | CI/CD 強化 | TBD | 未着手 | TBD |
| C-3 | C | 観測性ダッシュボード | TBD | 未着手 | TBD |
| C-4 | C | 拡張アーキテクチャ整備 | TBD | 未着手 | TBD |

## 5. 運用ルール
- 進捗更新はスプリント終了時および主要マイルストン完了時に実施し、`docs/SPRINT_PLAN.md` と整合させる。
- タスクの粒度は「実装完了まで 1〜3 日で収束する単位」を目安とし、超える場合はサブタスクへ分割する。
- 依存関係変更や設計変更は本ドキュメントに反映し、レビュアと共有する。

## 6. 次アクション 
1. フェーズA-1/A-2 の要件定義と技術調査を完了し、データ入手経路・スキーマ・API 契約を確定する。
2. ユースケースプリセットの UI 仕様を決定し、Next.js フォームへの組み込み設計を作成する。
3. KB 同期自動化の PoC (GCS → Discovery Engine) を scripts/ または infra/ 配下で実装し、手順書を追加する。

## 7. フェーズA 要件調査ログ

### A-1 地域データ連携基盤 — 要件整理
- **目的**: 住所/緯度経度を起点に、自治体境界・避難所・想定ハザード・施設属性を自動補完し、Plan/Scenario/Safety 各エージェントが参照できる `RegionContext` を構築する。
- **入力データ候補**
  - 国土地理院「基盤地図情報」「浸水想定区域データ」：行政界、避難施設、洪水深さ等。
  　https://nlftp.mlit.go.jp/ksj/
  - 防災科学技術研究所 J-SHIS：地震動・断層帯のリスク指標。
  - 自治体オープンデータ（横浜市防災情報、指定避難所一覧、多言語対応施設）。
  - 気象庁/国交省 災害危険度マップ（高潮・土砂災害警戒区域 等）。
- **必須フィールド**
- `region` (prefecture, city, ward)、`hazard_scores` (earthquake, flood, tsunami, landslide)、`shelters` (座標＋施設 ID/名称のみを取得し、収容人数など不足分は別マスタで管理)、`critical_infrastructure` (hospitals, schools, care homes)、`population_profile` (estimated elderly/foreign ratio)。
  - `geometry` (GeoJSON MultiPolygon) と `egress_routes` (主要道路/避難路のライン情報)。
- **アーキテクチャ案**
  - `scripts/ingest_region_context.py` を新設し、Open Data → Parquet/JSON へ整形。Cloud Storage `gs://.../region_context/{pref}/{city}.json` に保存。
  - Worker 起動時に `RegionContextStore` を通じ Firestore `regions/{city_id}` をキャッシュ。ジョブ作成時に `JobsStore.create` へ `region_context_ref` を追記。
  - API 層では `GenerateBaseRequest` 拡張（`context_hint`）or ミドルウェアで住所正規化（Geocoding）。
- **検証観点**
  - サンプル住所（横浜市戸塚区）で行政界一致率 > 99%、避難所件数が自治体公開数と一致。
  - `RegionContext` 取得の 95 パーセンタイル < 400ms（Firestore キャッシュが効いていること）。
  - 欠損時フェールセーフ（デフォルトテンプレへのフォールバック）を定義。
- **リスク/留意事項**
  - データライセンス（CC BY 等）と更新頻度の管理。
  - GeoJSON サイズ制約（Firestore 1MB 制限）→ GCS 参照に分離。
  - 多言語名の扱い（避難所名の英訳/やさしい日本語表記）。

#### A-1 進捗（プロトタイプ）
- `scripts/ingest_region_context.py` を更新し、行政界 (`kb/gyouseiku.geojson`) を読み込んで戸塚区ポリゴンを抽出。津波浸水想定 (`kb/tunami.geojson`) と急傾斜地崩壊 (`kb/hazardarea.geojson`) を行政界バウンダリとセントロイド内判定でクリップし、座標を丸めて簡易 simplify。
- 出力サンプル `kb/region_context/totsuka.json` を生成（津波ポリゴン 0 件、急傾斜 30 件、洪水 1,874 件、避難所 36 件）。津波ハザードが 0 件となるため、将来的には polygon intersection を導入して周辺地域も評価できるよう改善予定。
- 避難所は座標＋名称/id のみに限定し、追加属性は別マスタ管理とする方針を確認済み。
- `hazard_scores` を集計（feature 件数・カバレッジ km2・最大浸水深・トップハザード種別/ランク件数）し、RegionContext JSON に含める仕組みを整備。
- Cloud Run Worker が GCS (`REGION_CONTEXT_DIR`) から地域コンテキストを取得し、Plan/Scenario に flood / landslide サマリ・ハイライトが反映されることを本番相当環境で検証済み。
- **残タスク (A-1)**
  - 行政界クリップをセントロイド判定から厳密な polygon intersection へ置き換え。
  - 津波以外のハザード（高潮・J-SHIS 地震動など）を追加取り込みし `hazard_scores` を拡充。
  - 地域キー生成を汎用化し、複数市区町村へ展開可能にする。
  - `kb/region_context/*.json` を GCS へ自動同期する仕組みと CI 手順を整備。
  - JSON サイズ削減（必要フィールドのみ抽出、座標 quantization）とキャッシュ戦略の検討。
  - ハザードサマリ出力の単体/E2E テストを整備。
- 避難所は座標＋名称/id のみに限定し、追加属性は別マスタ管理とする方針を確認済み。

### A-2 Plan/Scenario 生成強化 — 要件整理
- **目的**: 地域文脈と参加者属性に基づき、定型テンプレではなく動的に差別化された Plan/Scenario を生成する。
- **現行ギャップ**
  - `_build_plan` が災害タイプのみを参照し固定 KPI を返却（workers/server.py:82-125）。
  - `_build_scenario` のフォールバックが単一路線・固定手順で地理情報を活かせていない（workers/server.py:193-261）。
- **拡張要件**
  - `RegionContext` を受け取り、危険箇所/避難所/道路閉塞情報を Plan の `acceptance.must_include` / `handoff` に反映。
  - 参加者属性（車椅子/子ども/言語）×施設用途ごとに推奨 KPI・タイムラインを可変化。
  - Scenario 出力に `routes` 複数系（メイン/バリアフリー/代替）、各ステップの `timestamp_offset_sec`、`resource_checklist` を追加。
  - Gemini 有効時はプロンプトに JSON スキーマと地域サマリを付与。無効時フォールバックでも同等構造を組み立て。
- **API/スキーマ変更案**
  - `schemas/models.py` に `RegionContext`, `ScenarioStep`, `ResourceItem` を追加。
  - `GenerateBaseRequest` に `context_ref` or `region_context` を追加し、後方互換のため optional にする。
- **検証観点**
  - テストケース: 地震+火災 / 夜間 / 車椅子5名 / 近隣が洪水想定区域 → 生成タイムラインに屋内退避→屋外避難の遷移が含まれること。
  - GeoJSON の自己交差検知、ルート長/斜度の整合（疑似データで unit test）。
  - Gemini 失敗時にフォールバックでも多言語シナリオが生成されること。
- **リスク/留意事項**
  - プロンプト/出力サイズ増大によるコスト・レイテンシ。必要に応じ要約/圧縮。
  - データ欠損地域向けのフェールバック維持。
  - 将来の Imagen/Veo 連携でルート・タイムラインを視覚化するための ID 付与。

#### A-2 進捗（2025-09-20）
- RegionContext からのハザードサマリを Plan の `acceptance.must_include` に反映し、Scenario では `timeline`・`resource_checklist`・`alternate` ルートを自動生成するよう実装。Gemini 経由の出力にも後処理で強制適用。
- Markdown 台本へ `Local Risk Highlights` / `地域特有の注意` を挿入し、洪水・急傾斜ハイライトを成果物に反映。成果物 (`output/script.md` 等) で確認済み。
- flood / landslide ハイライトが実環境で確認済み。残課題（行政界 intersection / 追加ハザード）は A-1 と連携して継続。
