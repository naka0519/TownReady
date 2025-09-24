#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import types
import unittest
from pathlib import Path


def _install_stubs() -> None:
    if 'fastapi' not in sys.modules:
        fastapi_mod = types.ModuleType('fastapi')

        class _FakeFastAPI:
            def __init__(self, *_, **__):
                pass

            def get(self, *_args, **_kwargs):
                def decorator(func):
                    return func
                return decorator

            def post(self, *_args, **_kwargs):
                def decorator(func):
                    return func
                return decorator

            def middleware(self, *_args, **_kwargs):
                def decorator(func):
                    return func
                return decorator

        fastapi_mod.FastAPI = _FakeFastAPI  # type: ignore[attr-defined]

        class _HTTPException(Exception):
            def __init__(self, status_code: int, detail: str = "") -> None:
                super().__init__(detail)
                self.status_code = status_code
                self.detail = detail

        fastapi_mod.HTTPException = _HTTPException  # type: ignore[attr-defined]
        fastapi_mod.Header = lambda *args, **kwargs: None  # type: ignore[attr-defined]
        sys.modules['fastapi'] = fastapi_mod

    # google oauth stubs (worker import path)
    if 'google' not in sys.modules:
        sys.modules['google'] = types.ModuleType('google')
    google_module = sys.modules['google']
    oauth2_mod = types.ModuleType('google.oauth2')
    id_token_mod = types.ModuleType('google.oauth2.id_token')

    def _verify_oauth2_token(*_args, **_kwargs):
        return {'iss': 'https://accounts.google.com', 'email': 'stub@example.com'}

    id_token_mod.verify_oauth2_token = _verify_oauth2_token  # type: ignore[attr-defined]
    oauth2_mod.id_token = id_token_mod  # type: ignore[attr-defined]
    sys.modules['google.oauth2'] = oauth2_mod
    sys.modules['google.oauth2.id_token'] = id_token_mod

    auth_mod = types.ModuleType('google.auth')
    auth_mod.__path__ = []  # type: ignore[attr-defined]
    transport_mod = types.ModuleType('google.auth.transport')
    transport_mod.__path__ = []  # type: ignore[attr-defined]
    requests_mod = types.ModuleType('google.auth.transport.requests')

    class _Request:
        pass

    requests_mod.Request = _Request  # type: ignore[attr-defined]
    transport_mod.requests = requests_mod  # type: ignore[attr-defined]
    auth_mod.transport = transport_mod  # type: ignore[attr-defined]
    iam_mod = types.ModuleType('google.auth.iam')
    class _Signer:
        def __init__(self, *args, **kwargs):
            pass
        def sign(self, *args, **kwargs):
            return b''
    iam_mod.Signer = _Signer  # type: ignore[attr-defined]
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
        def __init__(self, *_args, **_kwargs):
            pass

        def bucket(self, *_args, **_kwargs):
            raise FileNotFoundError

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
    from GCP_AI_Agent_hackathon.workers.server import (  # type: ignore
        _build_plan,
        _build_safety,
        _build_scenario,
        _load_region_context,
        _plan_context_summary,
    )
except Exception:  # pragma: no cover
    import sys
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from workers.server import (  # type: ignore
        _build_plan,
        _build_safety,
        _build_scenario,
        _load_region_context,
        _plan_context_summary,
    )


class PlanScenarioFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        base_dir = Path(__file__).resolve().parents[1] / "kb" / "region_context"
        os.environ["REGION_CONTEXT_DIR"] = str(base_dir)

    def _job_payload(self):
        return {
            "location": {
                "address": "神奈川県横浜市戸塚区戸塚町７６９−１",
                "lat": 35.398961,
                "lng": 139.537466,
            },
            "participants": {
                "total": 120,
                "children": 20,
                "elderly": 18,
                "wheelchair": 3,
                "languages": ["ja", "en"],
            },
            "hazard": {
                "types": ["earthquake", "flood"],
                "drill_date": "2025-10-12",
                "indoor": True,
                "nighttime": False,
            },
        }

    def test_build_plan_includes_hazard_highlights(self):
        payload = self._job_payload()
        context = {
            "hazard_scores": {
                "flood_plan": {"coverage_km2": 1.2, "max_depth_m": 2.5},
            },
            "highlights": ["洪水: 最大浸水深 2.5m / 想定面積 1.2km²"],
            "meta": {"region_context_id": "region-14110"},
            "region": {"prefecture": "神奈川県", "city": "横浜市", "ward": "戸塚区"},
        }
        summary = _plan_context_summary(context)
        plan = _build_plan(payload, summary)
        self.assertIn("highlights", plan)
        must_include = plan["acceptance"]["must_include"]
        self.assertIn("止水板設置と高台ルート誘導の訓練", must_include)
        self.assertGreaterEqual(plan["acceptance"]["kpi_plan"]["targets"]["avg_evac_time_sec"], 360)
        self.assertIn("region_context_id", plan.get("context", {}))

    def test_build_scenario_adds_flood_routes_and_roles(self):
        payload = self._job_payload()
        context = {
            "hazard_scores": {
                "flood_plan": {"coverage_km2": 1.2},
            },
            "highlights": [],
            "meta": {"region_context_id": "region-14110"},
        }
        summary = _plan_context_summary(context)
        scenario = _build_scenario("job123", payload, storage=None, context_summary=summary)
        assets = scenario["assets"]
        route_names = {route["name"] for route in assets["routes"]}
        self.assertIn("高台避難導線", route_names)
        self.assertIn("避難導線リーダー", assets["roles_csv"])
        self.assertIn("## ハザード別の重点確認", assets["script_md"])
        self.assertIn("止水板設置", "\n".join(assets["highlights"]))
        self.assertEqual(assets.get("context", {}).get("region_context_id"), summary.get("region_context_id"))

    def test_safety_uses_context_highlights(self):
        payload = self._job_payload()
        context = {
            "hazard_scores": {
                "flood_plan": {"coverage_km2": 1.2},
                "landslide": {"coverage_km2": 0.4},
            },
            "highlights": ["洪水: 最大浸水深 2.5m / 想定面積 1.2km²"],
            "meta": {"region_context_id": "region-14110", "source": "test"},
        }
        summary = _plan_context_summary(context)
        scenario = _build_scenario("job456", payload, storage=None, context_summary=summary)
        safety = _build_safety(payload, scenario["assets"], context_summary=summary)
        self.assertEqual(safety.get("context", {}).get("source"), summary.get("source"))
        issues_joined = " ".join(issue.get("issue", "") for issue in safety["issues"])
        self.assertIn("浸水想定区域", issues_joined)
        region_issue = [issue for issue in safety["issues"] if issue.get("issue") == "地域特有のリスク共有"]
        self.assertTrue(region_issue)
        self.assertIn("洪水", " ".join(region_issue[0].get("highlights", [])))

    def test_region_context_fallback_when_missing(self):
        payload = self._job_payload()
        payload["location"] = {
            "address": "東京都千代田区丸の内１丁目",
            "lat": 35.681236,
            "lng": 139.767125,
        }
        payload["hazard"]["types"] = ["flood", "landslide"]
        context = _load_region_context(payload)
        self.assertIsNotNone(context)
        assert context is not None
        meta = context.get("meta", {})
        self.assertEqual(meta.get("source"), "fallback")
        summary = _plan_context_summary(context)
        self.assertEqual(summary.get("source"), "fallback")
        plan = _build_plan(payload, summary)
        self.assertIn("context", plan)
        scenario = _build_scenario("job789", payload, storage=None, context_summary=summary)
        self.assertIn("context", scenario["assets"])
        safety = _build_safety(payload, scenario["assets"], summary)
        self.assertEqual(safety.get("context", {}).get("source"), "fallback")
        issues_joined = " ".join(issue.get("issue", "") for issue in safety["issues"])
        self.assertIn("浸水想定区域", issues_joined)

    def test_facility_profile_adjusts_outputs(self):
        payload = self._job_payload()
        payload["facility_profile"] = {
            "id": "municipal-school",
            "category": "school",
            "kpi_targets": {
                "attendanceRate": 0.97,
                "avgEvacTimeSec": 210,
                "quizScore": 0.88,
            },
            "acceptance_additions": ["学年別引率班と保護者引き渡し動線の整備"],
            "timeline_focus": ["校内放送と防災倉庫の開錠手順確認"],
            "resource_focus": ["学級別名簿"],
        }
        context = {
            "hazard_scores": {
                "flood_plan": {"coverage_km2": 0.5},
            },
            "meta": {"region_context_id": "region-14110", "source": "catalog"},
        }
        summary = _plan_context_summary(context)
        plan = _build_plan(payload, summary)
        self.assertIn("facility_profile", plan)
        self.assertIn("学年別引率班と保護者引き渡し動線の整備", plan["acceptance"]["must_include"])
        self.assertGreater(plan["acceptance"]["kpi_plan"]["targets"]["attendance_rate"], 0.9)
        scenario = _build_scenario("job_facility", payload, storage=None, context_summary=summary)
        self.assertIn("facility_profile", scenario["assets"])
        self.assertIn("学級別名簿", scenario["assets"]["resource_checklist"])
        timeline_desc = " ".join(step.get("description", "") for step in scenario["assets"]["timeline"])
        self.assertIn("校内放送", timeline_desc)
        safety = _build_safety(payload, scenario["assets"], summary)
        issues_joined = " ".join(issue.get("issue", "") for issue in safety["issues"])
        self.assertIn("児童引き渡し計画", issues_joined)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
