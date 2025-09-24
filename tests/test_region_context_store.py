#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import types
import unittest
from pathlib import Path


def _install_stubs() -> None:
    if 'google' not in sys.modules:
        sys.modules['google'] = types.ModuleType('google')
    oauth2_mod = types.ModuleType('google.oauth2')
    id_token_mod = types.ModuleType('google.oauth2.id_token')
    id_token_mod.verify_oauth2_token = lambda *args, **kwargs: {'iss': 'https://accounts.google.com'}  # type: ignore[attr-defined]
    oauth2_mod.id_token = id_token_mod  # type: ignore[attr-defined]
    sys.modules['google.oauth2'] = oauth2_mod
    sys.modules['google.oauth2.id_token'] = id_token_mod

    auth_mod = types.ModuleType('google.auth')
    auth_mod.__path__ = []  # type: ignore[attr-defined]
    transport_mod = types.ModuleType('google.auth.transport')
    transport_mod.__path__ = []  # type: ignore[attr-defined]
    requests_mod = types.ModuleType('google.auth.transport.requests')
    requests_mod.Request = object  # type: ignore[attr-defined]
    transport_mod.requests = requests_mod  # type: ignore[attr-defined]
    auth_mod.transport = transport_mod  # type: ignore[attr-defined]
    iam_mod = types.ModuleType('google.auth.iam')
    iam_mod.Signer = object  # type: ignore[attr-defined]
    sys.modules['google.auth'] = auth_mod
    sys.modules['google.auth.transport'] = transport_mod
    sys.modules['google.auth.transport.requests'] = requests_mod
    sys.modules['google.auth.iam'] = iam_mod
    auth_mod.iam = iam_mod  # type: ignore[attr-defined]

    cloud_mod = types.ModuleType('google.cloud')
    storage_mod = types.ModuleType('google.cloud.storage')
    firestore_mod = types.ModuleType('google.cloud.firestore')
    pubsub_mod = types.ModuleType('google.cloud.pubsub')
    pubsub_v1_mod = types.ModuleType('google.cloud.pubsub_v1')

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def bucket(self, *args, **kwargs):
            class _Bucket:
                def blob(self, *_args, **_kwargs):
                    class _Blob:
                        def exists(self):
                            return False

                        def download_as_text(self, **_kwargs):
                            return ''

                    return _Blob()

            return _Bucket()

    storage_mod.Client = _Client  # type: ignore[attr-defined]
    firestore_mod.Client = _Client  # type: ignore[attr-defined]
    class _PublisherClient:
        def __init__(self, *args, **kwargs):
            pass

        def publish(self, *args, **kwargs):
            class _Future:
                def result(self):
                    return None
            return _Future()

    pubsub_mod.PublisherClient = _PublisherClient  # type: ignore[attr-defined]
    pubsub_v1_mod.PublisherClient = _PublisherClient  # type: ignore[attr-defined]
    sys.modules['google.cloud'] = cloud_mod
    sys.modules['google.cloud.storage'] = storage_mod
    sys.modules['google.cloud.firestore'] = firestore_mod
    sys.modules['google.cloud.pubsub'] = pubsub_mod
    sys.modules['google.cloud.pubsub_v1'] = pubsub_v1_mod
    cloud_mod.storage = storage_mod  # type: ignore[attr-defined]
    cloud_mod.firestore = firestore_mod  # type: ignore[attr-defined]
    cloud_mod.pubsub = pubsub_mod  # type: ignore[attr-defined]
    cloud_mod.pubsub_v1 = pubsub_v1_mod  # type: ignore[attr-defined]


_install_stubs()

try:
    from GCP_AI_Agent_hackathon.services.region_context import RegionContextStore  # type: ignore
except Exception:  # pragma: no cover - local path fallback
    import sys
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from services.region_context import RegionContextStore  # type: ignore


class RegionContextStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        # Ensure the store reads from repository fixtures
        base_dir = Path(__file__).resolve().parents[1] / "kb" / "region_context"
        os.environ["REGION_CONTEXT_DIR"] = str(base_dir)
        os.environ.pop("REGION_CONTEXT_INDEX", None)

    def test_loads_region_by_index(self) -> None:
        store = RegionContextStore()
        location = {
            "address": "神奈川県横浜市戸塚区戸塚町上倉田町７６９−１",
            "lat": 35.398961,
            "lng": 139.537466,
        }
        ctx = store.load_for_location(location)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        meta = ctx.get("meta", {})
        self.assertEqual(meta.get("region_context_id"), "region-14110")
        self.assertIn("hazard_scores", ctx)
        catalog = meta.get("region_context_catalog", {})
        self.assertEqual(catalog.get("path"), "region-14110.json")

    def test_derive_key_without_match(self) -> None:
        store = RegionContextStore()
        location = {"address": "Somewhere", "lat": 0.0, "lng": 0.0}
        key = store.derive_key(location)
        self.assertIsNone(key)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
