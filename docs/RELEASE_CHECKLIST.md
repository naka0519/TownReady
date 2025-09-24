# TownReady リリースチェックリスト

成果物として提出する際に含めるべきディレクトリと除外すべき生成物をまとめます。

## 含めるもの
- `api/`, `workers/`, `web/`, `services/`, `schemas/`, `tests/`, `infra/`, `scripts/`: 実装とデプロイに必要なソースコード。
- `kb/` のうち軽量なサンプルデータ:
  - `kb/yokohama_guideline.txt` — Vertex AI Search 用のテキスト例。
  - `kb/region_context/index.json` と `kb/region_context/region-14110.json` — RegionContext カタログと 1 地域分のサンプル（提出物向けに座標を間引いた派生版を同名ファイルとして再作成しても可）。
- `docs/`: README と運用資料、スプリント記録。
- `requirements.txt`, `package.json` など依存宣言ファイル。

## 除外するもの
- ローカル仮想環境 (`venv/`, `.venv/`) や Python キャッシュ (`__pycache__/`, `*.pyc`)。
- 実行時の生成物 (`output/`, `tmp/`, `logs/`)。
- 大容量の知識ベース原本 (`kb/*.geojson`, `kb/region_context/*.json`)。
- Node.js の生成物 (`node_modules/`, `web/.next/`, `web/out/`, `web/.turbo/`)。
- 個別環境設定 (`.env`, `*.env.*`, `.envrc`)。
- テストカバレッジレポートやビルド成果物 (`.coverage`, `dist/`, `build/`)。

## 手順
1. `git status --short` で未コミット・不要ファイルがないか確認。
2. `scripts/` 以下の自動化スクリプトを利用してビルド/デプロイ成果物を生成しない状態で成果物を打包。
3. `tests/test_plan_scenario.py` を実行し、主要ワーカーロジックが回帰していないことを確認。
4. 生成物をアーカイブする際は `.gitignore` を尊重し、`kb/yokohama_guideline.txt` と `kb/region_context/index.json`／`region-14110.json` が含まれていることを確認しつつ、その他の大容量データは除外する。
