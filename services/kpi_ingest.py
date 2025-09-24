from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

try:
    from google.cloud import firestore  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    firestore = None  # type: ignore

try:
    from google.cloud import bigquery  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    bigquery = None  # type: ignore

from .config import Settings


class KPIIngestor:
    """Persist webhook KPI payloads to Firestore and BigQuery (best effort)."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings.load()
        self.firestore_collection = getattr(self.settings, "kpi_firestore_collection", "kpi_events")
        self.bigquery_dataset = getattr(self.settings, "bigquery_dataset", None)
        self.bigquery_table = getattr(self.settings, "bigquery_table", None)
        self._firestore_client = None
        self._bq_client = None

    def _firestore(self):
        if firestore is None:
            return None
        if self._firestore_client is not None:
            return self._firestore_client
        try:
            self._firestore_client = firestore.Client(project=self.settings.project, database=self.settings.firestore_db)  # type: ignore[attr-defined]
        except Exception:
            self._firestore_client = None
        return self._firestore_client

    def _bigquery(self):
        if bigquery is None:
            return None
        if self.bigquery_dataset is None or self.bigquery_table is None:
            return None
        if self._bq_client is not None:
            return self._bq_client
        try:
            self._bq_client = bigquery.Client(project=self.settings.project)  # type: ignore[attr-defined]
        except Exception:
            self._bq_client = None
        return self._bq_client

    def ingest(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        timestamp = int(time.time())
        fs_status = "skipped"
        bq_status = "skipped"

        client = self._firestore()
        if client is not None:
            try:
                doc_ref = client.collection(self.firestore_collection).document()
                doc_ref.set({
                    "payload": payload,
                    "ingested_at": timestamp,
                })
                fs_status = "stored"
            except Exception as exc:  # pragma: no cover - dependent on environment
                fs_status = f"error:{exc}"

        bq_client = self._bigquery()
        if bq_client is not None:
            table_id = f"{self.settings.project}.{self.bigquery_dataset}.{self.bigquery_table}"
            try:
                row = {
                    "ingested_at": timestamp,
                    "payload": json.dumps(payload, ensure_ascii=False),
                }
                errors = bq_client.insert_rows_json(table_id, [row])  # type: ignore[attr-defined]
                if errors:
                    bq_status = f"error:{errors}"
                else:
                    bq_status = "stored"
            except Exception as exc:  # pragma: no cover
                bq_status = f"error:{exc}"

        return {"firestore": fs_status, "bigquery": bq_status}
