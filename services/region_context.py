from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:  # Optional dependency; required when REGION_CONTEXT_DIR points to GCS.
    from google.cloud import storage  # type: ignore
except Exception:  # pragma: no cover - google libs may be absent locally
    storage = None  # type: ignore

try:  # Optional dependency for Firestore-backed cache.
    from google.cloud import firestore  # type: ignore
except Exception:  # pragma: no cover - firetore libs may be absent locally
    firestore = None  # type: ignore

from .config import Settings


@dataclass
class _CatalogEntry:
    """Normalized index entry for RegionContext resolution."""

    id: Optional[str]
    path: str
    keywords: Tuple[str, ...]
    bbox: Optional[Tuple[float, float, float, float]]
    centroid: Optional[Tuple[float, float]]
    slugs: Tuple[str, ...]
    hazards: Tuple[str, ...]
    preferred_names: Tuple[str, ...]
    municipal_code: Optional[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "_CatalogEntry":
        def _tuple(field: str) -> Tuple[str, ...]:
            raw = data.get(field) or []
            if isinstance(raw, str):
                raw = [raw]
            filtered = tuple(str(item).strip() for item in raw if isinstance(item, str) and item.strip())
            return filtered

        bbox_val = data.get("bbox")
        bbox: Optional[Tuple[float, float, float, float]] = None
        if isinstance(bbox_val, Iterable):
            bbox_list = list(bbox_val)  # type: ignore[arg-type]
            if len(bbox_list) == 4:
                try:
                    nums = [float(item) for item in bbox_list]
                except Exception:
                    nums = []
                if len(nums) == 4:
                    bbox = tuple(nums)  # type: ignore[assignment]

        centroid_val = data.get("centroid")
        centroid: Optional[Tuple[float, float]] = None
        if isinstance(centroid_val, Iterable):
            pts_raw = list(centroid_val)  # type: ignore[arg-type]
            if len(pts_raw) >= 2:
                try:
                    centroid = (float(pts_raw[0]), float(pts_raw[1]))
                except Exception:
                    centroid = None

        slug_items: List[str] = []
        slug_primary = data.get("slug")
        if isinstance(slug_primary, str) and slug_primary.strip():
            slug_items.append(slug_primary.strip())
        slug_extra = data.get("slugs")
        if isinstance(slug_extra, Iterable) and not isinstance(slug_extra, (str, bytes)):
            for item in slug_extra:  # type: ignore
                if isinstance(item, str) and item.strip():
                    slug_items.append(item.strip())

        return cls(
            id=str(data.get("id")) if data.get("id") else None,
            path=str(data.get("path")),
            keywords=_tuple("keywords"),
            bbox=bbox,
            centroid=centroid,
            slugs=tuple(slug_items),
            hazards=_tuple("hazards"),
            preferred_names=_tuple("preferred_names"),
            municipal_code=str(data.get("municipal_code")) if data.get("municipal_code") else None,
        )


class RegionContextStore:
    """Loader for RegionContext JSON blobs with catalog-based resolution."""

    def __init__(
        self,
        base_dir: Optional[os.PathLike[str] | str] = None,
        *,
        index_path: Optional[os.PathLike[str] | str] = None,
    ) -> None:
        base = str(base_dir or os.getenv("REGION_CONTEXT_DIR", "kb/region_context"))
        self._is_gcs = base.startswith("gs://")
        self._gcs_client: Optional[Any] = None
        self._catalog: Optional[List[_CatalogEntry]] = None
        if self._is_gcs:
            without_scheme = base[len("gs://") :]
            parts = without_scheme.split("/", 1)
            self._gcs_bucket = parts[0]
            self._gcs_prefix = parts[1].strip("/") if len(parts) > 1 else ""
            self.base_dir_path = None
        else:
            self.base_dir_path = Path(base)
        self._index_override = str(index_path) if index_path is not None else os.getenv("REGION_CONTEXT_INDEX")
        self._firestore_client: Optional[Any] = None
        self._firestore_collection = os.getenv("REGION_CONTEXT_COLLECTION", "regions")
        self._firestore_unavailable = False

    def _resolve_base(self) -> Path:
        base = getattr(self, "base_dir_path", None)
        if base is None:
            raise RuntimeError("RegionContextStore base path is not a filesystem path")
        if base.is_absolute():
            return base
        return Path(__file__).resolve().parents[1] / base

    _mapping_cache: Optional[list[dict[str, Any]]] = None

    @classmethod
    def _load_mapping_entries(cls) -> list[dict[str, Any]]:
        if cls._mapping_cache is not None:
            return cls._mapping_cache
        raw = os.getenv("REGION_CONTEXT_MAP", "").strip()
        entries: list[dict[str, Any]] = []
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    entries = [e for e in parsed if isinstance(e, dict)]
                elif isinstance(parsed, dict):
                    maybe_entries = parsed.get("entries")
                    if isinstance(maybe_entries, list):
                        entries = [e for e in maybe_entries if isinstance(e, dict)]
            except Exception:
                entries = []
        cls._mapping_cache = entries
        return cls._mapping_cache

    def _load_catalog(self) -> List[_CatalogEntry]:
        if self._catalog is not None:
            return self._catalog

        index_rel = self._index_override or "index.json"

        entries_data: List[Dict[str, Any]] = []
        try:
            if getattr(self, "_is_gcs", False):
                if storage is None:
                    raise RuntimeError("google-cloud-storage is required for REGION_CONTEXT_DIR=gs://...")
                client = self._gcs_client or storage.Client()  # type: ignore
                self._gcs_client = client
                prefix = getattr(self, "_gcs_prefix", "")
                object_name = index_rel.strip("/")
                if prefix:
                    object_name = f"{prefix}/{object_name}".strip("/")
                blob = client.bucket(self._gcs_bucket).blob(object_name)
                if blob.exists():
                    contents = blob.download_as_text(encoding="utf-8")
                    payload = json.loads(contents) if contents else {}
                    entries_section = payload.get("regions") if isinstance(payload, dict) else payload
                    if isinstance(entries_section, list):
                        entries_data = [e for e in entries_section if isinstance(e, dict) and e.get("path")]
            else:
                base = self._resolve_base()
                index_path = Path(index_rel)
                if not index_path.is_absolute():
                    index_path = base / index_rel
                if index_path.exists():
                    contents = index_path.read_text(encoding="utf-8")
                    payload = json.loads(contents) if contents else {}
                    entries_section = payload.get("regions") if isinstance(payload, dict) else payload
                    if isinstance(entries_section, list):
                        entries_data = [e for e in entries_section if isinstance(e, dict) and e.get("path")]
        except Exception:
            entries_data = []

        self._catalog = [_CatalogEntry.from_dict(entry) for entry in entries_data]
        return self._catalog

    @staticmethod
    def _score_entry(address: str, lat: Optional[float], lng: Optional[float], entry: _CatalogEntry) -> float:
        score = 0.0
        address = address or ""
        if entry.keywords:
            if all(kw in address for kw in entry.keywords):
                score += 3.0 + 0.25 * len(entry.keywords)
            else:
                missing = sum(1 for kw in entry.keywords if kw not in address)
                score -= missing
        if entry.preferred_names:
            matches = sum(1 for name in entry.preferred_names if name in address)
            score += matches * 0.5
        if entry.bbox and lat is not None and lng is not None:
            min_lng, min_lat, max_lng, max_lat = entry.bbox
            if min_lat <= float(lat) <= max_lat and min_lng <= float(lng) <= max_lng:
                score += 5.0
            else:
                score -= 2.0
        if entry.centroid and lat is not None and lng is not None:
            try:
                d_lat = abs(entry.centroid[1] - float(lat))
                d_lng = abs(entry.centroid[0] - float(lng))
                score += max(0.0, 2.0 - (d_lat + d_lng) * 50)
            except Exception:
                pass
        return score

    def _match_catalog_entry(self, location: Dict[str, Any]) -> Optional[_CatalogEntry]:
        address = str(location.get("address", ""))
        lat = location.get("lat")
        lng = location.get("lng")
        best_entry: Optional[_CatalogEntry] = None
        best_score = float("-inf")
        for entry in self._load_catalog():
            score = self._score_entry(address, lat, lng, entry)
            if score > best_score:
                best_score = score
                best_entry = entry
        if best_score > 0:
            return best_entry
        return None

    @classmethod
    def _match_legacy_entry(cls, location: Dict[str, Any]) -> Optional[str]:
        address = str(location.get("address", ""))
        lat = location.get("lat")
        lng = location.get("lng")

        for entry in cls._load_mapping_entries():
            filename = entry.get("file") or entry.get("filename")
            if not filename:
                continue
            keywords = entry.get("address_keywords") or entry.get("keywords") or []
            if keywords:
                if not all(isinstance(kw, str) and kw in address for kw in keywords):
                    continue
            bbox = entry.get("bbox") or entry.get("bounds")
            if bbox and all(isinstance(v, (int, float)) for v in bbox) and len(bbox) == 4:
                if lat is None or lng is None:
                    continue
                min_lng, min_lat, max_lng, max_lat = bbox
                if not (min_lat <= float(lat) <= max_lat and min_lng <= float(lng) <= max_lng):
                    continue
            return str(filename)

        return None

    @lru_cache(maxsize=32)
    def _load_json(self, filename: str) -> Dict[str, Any]:
        if getattr(self, "_is_gcs", False):
            if storage is None:
                raise RuntimeError("google-cloud-storage is required for REGION_CONTEXT_DIR=gs://...")
            client = self._gcs_client or storage.Client()  # type: ignore
            self._gcs_client = client
            prefix = getattr(self, "_gcs_prefix", "")
            object_name = filename
            if prefix and not filename.startswith(prefix):
                object_name = f"{prefix}/{filename}".strip("/")
            blob = client.bucket(self._gcs_bucket).blob(object_name)
            if not blob.exists():
                raise FileNotFoundError(object_name)
            contents = blob.download_as_text(encoding="utf-8")
            return json.loads(contents)
        path = Path(filename)
        if not path.is_absolute():
            path = self._resolve_base() / filename
        with path.open("r", encoding="utf-8") as fp:
            return json.load(fp)

    def load_for_location(self, location: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        catalog_entry = self._match_catalog_entry(location)
        if catalog_entry is not None:
            context = self._load_entry_context(catalog_entry)
            if context:
                return context
        legacy_key = self._match_legacy_entry(location)
        filename: Optional[str] = None
        if legacy_key:
            filename = f"{legacy_key}.json" if not legacy_key.endswith(".json") else legacy_key
        if not filename:
            return None
        try:
            context = self._load_json(filename)
        except FileNotFoundError:
            context = None
        except Exception:
            context = None
        if not context:
            return None
        meta = context.setdefault("meta", {}) if isinstance(context, dict) else {}
        if isinstance(meta, dict):
            meta.setdefault("region_context_id", legacy_key)
            meta.setdefault("source", meta.get("source", "legacy_map"))
        return context

    def derive_key(self, location: Dict[str, Any]) -> Optional[str]:
        entry = self._match_catalog_entry(location)
        if entry and entry.id:
            return entry.id
        legacy_key = self._match_legacy_entry(location)
        if legacy_key:
            return legacy_key
        return None

    def _firestore(self) -> Optional[Any]:
        if self._firestore_unavailable:
            return None
        if firestore is None:
            self._firestore_unavailable = True
            return None
        if self._firestore_client is not None:
            return self._firestore_client
        try:
            settings = Settings.load()
            self._firestore_client = firestore.Client(project=settings.project, database=settings.firestore_db)  # type: ignore[attr-defined]
            return self._firestore_client
        except Exception:
            self._firestore_unavailable = True
            return None

    def _load_from_firestore(self, doc_id: str) -> Optional[Dict[str, Any]]:
        if not doc_id:
            return None
        client = self._firestore()
        if client is None:
            return None
        try:
            snap = client.collection(self._firestore_collection).document(doc_id).get()  # type: ignore[attr-defined]
        except Exception:
            return None
        if not getattr(snap, "exists", False):
            return None
        data = snap.to_dict() or {}
        if isinstance(data, dict) and "context" in data and isinstance(data["context"], dict):
            context = data["context"]
        else:
            context = data
        if isinstance(context, dict):
            meta = context.setdefault("meta", {}) if isinstance(context, dict) else {}
            if isinstance(meta, dict):
                meta.setdefault("region_context_id", doc_id)
                meta.setdefault("source", "firestore_cache")
        return context if isinstance(context, dict) else None

    def _load_entry_context(self, entry: _CatalogEntry) -> Optional[Dict[str, Any]]:
        context: Optional[Dict[str, Any]] = None
        try:
            context = self._load_json(entry.path)
        except FileNotFoundError:
            context = None
        except Exception:
            context = None
        if not context and entry.id:
            context = self._load_from_firestore(entry.id)
        if not context:
            return None
        meta = context.setdefault("meta", {}) if isinstance(context, dict) else {}
        if isinstance(meta, dict):
            if entry.id:
                meta.setdefault("region_context_id", entry.id)
            meta.setdefault(
                "region_context_catalog",
                {
                    "path": entry.path,
                    "keywords": entry.keywords,
                    "bbox": entry.bbox,
                    "hazards": entry.hazards,
                    "municipal_code": entry.municipal_code,
                },
            )
        return context

    def load_by_id(self, region_id: str) -> Optional[Dict[str, Any]]:
        if not region_id:
            return None
        for entry in self._load_catalog():
            if entry.id == region_id:
                return self._load_entry_context(entry)
        # Not present in catalog; attempt Firestore cache directly
        context = self._load_from_firestore(region_id)
        if context and isinstance(context, dict):
            meta = context.setdefault("meta", {}) if isinstance(context, dict) else {}
            if isinstance(meta, dict):
                meta.setdefault("region_context_id", region_id)
                meta.setdefault("source", meta.get("source", "firestore_cache"))
        return context

    def list_catalog(self) -> List[Dict[str, Any]]:
        catalog = []
        for entry in self._load_catalog():
            catalog.append(
                {
                    "id": entry.id,
                    "path": entry.path,
                    "keywords": list(entry.keywords),
                    "bbox": list(entry.bbox) if entry.bbox else None,
                    "centroid": list(entry.centroid) if entry.centroid else None,
                    "slugs": list(entry.slugs),
                    "hazards": list(entry.hazards),
                    "preferred_names": list(entry.preferred_names),
                    "municipal_code": entry.municipal_code,
                }
            )
        return catalog

    def sync_to_firestore(self, *, collection: Optional[str] = None) -> List[str]:
        client = self._firestore()
        if client is None:
            raise RuntimeError("Firestore client is unavailable; ensure google-cloud-firestore is installed and credentials are configured")
        col_name = collection or self._firestore_collection
        saved: List[str] = []
        for entry in self._load_catalog():
            if not entry.path:
                continue
            context = self._load_entry_context(entry)
            if not context:
                continue
            context_copy = json.loads(json.dumps(context, ensure_ascii=False))
            meta = context_copy.setdefault("meta", {}) if isinstance(context_copy, dict) else {}
            if isinstance(meta, dict):
                meta.setdefault("synced_at", int(time.time()))
                meta.setdefault("source", meta.get("source", "filesystem"))
            doc_id = entry.id or Path(entry.path).stem
            try:
                client.collection(col_name).document(doc_id).set(context_copy)  # type: ignore[attr-defined]
                saved.append(doc_id)
            except Exception:
                continue
        return saved
