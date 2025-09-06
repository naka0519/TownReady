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
        self.data_store = self.client.data_store_path(
            self.settings.project,
            getattr(self.settings, "kb_search_location", "global"),
            getattr(self.settings, "kb_search_collection", "default_collection"),
            getattr(self.settings, "kb_search_datastore", self.settings.kb_dataset),
        )

    def search(self, query: str, page_size: int = 5) -> List[dict]:
        req = de.SearchRequest(query=query, data_store=self.data_store, page_size=page_size)
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

