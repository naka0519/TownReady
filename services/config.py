from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


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
    # Optional: secure Pub/Sub push with OIDC verification
    push_verify: bool
    push_audience: Optional[str]
    push_service_account: Optional[str]
    # Signed URL defaults
    signed_url_ttl: int
    # Retry policy
    retry_max_attempts: int
    # Generative AI (Gemini) staging flags
    use_gemini: bool
    gemini_model: str
    vai_location: str
    gemini_timeout_sec: int
    gemini_max_retries: int
    use_imagen: bool
    use_veo: bool
    media_budget_usd: float
    media_cost_image: float
    media_cost_video: float
    kpi_firestore_collection: str
    bigquery_dataset: Optional[str]
    bigquery_table: Optional[str]

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
        push_verify = str(os.getenv("PUSH_VERIFY", "false")).lower() in {"1", "true", "yes", "on"}
        push_audience = os.getenv("PUSH_AUDIENCE")
        push_service_account = os.getenv("PUSH_SERVICE_ACCOUNT")
        try:
            signed_url_ttl = int(os.getenv("SIGNED_URL_TTL", "3600"))
        except Exception:
            signed_url_ttl = 3600
        try:
            retry_max_attempts = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
        except Exception:
            retry_max_attempts = 3
        use_gemini = str(os.getenv("GEMINI_ENABLED", "false")).lower() in {"1", "true", "yes", "on"}
        # Default to stable public model/region
        gemini_model = os.getenv("GEMINI_MODEL", os.getenv("GEMINI", "gemini-2.0-flash"))
        vai_location = os.getenv("VAI_LOCATION", os.getenv("VERTEX_LOCATION", "us-central1"))
        try:
            gemini_timeout_sec = int(os.getenv("GEMINI_TIMEOUT_SEC", "25"))
        except Exception:
            gemini_timeout_sec = 25
        try:
            gemini_max_retries = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
        except Exception:
            gemini_max_retries = 2
        use_imagen = str(os.getenv("IMAGEN_ENABLED", "false")).lower() in {"1", "true", "yes", "on"}
        use_veo = str(os.getenv("VEO_ENABLED", "false")).lower() in {"1", "true", "yes", "on"}
        try:
            media_budget_usd = float(os.getenv("MEDIA_MAX_COST_USD", "1.0"))
        except Exception:
            media_budget_usd = 1.0
        try:
            media_cost_image = float(os.getenv("MEDIA_COST_IMAGE_USD", "0.02"))
        except Exception:
            media_cost_image = 0.02
        try:
            media_cost_video = float(os.getenv("MEDIA_COST_VIDEO_USD", "0.2"))
        except Exception:
            media_cost_video = 0.2
        kpi_firestore_collection = os.getenv("KPI_COLLECTION", "kpi_events")
        bigquery_dataset = os.getenv("BIGQUERY_DATASET") or None
        bigquery_table = os.getenv("BIGQUERY_TABLE") or None

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
            push_verify=push_verify,
            push_audience=push_audience,
            push_service_account=push_service_account,
            signed_url_ttl=signed_url_ttl,
            retry_max_attempts=retry_max_attempts,
            use_gemini=use_gemini,
            gemini_model=gemini_model,
            vai_location=vai_location,
            gemini_timeout_sec=gemini_timeout_sec,
            gemini_max_retries=gemini_max_retries,
            use_imagen=use_imagen,
            use_veo=use_veo,
            media_budget_usd=media_budget_usd,
            media_cost_image=media_cost_image,
            media_cost_video=media_cost_video,
            kpi_firestore_collection=kpi_firestore_collection,
            bigquery_dataset=bigquery_dataset,
            bigquery_table=bigquery_table,
        )
