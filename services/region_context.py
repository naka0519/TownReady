from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

try:  # Optional dependency; required when REGION_CONTEXT_DIR points to GCS.
    from google.cloud import storage  # type: ignore
except Exception:  # pragma: no cover - google libs may be absent locally
    storage = None  # type: ignore


class RegionContextStore:
    """Lightweight loader for pre-generated RegionContext JSON blobs.

    In production this would likely back onto Firestore or GCS. For the MVP we
    load JSON files from `kb/region_context` (or `REGION_CONTEXT_DIR`).
    """

    def __init__(self, base_dir: Optional[os.PathLike[str] | str] = None) -> None:
        base = str(base_dir or os.getenv("REGION_CONTEXT_DIR", "kb/region_context"))
        self._is_gcs = base.startswith("gs://")
        self._gcs_client: Optional[Any] = None
        if self._is_gcs:
            without_scheme = base[len("gs://") :]
            parts = without_scheme.split("/", 1)
            self._gcs_bucket = parts[0]
            self._gcs_prefix = parts[1].strip("/") if len(parts) > 1 else ""
            self.base_dir_path = None
        else:
            self.base_dir_path = Path(base)

    def _resolve_base(self) -> Path:
        base = getattr(self, "base_dir_path", None)
        if base is None:
            raise RuntimeError("RegionContextStore base path is not a filesystem path")
        if base.is_absolute():
            return base
        return Path(__file__).resolve().parents[1] / base

    @staticmethod
    def _match_key(location: Dict[str, Any]) -> Optional[str]:
        address = str(location.get("address", ""))
        # Minimal heuristics; can be extended with geocoding later.
        if "戸塚区" in address and "横浜市" in address:
            return "totsuka.json"
        return None

    @lru_cache(maxsize=32)
    def _load_json(self, filename: str) -> Dict[str, Any]:
        if getattr(self, "_is_gcs", False):
            if storage is None:
                raise RuntimeError("google-cloud-storage is required for REGION_CONTEXT_DIR=gs://...")
            client = self._gcs_client or storage.Client()  # type: ignore
            self._gcs_client = client
            prefix = getattr(self, "_gcs_prefix", "")
            object_name = f"{prefix}/{filename}" if prefix else filename
            blob = client.bucket(self._gcs_bucket).blob(object_name)
            if not blob.exists():
                raise FileNotFoundError(object_name)
            contents = blob.download_as_text(encoding="utf-8")
            return json.loads(contents)
        path = self._resolve_base() / filename
        with path.open("r", encoding="utf-8") as fp:
            return json.load(fp)

    def load_for_location(self, location: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        key = self._match_key(location)
        if not key:
            return None
        filename = f"{key}.json" if not key.endswith(".json") else key
        try:
            return self._load_json(filename)
        except FileNotFoundError:
            return None
        except Exception:
            return None
