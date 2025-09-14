from __future__ import annotations

from typing import Optional
import os
from datetime import timedelta

from google.cloud import storage
from google.auth.transport.requests import Request as GoogleAuthRequest  # type: ignore
from google.auth.iam import Signer as IamSigner  # type: ignore
try:
    from google.auth.credentials import with_scopes_if_required  # type: ignore
except Exception:  # pragma: no cover
    with_scopes_if_required = None  # type: ignore
try:
    from google.auth import default as google_auth_default  # type: ignore
except Exception:  # pragma: no cover
    google_auth_default = None  # type: ignore

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

    def signed_url(self, path: str, ttl_seconds: int = 3600, method: str = "GET", content_type: Optional[str] = None) -> str:
        """Generate a V4 signed URL for the given object path.

        Parameters:
            path: Object path within the bucket (no gs:// prefix)
            ttl_seconds: Expiration in seconds (default 1 hour)
            method: HTTP method the URL will allow (default GET)
            content_type: Optional content type hint
        Returns:
            A time-limited HTTPS URL
        """
        blob = self.bucket.blob(path)
        expiration = timedelta(seconds=ttl_seconds)

        # Resolve credentials with required scopes for IAM SignBlob
        REQUIRED_SCOPES = (
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/iam",
        )
        credentials_hint = getattr(self.client, "_credentials", None)
        if google_auth_default is not None:
            try:
                credentials_hint, _ = google_auth_default(scopes=REQUIRED_SCOPES)
            except Exception:
                # Fallback to client's credentials
                credentials_hint = getattr(self.client, "_credentials", None)
        try:
            if credentials_hint is not None and getattr(credentials_hint, "requires_scopes", False):
                if hasattr(credentials_hint, "with_scopes"):
                    credentials_hint = credentials_hint.with_scopes(REQUIRED_SCOPES)
                elif with_scopes_if_required is not None:
                    credentials_hint = with_scopes_if_required(credentials_hint, REQUIRED_SCOPES)
        except Exception:
            pass
        # Prefer configured SA email over credentials-derived to avoid 'default'
        sa_email: Optional[str] = (
            getattr(self.settings, "push_service_account", None)
            or os.getenv("SERVICE_ACCOUNT_EMAIL")
            or os.getenv("SA")
        )
        if not sa_email:
            try:
                sa_email = getattr(credentials_hint, "service_account_email", None)  # type: ignore[attr-defined]
            except Exception:
                sa_email = None
        # Guard against placeholder values like 'default'
        if sa_email and sa_email.strip().lower() in {"default", "(default)"}:
            sa_email = None

        # Strategy A: Use IAMCredentials SignBlob via access_token + service_account_email
        access_token: Optional[str] = None
        try:
            if credentials_hint is not None:
                req = GoogleAuthRequest()
                if not getattr(credentials_hint, "valid", False):
                    credentials_hint.refresh(req)
                access_token = getattr(credentials_hint, "token", None)
        except Exception:
            access_token = None

        params = {"version": "v4", "expiration": expiration, "method": method}
        if content_type:
            params["content_type"] = content_type

        if sa_email and access_token:
            params["service_account_email"] = sa_email
            params["access_token"] = access_token
            return blob.generate_signed_url(**params)

        # Strategy B: Fallback to library auto-detection (may fail on GCE credentials)
        if sa_email:
            params["service_account_email"] = sa_email
        return blob.generate_signed_url(**params)
