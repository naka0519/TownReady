from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from google.cloud import firestore

from .config import Settings


class JobsStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.load()
        self.client = firestore.Client(project=self.settings.project, database=self.settings.firestore_db)
        self.col = self.client.collection("jobs")

    def create(self, payload: Dict[str, Any], status: str = "received") -> str:
        job_id = str(uuid.uuid4())
        now = int(time.time())
        doc = {
            "status": status,
            "payload": payload,
            "created_at": now,
            "updated_at": now,
        }
        region_ref = payload.get("region_context_ref") if isinstance(payload, dict) else None
        if region_ref:
            doc["region_context_ref"] = region_ref
        snapshot = payload.get("region_context_snapshot") if isinstance(payload, dict) else None
        if snapshot:
            doc["region_context_snapshot"] = snapshot
        facility_profile = payload.get("facility_profile") if isinstance(payload, dict) else None
        if facility_profile:
            doc["facility_profile"] = facility_profile
        self.col.document(job_id).set(doc)
        return job_id

    def update_status(self, job_id: str, status: str, extra: Optional[Dict[str, Any]] = None) -> None:
        now = int(time.time())
        patch: Dict[str, Any] = {"status": status, "updated_at": now}
        if extra:
            patch.update(extra)
        self.col.document(job_id).set(patch, merge=True)

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        snap = self.col.document(job_id).get()
        if not snap.exists:
            return None
        doc = snap.to_dict() or {}
        doc["job_id"] = job_id
        return doc
