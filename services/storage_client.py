from __future__ import annotations

from typing import Optional

from google.cloud import storage

from .config import Settings


class Storage:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.load()
        self.client = storage.Client(project=self.settings.project)
        if not self.settings.gcs_bucket:
            raise RuntimeError("GCS_BUCKET is not set (gs://bucket or bucket)")
        self.bucket = self.client.bucket(self.settings.gcs_bucket)

    def upload_text(self, path: str, content: str, content_type: str = "text/plain") -> str:
        blob = self.bucket.blob(path)
        blob.upload_from_string(content, content_type=content_type)
        return f"gs://{self.bucket.name}/{path}"

    def upload_bytes(self, path: str, data: bytes, content_type: Optional[str] = None) -> str:
        blob = self.bucket.blob(path)
        blob.upload_from_string(data, content_type=content_type)
        return f"gs://{self.bucket.name}/{path}"

