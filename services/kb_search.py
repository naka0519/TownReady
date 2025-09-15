from __future__ import annotations

from typing import List, Optional

try:
    from google.cloud import discoveryengine_v1 as de
except Exception:  # library may not be installed yet
    de = None  # type: ignore

from .config import Settings


class KBSearch:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.load()
        if de is None:
            raise RuntimeError("google-cloud-discoveryengine is not installed")
        self.client = de.SearchServiceClient()
        project = self.settings.project
        location = getattr(self.settings, "kb_search_location", "global")
        collection = getattr(self.settings, "kb_search_collection", "default_collection")
        datastore = getattr(self.settings, "kb_search_datastore", self.settings.kb_dataset)
        # Support both API surface variants:
        # v1 (older): projects/{p}/locations/{l}/dataStores/{ds}
        # v1 (newer): projects/{p}/locations/{l}/collections/{c}/dataStores/{ds}
        try:
            self.data_store = self.client.data_store_path(project, location, collection, datastore)  # type: ignore[arg-type]
        except TypeError:
            # Fallback to 3-arg signature
            self.data_store = self.client.data_store_path(project, location, datastore)  # type: ignore[arg-type]

        # Derive serving_config path robustly even if collections が無い場合
        self.serving_config = self._derive_serving_config(self.data_store)

    @staticmethod
    def _derive_serving_config(data_store_path: str) -> str:
        ds = data_store_path.strip("/")
        if "/servingConfigs/" in ds:
            return ds
        if "/collections/" in ds:
            return f"{ds}/servingConfigs/default_search"
        # Expected: projects/{p}/locations/{l}/dataStores/{ds}
        parts = ds.split("/")
        try:
            # [projects, p, locations, l, dataStores, dsid]
            p = parts[1]
            l = parts[3]
            dsid = parts[5]
            return f"projects/{p}/locations/{l}/collections/default_collection/dataStores/{dsid}/servingConfigs/default_search"
        except Exception:
            # 最後の手段: そのまま付与
            return f"{ds}/servingConfigs/default_search"

    def search(self, query: str, page_size: int = 5) -> List[dict]:
        """KB 検索（ライブラリ差異を吸収）。常に serving_config を優先し、不可時のみ data_store にフォールバック。

        スニペット表示（抜粋）を可能なら有効化します（未対応ライブラリでは無視）。
        """
        # まず serving_config を試す
        try:
            try:
                # Optional: enable snippet extraction if the library supports it
                snippet_spec = de.SearchRequest.ContentSearchSpec.SnippetSpec(max_snippet_count=1)  # type: ignore[attr-defined]
                content_spec = de.SearchRequest.ContentSearchSpec(snippet_spec=snippet_spec)  # type: ignore[attr-defined]
                req = de.SearchRequest(
                    serving_config=self.serving_config,
                    query=query,
                    page_size=page_size,
                    content_search_spec=content_spec,  # type: ignore[call-arg]
                )
            except Exception:
                req = de.SearchRequest(serving_config=self.serving_config, query=query, page_size=page_size)  # type: ignore[call-arg]
            resp = self.client.search(req)
        except Exception:
            # 旧フィールドが必要な場合のみ data_store を試す
            try:
                snippet_spec = de.SearchRequest.ContentSearchSpec.SnippetSpec(max_snippet_count=1)  # type: ignore[attr-defined]
                content_spec = de.SearchRequest.ContentSearchSpec(snippet_spec=snippet_spec)  # type: ignore[attr-defined]
                req = de.SearchRequest(
                    query=query,
                    data_store=self.data_store,
                    page_size=page_size,
                    content_search_spec=content_spec,  # type: ignore[call-arg]
                )
            except Exception:
                req = de.SearchRequest(query=query, data_store=self.data_store, page_size=page_size)  # type: ignore[call-arg]
            resp = self.client.search(req)
        out = []
        for r in resp:
            doc = {
                "name": r.document.name,
                "id": r.document.id,
                "title": r.document.derived_struct_data.get("title", ""),
                "link": r.document.derived_struct_data.get("link", ""),
                "snippet": getattr(r, "snippet", ""),
            }
            out.append(doc)
        return out
