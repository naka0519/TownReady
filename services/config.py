from __future__ import annotations

import os
from dataclasses import dataclass


def _normalize_bucket_name(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip()
    if v.startswith("gs://"):
        v = v[len("gs://") :]
    return v


@dataclass(frozen=True)
class Settings:
    project: str
    region: str
    firestore_db: str
    gcs_bucket: str | None
    pubsub_topic: str
    kb_dataset: str
    kb_search_location: str
    kb_search_collection: str
    kb_search_datastore: str

    @staticmethod
    def load() -> "Settings":
        project = os.getenv("GCP_PROJECT", "")
        region = os.getenv("REGION", "asia-northeast1")
        firestore_db = os.getenv("FIRESTORE_DB", "townready")
        gcs_bucket = _normalize_bucket_name(os.getenv("GCS_BUCKET"))
        pubsub_topic = os.getenv("PUBSUB_TOPIC", "townready-jobs")
        kb_dataset = os.getenv("KB_DATASET", "kb_default")
        kb_search_location = os.getenv("KB_SEARCH_LOCATION", "global")
        kb_search_collection = os.getenv("KB_SEARCH_COLLECTION", "default_collection")
        kb_search_datastore = os.getenv("KB_SEARCH_DATASTORE", kb_dataset)

        if not project:
            raise RuntimeError("GCP_PROJECT is not set in environment")

        return Settings(
            project=project,
            region=region,
            firestore_db=firestore_db,
            gcs_bucket=gcs_bucket,
            pubsub_topic=pubsub_topic,
            kb_dataset=kb_dataset,
            kb_search_location=kb_search_location,
            kb_search_collection=kb_search_collection,
            kb_search_datastore=kb_search_datastore,
        )
