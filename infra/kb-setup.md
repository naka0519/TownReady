# Vertex AI Search（KB）設定と運用方針

本プロジェクトでは「Vertex AI Search（Discovery Engine）」をKBとして活用し、Safetyレビュー等で根拠引用を行います。最初はSearchのみ、その後ADKでエージェント化を検討します。

## 前提
- API: `discoveryengine.googleapis.com`
- リージョンは `global` 推奨（Searchはグローバル扱い）
- コレクションは `default_collection`、データストアIDは `.env` の `KB_DATASET`/`KB_SEARCH_DATASTORE` を使用

## 変数例
```bash
export GCP_PROJECT="townready"
export KB_SEARCH_LOCATION="global"
export KB_SEARCH_COLLECTION="default_collection"
export KB_SEARCH_DATASTORE="kb_default"  # .envのKB_DATASETと揃える
```

## 有効化とデータストア作成（ガイド）
```bash
gcloud config set project "$GCP_PROJECT"
gcloud services enable discoveryengine.googleapis.com

# データストア作成はUI推奨（Console > Vertex AI Search）
# 種別: App Search / ドキュメント
# ID: $KB_SEARCH_DATASTORE / コレクション: $KB_SEARCH_COLLECTION
# 検索ブランチ: default_branch
```

## ドキュメント取り込み（簡易運用）
1. `kb/` 配下のMarkdownをGCSへアップロード（例: `gs://<bucket>/kb/`）
2. Discovery Engineの「データソース」でGCSコネクタを作成し、`kb/`プリフィックスを指定
3. 取り込み後にインデックス作成完了を待機

## 動作確認（サンプル検索）
Pythonクライアント（`google-cloud-discoveryengine`）を使ってクエリを送信します。

```bash
pip install google-cloud-discoveryengine
python - <<'PY'
from google.cloud import discoveryengine_v1 as de
import os

project=os.environ['GCP_PROJECT']
location=os.environ.get('KB_SEARCH_LOCATION','global')
collection=os.environ.get('KB_SEARCH_COLLECTION','default_collection')
datastore=os.environ.get('KB_SEARCH_DATASTORE','kb_default')

client=de.SearchServiceClient()
data_store=client.data_store_path(project, location, collection, datastore)

req=de.SearchRequest(query='横浜市 ガイドライン 避難', data_store=data_store, page_size=3)
resp=client.search(req)
for r in resp:
  print(r.document.name, r.document.derived_struct_data.get('link', ''))
PY
```

---

## 運用メモ
- ドキュメントはMarkdown推奨（出典URLや章見出しを明示）
- `kb/` の追加・更新後は、GCSコネクタの再取り込みをキック
- 将来的にADK導入時は、このデータストアを知識ベースとして参照

