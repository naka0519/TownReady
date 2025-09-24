#!/usr/bin/env python3
"""Synchronize RegionContext JSON assets to Firestore and/or GCS.

This script is intended to keep RegionContext data in sync across
filesystem, Cloud Storage, and Firestore caches so that workers can
serve region-aware plans even when catalog files are unavailable at
runtime.

Typical usage:

    python scripts/region_context_sync.py --gcs-bucket my-bucket --gcs-prefix region_context

The script is best-effort; missing credentials or optional dependencies
will be reported but do not abort the entire sync unless --strict is
specified.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from services.region_context import RegionContextStore


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync RegionContext assets")
    parser.add_argument(
        "--source",
        default="kb/region_context",
        help="Directory that contains RegionContext JSON and index.json",
    )
    parser.add_argument(
        "--index",
        default=None,
        help="Override path to index.json (defaults to <source>/index.json)",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Firestore collection name for RegionContext cache (default: env REGION_CONTEXT_COLLECTION or 'regions')",
    )
    parser.add_argument(
        "--gcs-bucket",
        default=None,
        help="Upload JSON files to this Cloud Storage bucket (gs:// prefix optional)",
    )
    parser.add_argument(
        "--gcs-prefix",
        default="region_context",
        help="Prefix/path under the bucket to store JSON files",
    )
    parser.add_argument(
        "--include-index",
        action="store_true",
        help="Include index.json when uploading to GCS (default: skip)",
    )
    parser.add_argument(
        "--skip-firestore",
        action="store_true",
        help="Skip Firestore synchronization (default: sync if possible)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended actions without performing writes",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Raise an error on the first failure (default: report and continue)",
    )
    return parser.parse_args()


def _normalize_bucket(bucket: str) -> str:
    return bucket[len("gs://") :] if bucket.startswith("gs://") else bucket


def _sync_firestore(store: RegionContextStore, collection: str | None, dry_run: bool) -> Dict[str, Any]:
    result: Dict[str, Any] = {"target": "firestore"}
    if dry_run:
        catalog = store.list_catalog()
        result["catalog_size"] = len(catalog)
        result["note"] = "dry_run"
        return result
    try:
        saved = store.sync_to_firestore(collection=collection)
        result["saved"] = saved
    except Exception as exc:  # pragma: no cover - environment dependent
        result["error"] = str(exc)
    return result


def _sync_gcs(source_dir: Path, bucket: str, prefix: str, include_index: bool, dry_run: bool) -> Dict[str, Any]:
    report: Dict[str, Any] = {"target": "gcs", "bucket": bucket, "prefix": prefix}
    try:
        from google.cloud import storage  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        report["error"] = f"google-cloud-storage missing: {exc}"
        return report

    client = storage.Client()
    bucket_obj = client.bucket(bucket)
    uploaded: List[str] = []
    for path in sorted(source_dir.glob("*.json")):
        if path.name == "index.json" and not include_index:
            continue
        blob_path = "/".join(p for p in (prefix.strip("/"), path.name) if p)
        if dry_run:
            uploaded.append(blob_path)
            continue
        blob = bucket_obj.blob(blob_path)
        blob.upload_from_filename(str(path), content_type="application/json")
        uploaded.append(blob_path)
    report["uploaded"] = uploaded
    if dry_run:
        report["note"] = "dry_run"
    return report


def main() -> None:
    args = _parse_args()
    source_dir = Path(args.source)
    if not source_dir.exists():
        raise SystemExit(f"source directory not found: {source_dir}")

    index_path = Path(args.index) if args.index else None
    store = RegionContextStore(base_dir=source_dir, index_path=index_path)

    reports: List[Dict[str, Any]] = []

    if not args.skip_firestore:
        reports.append(_sync_firestore(store, args.collection, args.dry_run))

    if args.gcs_bucket:
        bucket = _normalize_bucket(args.gcs_bucket)
        reports.append(
            _sync_gcs(
                source_dir=source_dir,
                bucket=bucket,
                prefix=args.gcs_prefix,
                include_index=args.include_index,
                dry_run=args.dry_run,
            )
        )

    print(json.dumps({"reports": reports}, ensure_ascii=False, indent=2))

    if args.strict:
        for report in reports:
            if "error" in report:
                raise SystemExit(report["error"])


if __name__ == "__main__":
    main()
