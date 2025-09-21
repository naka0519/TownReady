from __future__ import annotations

import base64
import json
from typing import Any, Dict, List
import time
import random

from fastapi import FastAPI, HTTPException, Header
import logging
from typing import Optional

try:
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests
except Exception:  # pragma: no cover - libs should be present via google-cloud deps
    google_id_token = None  # type: ignore
    google_requests = None  # type: ignore

try:
    from GCP_AI_Agent_hackathon.services import JobsStore, Settings, Storage, Publisher, RegionContextStore
    from GCP_AI_Agent_hackathon.services.gemini_client import Gemini  # type: ignore
except Exception:
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from services import JobsStore, Settings, Storage, Publisher, RegionContextStore  # type: ignore
    try:
        from services.gemini_client import Gemini  # type: ignore
    except Exception:  # pragma: no cover
        Gemini = None  # type: ignore


app = FastAPI(title="TownReady Worker", version="0.2.0")
logger = logging.getLogger("townready.worker")

HAZARD_LABEL_JA = {
    "earthquake": "地震",
    "fire": "火災",
    "flood": "洪水",
    "tsunami": "津波",
    "landslide": "土砂災害",
}

HAZARD_ACCEPTANCE_TIPS = {
    "earthquake": "余震時の建物安全確認と負傷者搬送動線",
    "fire": "初期消火班の配置と消火設備の確認",
    "flood": "止水板設置と高台ルート誘導の訓練",
    "tsunami": "垂直避難の階段・屋上アクセス整備",
    "landslide": "急傾斜地の監視と立入禁止ゾーン設定",
}

HAZARD_FOCUS_JA = {
    "earthquake": "余震に備えて建物の損傷と危険物を確認し、安全が確保できたエリアから段階的に避難を開始します。",
    "fire": "初期消火班が消火器・屋内消火栓を点検し、安全距離を確保したうえで避難誘導を行います。",
    "flood": "止水板と吸水土嚢を配置し、高台ルートの先導員を先行させて浸水域を避けます。",
    "tsunami": "沿岸警戒情報を監視し、階段と屋上スペースを確保して3分以内に垂直避難を開始します。",
    "landslide": "急傾斜地付近に監視要員を配置し、立入禁止区間にバリケードを設置します。",
}

BASE_ROLES_JA: List[Tuple[str, str, str]] = [
    ("統括責任者", "田中", "全体統括と状況判断"),
    ("安全管理", "佐藤", "安全監視と危険エリア封鎖"),
    ("救護担当", "鈴木", "応急手当と搬送手配"),
]

HAZARD_ROLE_APPEND_JA: Dict[str, Tuple[str, str, str]] = {
    "flood": ("避難導線リーダー", "高橋", "高台・垂直避難の先導"),
    "tsunami": ("避難導線リーダー", "高橋", "高台・垂直避難の先導"),
    "fire": ("初期消火班", "中村", "消火器・屋内消火栓の操作"),
}


def _load_region_context(job_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        store = RegionContextStore()
        location = job_payload.get("location") or {}
        context = store.load_for_location(location)
        if isinstance(context, dict):
            meta = context.setdefault("meta", {})
            if not meta.get("region_context_id"):
                key = store.derive_key(location)
                if key:
                    meta["region_context_id"] = key
        return context
    except Exception:
        return None


def _plan_context_summary(region_ctx: Dict[str, Any]) -> Dict[str, Any]:
    scores = region_ctx.get("hazard_scores") or {}
    notes: List[str] = []
    flood = scores.get("flood_plan") or {}
    if flood:
        max_depth = flood.get("max_depth_m")
        coverage = flood.get("coverage_km2")
        note = "洪水: 最大浸水深" + (f" {max_depth}m" if max_depth is not None else " 不明")
        if coverage:
            note += f" / 想定面積 {coverage}km²"
        notes.append(note)
    landslide = scores.get("landslide") or {}
    if landslide:
        coverage = landslide.get("coverage_km2")
        note = "急傾斜地崩壊: 登録区域" + (f" {coverage}km²" if coverage else " 有")
        notes.append(note)
    summary: Dict[str, Any] = {"hazard_scores": scores}
    region_meta = region_ctx.get("meta", {}) if isinstance(region_ctx, dict) else {}
    region_info = region_ctx.get("region") if isinstance(region_ctx, dict) else None
    if isinstance(region_meta, dict) and region_meta.get("region_context_id"):
        summary["region_context_id"] = region_meta.get("region_context_id")
    if isinstance(region_info, dict):
        summary["region"] = {
            key: val
            for key, val in region_info.items()
            if key in ("prefecture", "city", "ward") and val
        }
    if notes:
        summary["highlights"] = notes
    return summary


def _generate_japanese_script(location: Dict[str, Any], hazard_types: Iterable[str]) -> str:
    hazard_types_list = [str(h) for h in hazard_types if h]
    hazard_labels = "、".join(HAZARD_LABEL_JA.get(h, h) for h in hazard_types_list) or "複合災害"
    focus_lines: List[str] = []
    for htype in hazard_types_list:
        note = HAZARD_FOCUS_JA.get(htype)
        if note and note not in focus_lines:
            focus_lines.append(f"- {note}")

    parts = [
        "# 訓練台本",
        "",
        f"- 場所: {location.get('address', '')}",
        f"- 想定: {hazard_labels}",
        "",
        "## 手順",
        "1. 集合・点呼",
        "2. 初期対応（安全確認/初期消火）",
        "3. 避難誘導（要配慮者を先導）",
        "4. 振り返り・改善共有",
    ]
    if focus_lines:
        parts.extend(["", "## ハザード別の重点確認", *focus_lines])
    return "\n".join(parts) + "\n"


def _generate_japanese_roles(hazard_types: Iterable[str]) -> str:
    hazard_types_list = [str(h) for h in hazard_types if h]
    rows = list(BASE_ROLES_JA)
    existing = {role for role, _, _ in rows}
    for htype in hazard_types_list:
        role_entry = HAZARD_ROLE_APPEND_JA.get(htype)
        if role_entry and role_entry[0] not in existing:
            rows.append(role_entry)
            existing.add(role_entry[0])
    header = "\ufeff役割,氏名,担当\n"
    body = "\n".join(f"{role},{name},{resp}" for role, name, resp in rows)
    return header + body + "\n"


def _augment_plan_payload(plan: Dict[str, Any], context_summary: Optional[Dict[str, Any]]) -> None:
    if not context_summary:
        return
    hazard_scores = context_summary.get("hazard_scores", {})
    acceptance = plan.setdefault("acceptance", {})
    must_include = acceptance.setdefault("must_include", [])
    if hazard_scores.get("flood_plan") and "洪水想定エリアでの避難動線確認" not in must_include:
        must_include.append("洪水想定エリアでの避難動線確認")
    if hazard_scores.get("landslide") and "急傾斜地付近での安全導線点検" not in must_include:
        must_include.append("急傾斜地付近での安全導線点検")
    plan["context"] = context_summary


def _build_routes(
    loc: Dict[str, Any],
    context_summary: Optional[Dict[str, Any]],
    hazard_types: Iterable[str],
) -> List[Dict[str, Any]]:
    base_lat = loc.get("lat") or 0.0
    base_lng = loc.get("lng") or 0.0

    def _offset(lat_delta: float, lng_delta: float) -> Dict[str, float]:
        return {"lat": round(base_lat + lat_delta, 6), "lng": round(base_lng + lng_delta, 6)}

    hazard_set = {str(h) for h in hazard_types if h}
    routes: List[Dict[str, Any]] = [
        {
            "name": "主要導線",
            "type": "main",
            "points": [
                {**_offset(0.0, 0.0), "label": "開始地点"},
                {**_offset(0.0005, 0.0005), "label": "集合地点"},
                {**_offset(0.001, 0.001), "label": "指定避難所"},
            ],
            "notes": "通常導線。建物前広場を経由して指定避難所へ移動します。",
        },
        {
            "name": "バリアフリー導線",
            "type": "accessible",
            "points": [
                {**_offset(0.0, 0.0), "label": "開始地点"},
                {**_offset(0.0004, -0.0003), "label": "スロープ"},
                {**_offset(0.0009, -0.0001), "label": "指定避難所"},
            ],
            "notes": "スロープを利用した車椅子対応導線。介助者2名を配置して段差を回避します。",
        },
    ]

    hazard_scores = (context_summary or {}).get("hazard_scores", {})
    if hazard_scores.get("flood_plan") or "flood" in hazard_set:
        routes.append(
            {
                "name": "高台避難導線",
                "type": "alternate",
                "points": [
                    {**_offset(0.0, 0.0), "label": "開始地点"},
                    {**_offset(-0.0006, 0.0004), "label": "高台入口"},
                    {**_offset(-0.0012, 0.0008), "label": "第二避難所"},
                ],
                "notes": "浸水リスクを避けるための高台ルート。夜間照明と案内表示を事前確認します。",
            }
        )
    if "tsunami" in hazard_set:
        routes.append(
            {
                "name": "垂直避難導線",
                "type": "alternate",
                "points": [
                    {**_offset(0.0, 0.0), "label": "開始地点"},
                    {**_offset(0.0002, 0.0001), "label": "屋内階段"},
                    {**_offset(0.0002, 0.0001), "label": "屋上避難スペース"},
                ],
                "notes": "津波警報発令時に3分以内で屋上へ避難するための垂直導線。手すり点検と照明確保が必要です。",
            }
        )
    if "fire" in hazard_set:
        routes.append(
            {
                "name": "防火巡回導線",
                "type": "inspection",
                "points": [
                    {**_offset(0.0, 0.0), "label": "開始地点"},
                    {**_offset(0.0003, 0.0002), "label": "屋内消火栓"},
                    {**_offset(0.0006, 0.0001), "label": "集合地点"},
                ],
                "notes": "消火班が消防設備を確認しながら巡回する導線。避難開始前に安全距離を確保します。",
            }
        )
    return routes


def _build_timeline(
    context_summary: Optional[Dict[str, Any]],
    hazard_types: Iterable[str],
) -> List[Dict[str, Any]]:
    timeline = [
        {"step": "集合・点呼", "timestamp_offset_sec": 0, "description": "集合場所でグループ分けと人数確認"},
        {"step": "初期対応", "timestamp_offset_sec": 180, "description": "負傷者確認と初期消火・救護班の展開"},
        {"step": "避難開始", "timestamp_offset_sec": 360, "description": "メイン導線で避難開始。車椅子/要配慮者は先行"},
        {"step": "避難所到着", "timestamp_offset_sec": 780, "description": "受付で名簿照合。医療班が体調チェック"},
        {"step": "振り返り", "timestamp_offset_sec": 1200, "description": "ハイライト共有と改善点の洗い出し"},
    ]

    hazard_scores = (context_summary or {}).get("hazard_scores", {})
    hazard_set = {str(h) for h in hazard_types if h}
    if hazard_scores.get("flood_plan"):
        timeline.insert(
            3,
            {
                "step": "浸水箇所確認",
                "timestamp_offset_sec": 480,
                "description": "浸水想定エリアのバリケード設置と誘導員配置を確認",
            },
        )
    if hazard_scores.get("landslide"):
        timeline.insert(
            3,
            {
                "step": "急傾斜地確認",
                "timestamp_offset_sec": 420,
                "description": "土砂崩れ警戒区域の見回りと通行禁止ゾーンの設定",
            },
        )
    if "fire" in hazard_set:
        timeline.insert(
            2,
            {
                "step": "初期消火訓練",
                "timestamp_offset_sec": 240,
                "description": "消火器/屋内消火栓の操作訓練と安全確認",
            },
        )
    if "earthquake" in hazard_set:
        timeline.insert(
            1,
            {
                "step": "建物安全チェック",
                "timestamp_offset_sec": 90,
                "description": "余震想定の安全確認と倒壊リスク区域の封鎖",
            },
        )
    if "tsunami" in hazard_set:
        timeline.insert(
            4,
            {
                "step": "高台/屋上退避",
                "timestamp_offset_sec": 600,
                "description": "沿岸警戒情報の共有と垂直避難ルートの点検",
            },
        )
    return timeline


def _build_resource_checklist(
    context_summary: Optional[Dict[str, Any]],
    hazard_types: Iterable[str],
) -> List[str]:
    checklist = [
        "誘導用ベスト/ライト (10 セット)",
        "救護セット (AED / 応急キット)",
        "多言語アナウンス資料 (日英)",
    ]
    hazard_scores = (context_summary or {}).get("hazard_scores", {})
    hazard_set = {str(h) for h in hazard_types if h}
    if hazard_scores.get("flood_plan"):
        checklist.append("止水板・吸水土嚢・ポンプの点検")
    if hazard_scores.get("landslide"):
        checklist.append("土砂崩れ警戒区域のバリケードとメガホン")
    if "fire" in hazard_set:
        checklist.append("消火器・屋内消火栓・防火シャッターの点検")
    if "earthquake" in hazard_set:
        checklist.append("ヘルメット・簡易担架・ジャッキの準備")
    if "tsunami" in hazard_set:
        checklist.append("津波避難ビブス・スピーカー・携帯無線の充電確認")
    return checklist


def _augment_scenario_assets(
    assets: Dict[str, Any],
    job_payload: Dict[str, Any],
    context_summary: Optional[Dict[str, Any]],
) -> None:
    loc = job_payload.get("location", {})
    hazard_types = [str(t) for t in job_payload.get("hazard", {}).get("types", []) or []]
    routes = _build_routes(loc, context_summary, hazard_types)
    if not assets.get("routes"):
        assets["routes"] = routes
    elif context_summary and context_summary.get("hazard_scores", {}).get("flood_plan"):
        # Ensure alternate route is present when flood risk exists
        existing_names = {r.get("name") for r in assets.get("routes", []) if isinstance(r, dict)}
        for route in routes:
            if route.get("name") == "高台避難導線" and route.get("name") not in existing_names:
                assets.setdefault("routes", []).append(route)

    timeline = _build_timeline(context_summary, hazard_types)
    if not assets.get("timeline"):
        assets["timeline"] = timeline

    checklist = _build_resource_checklist(context_summary, hazard_types)
    if not assets.get("resource_checklist"):
        assets["resource_checklist"] = checklist


def _inject_highlights_into_script(
    script: str,
    highlights: List[str],
    lang: str,
) -> str:
    if not highlights:
        return script
    section_title = "## Local Risk Highlights"
    bullet = "- "
    if lang == "ja":
        section_title = "## 地域特有の注意"
    lines = ["", section_title] + [f"{bullet}{note}" for note in highlights]
    return script.rstrip() + "\n" + "\n".join(lines) + "\n"


@app.get("/")
def root() -> Dict[str, str]:
    return {"status": "ok", "service": "worker"}


# @app.get("/healthz")
# def healthz() -> Dict[str, str]:
#     return {"status": "ok"}


# Some Cloud Run frontends may treat "/healthz" specially. Provide an alias.
@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


def _verify_push(authorization: Optional[str]) -> bool:
    """Verify Pub/Sub OIDC token if enabled via settings.

    Returns True if verification passes or is disabled. False otherwise.
    """
    try:
        settings = Settings.load()
        if not getattr(settings, "push_verify", False):
            return True
        if not authorization or not authorization.lower().startswith("bearer "):
            return False
        if google_id_token is None or google_requests is None:
            return False
        token = authorization.split(" ", 1)[1].strip()
        req = google_requests.Request()
        claims = google_id_token.verify_oauth2_token(token, req, settings.push_audience)
        iss = claims.get("iss", "")
        if not ("accounts.google.com" in iss):
            return False
        expected_email = getattr(settings, "push_service_account", None)
        if expected_email and claims.get("email") != expected_email:
            return False
        return True
    except Exception:
        return False


def _build_plan(
    job_payload: Dict[str, Any],
    context_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    # Optional Gemini generation (staged via env)
    try:
        settings = Settings.load()
        if getattr(settings, "use_gemini", False) and Gemini is not None:
            g = Gemini(settings)
            payload_for_model = dict(job_payload)
            if context_summary:
                payload_for_model = dict(payload_for_model)
                payload_for_model["region_context"] = context_summary
            raw = g.generate_plan(payload_for_model)
            # normalize minimal keys
            scenarios = raw.get("scenarios") or []
            acceptance = raw.get("acceptance") or {}
            handoff = raw.get("handoff") or {"to": "Scenario Agent", "with": {}}
            plan = {"scenarios": scenarios, "acceptance": acceptance, "handoff": handoff}
            _augment_plan_payload(plan, context_summary)
            return plan
    except Exception as e:
        logger.exception("gemini_plan_failed: %s", e)
    loc = job_payload.get("location", {})
    parts = job_payload.get("participants", {})
    hazard = job_payload.get("hazard", {})
    langs: List[str] = parts.get("languages") or ["ja"]
    types: List[str] = [str(t) for t in hazard.get("types") or []]

    labels = [HAZARD_LABEL_JA.get(t, t) for t in types]
    highlighted_sequence = "→".join(labels) if labels else "避難誘導"
    titles: List[str] = []
    if labels:
        titles.append(highlighted_sequence)
    else:
        titles.append("避難誘導")

    scenarios = [
        {"id": f"S{i+1}", "title": t, "languages": langs} for i, t in enumerate(titles)
    ]
    base_attendance = 0.6 + min(0.3, (parts.get("children", 0) + parts.get("elderly", 0)) / max(parts.get("total", 1), 1) * 0.2)
    avg_evac = 300
    if "flood" in types:
        avg_evac = 420
    if "tsunami" in types:
        avg_evac = max(avg_evac, 480)
    if parts.get("wheelchair", 0) > 0:
        avg_evac += 60
    kpi_collection = ["checkin", "route_time", "post_quiz"]
    if "fire" in types and "extinguisher_drill_feedback" not in kpi_collection:
        kpi_collection.append("extinguisher_drill_feedback")
    if "flood" in types and "water_barrier_check" not in kpi_collection:
        kpi_collection.append("water_barrier_check")
    if "tsunami" in types and "vertical_evacuation_time" not in kpi_collection:
        kpi_collection.append("vertical_evacuation_time")

    seen_channels = set()
    kpi_collection_ordered: List[str] = []
    for channel in kpi_collection:
        if channel not in seen_channels:
            seen_channels.add(channel)
            kpi_collection_ordered.append(channel)

    kpi = {
        "targets": {
            "attendance_rate": round(min(base_attendance, 0.85), 2),
            "avg_evac_time_sec": int(avg_evac),
            "quiz_score": 0.75 if "fire" in types else 0.7,
        },
        "collection": kpi_collection_ordered,
    }
    acceptance_list = ["要配慮者ルート", "多言語掲示", "役割表CSV"]
    if parts.get("wheelchair", 0) > 0 and "バリアフリー導線事前確認" not in acceptance_list:
        acceptance_list.append("バリアフリー導線事前確認")
    for hazard_type in types:
        tip = HAZARD_ACCEPTANCE_TIPS.get(hazard_type)
        if tip and tip not in acceptance_list:
            acceptance_list.append(tip)
    hazard_scores: Dict[str, Any] = context_summary.get("hazard_scores", {}) if context_summary else {}
    acceptance = {"must_include": acceptance_list, "kpi_plan": kpi}
    plan_highlights: List[str] = []
    if context_summary and context_summary.get("highlights"):
        plan_highlights.extend(context_summary.get("highlights", []))
    for hazard_type in types:
        tip = HAZARD_ACCEPTANCE_TIPS.get(hazard_type)
        if tip and tip not in plan_highlights:
            plan_highlights.append(tip)
    plan = {
        "scenarios": scenarios,
        "acceptance": acceptance,
        "handoff": {"to": "Scenario Agent", "with": {"scenario_id": scenarios[0]["id"]}},
        "location": {"address": loc.get("address"), "lat": loc.get("lat"), "lng": loc.get("lng")},
    }
    if plan_highlights:
        plan["highlights"] = plan_highlights
    _augment_plan_payload(plan, context_summary)
    return plan


def _build_scenario(
    job_id: str,
    job_payload: Dict[str, Any],
    storage: Optional[Storage],
    context_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    # Optional Gemini generation (staged via env)
    try:
        settings = Settings.load()
        if getattr(settings, "use_gemini", False) and Gemini is not None:
            g = Gemini(settings)
            payload_for_model = dict(job_payload)
            if context_summary:
                payload_for_model = dict(payload_for_model)
                payload_for_model["region_context"] = context_summary
            raw = g.generate_scenario(payload_for_model) or {}
            assets_in = raw.get("assets") or raw
            routes = assets_in.get("routes") or []
            langs = assets_in.get("languages") or (job_payload.get("participants", {}).get("languages") or ["ja"])
            hazard_types = [str(t) for t in (job_payload.get("hazard", {}).get("types") or [])]
            script_md = _generate_japanese_script(job_payload.get("location", {}), hazard_types)
            roles_csv = _generate_japanese_roles(hazard_types)
            assets: Dict[str, Any] = {"script_md": script_md, "roles_csv": roles_csv, "routes": routes, "languages": langs}
            if context_summary:
                assets["context"] = context_summary
            assets.setdefault("timeline", _build_timeline(context_summary, hazard_types))
            assets.setdefault("resource_checklist", _build_resource_checklist(context_summary, hazard_types))
            _augment_scenario_assets(assets, job_payload, context_summary)
            highlights_g = list(context_summary.get("highlights", []) if context_summary else [])
            hazard_tips = [HAZARD_ACCEPTANCE_TIPS.get(ht) for ht in hazard_types if HAZARD_ACCEPTANCE_TIPS.get(ht)]
            for tip in hazard_tips:
                if tip and tip not in highlights_g:
                    highlights_g.append(tip)
            if highlights_g and isinstance(assets.get("script_md"), str):
                primary_lang = langs[0] if isinstance(langs, list) and langs else "ja"
                assets["script_md"] = _inject_highlights_into_script(assets["script_md"], highlights_g, primary_lang)
                script_md = assets["script_md"]
            if highlights_g and not assets.get("highlights"):
                assets["highlights"] = highlights_g
            if storage:
                script_path = f"jobs/{job_id}/script.md"
                roles_path = f"jobs/{job_id}/roles.csv"
                routes_path = f"jobs/{job_id}/routes.json"
                assets["script_md_uri"] = storage.upload_text(script_path, script_md, "text/markdown")
                assets["roles_csv_uri"] = storage.upload_text(roles_path, roles_csv, "text/csv")
                assets["routes_json_uri"] = storage.upload_text(routes_path, json.dumps(routes, ensure_ascii=False, indent=2), "application/json")
                try:
                    settings2 = Settings.load()
                    assets["script_md_url"] = storage.signed_url(script_path, ttl_seconds=settings2.signed_url_ttl, download_name="script.md")
                    assets["roles_csv_url"] = storage.signed_url(roles_path, ttl_seconds=settings2.signed_url_ttl, download_name="roles.csv")
                    assets["routes_json_url"] = storage.signed_url(routes_path, ttl_seconds=settings2.signed_url_ttl, download_name="routes.json")
                except Exception as se:  # pragma: no cover
                    logger.exception("signed_url_failed_scenario_gemini: %s", se)
            return {"type": "scenario", "assets": assets}
    except Exception as e:
        logger.exception("gemini_scenario_failed: %s", e)
    loc = job_payload.get("location", {})
    parts = job_payload.get("participants", {})
    hazard = job_payload.get("hazard", {})
    hazard_types = [str(t) for t in hazard.get("types", []) or []]
    langs: List[str] = parts.get("languages") or ["ja"]

    highlights: List[str] = []
    if context_summary:
        highlights = list(context_summary.get("highlights", []) or [])
    for hazard_type in hazard_types:
        tip = HAZARD_ACCEPTANCE_TIPS.get(hazard_type)
        if tip and tip not in highlights:
            highlights.append(tip)

    routes = _build_routes(loc, context_summary, hazard_types)
    timeline = _build_timeline(context_summary, hazard_types)
    resource_checklist = _build_resource_checklist(context_summary, hazard_types)
    script_base = _generate_japanese_script(loc, hazard_types)
    roles_base = _generate_japanese_roles(hazard_types)

    # Base assets and per-language containers
    assets: Dict[str, Any] = {
        "routes": routes,
        "languages": langs,
        "timeline": timeline,
        "resource_checklist": resource_checklist,
        "highlights": highlights,
    }
    if context_summary:
        assets["context"] = context_summary
    by_lang: Dict[str, Any] = {}
    primary = (langs[0] if len(langs) else "ja")
    if storage:
        routes_path = f"jobs/{job_id}/routes.json"
        assets["routes_json_uri"] = storage.upload_text(
            routes_path, json.dumps(routes, ensure_ascii=False, indent=2), "application/json"
        )
    # Generate per-language script/roles
    for lang in langs:
        script = _inject_highlights_into_script(script_base, highlights, lang)
        roles = roles_base
        entry: Dict[str, Any] = {"lang": lang, "script_md": script, "roles_csv": roles}
        if storage:
            script_path = f"jobs/{job_id}/{lang}/script.md"
            roles_path = f"jobs/{job_id}/{lang}/roles.csv"
            entry["script_md_uri"] = storage.upload_text(script_path, script, "text/markdown")
            entry["roles_csv_uri"] = storage.upload_text(roles_path, roles, "text/csv")
        by_lang[lang] = entry
        # Backward-compat: set top-level for primary language
        if lang == primary:
            assets.update({"script_md": script, "roles_csv": roles})
            if storage:
                try:
                    from GCP_AI_Agent_hackathon.services import Settings as _Settings
                except Exception:
                    import sys as _sys
                    from pathlib import Path as _Path
                    _sys.path.append(str(_Path(__file__).resolve().parents[1]))
                    from services import Settings as _Settings  # type: ignore
                settings = _Settings.load()
                try:
                    assets["script_md_url"] = storage.signed_url(f"jobs/{job_id}/{lang}/script.md", ttl_seconds=settings.signed_url_ttl, download_name="script.md")
                    assets["roles_csv_url"] = storage.signed_url(f"jobs/{job_id}/{lang}/roles.csv", ttl_seconds=settings.signed_url_ttl, download_name="roles.csv")
                except Exception as e:
                    logger.exception("signed_url_failed_scenario_primary: job=%s lang=%s err=%s", job_id, lang, e)
    # Signed URL for routes
    if storage:
        try:
            from GCP_AI_Agent_hackathon.services import Settings as _Settings
        except Exception:
            import sys as _sys
            from pathlib import Path as _Path
            _sys.path.append(str(_Path(__file__).resolve().parents[1]))
            from services import Settings as _Settings  # type: ignore
        settings = _Settings.load()
        try:
            assets["routes_json_url"] = storage.signed_url(f"jobs/{job_id}/routes.json", ttl_seconds=settings.signed_url_ttl, download_name="routes.json")
            # Signed URLs for each language entries
            for lang, entry in by_lang.items():
                try:
                    entry["script_md_url"] = storage.signed_url(f"jobs/{job_id}/{lang}/script.md", ttl_seconds=settings.signed_url_ttl, download_name=f"script_{lang}.md")
                    entry["roles_csv_url"] = storage.signed_url(f"jobs/{job_id}/{lang}/roles.csv", ttl_seconds=settings.signed_url_ttl, download_name=f"roles_{lang}.csv")
                except Exception as e:
                    logger.exception("signed_url_failed_scenario_lang: job=%s lang=%s err=%s", job_id, lang, e)
        except Exception as e:
            logger.exception("signed_url_failed_scenario_routes: job=%s err=%s", job_id, e)
    assets["by_language"] = by_lang
    return {"type": "scenario", "assets": assets}


def _build_safety(job_payload: Dict[str, Any], scenario_assets: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    parts = job_payload.get("participants", {})
    hazard = job_payload.get("hazard", {})
    cons = job_payload.get("constraints", {})
    if (parts.get("elderly", 0) + parts.get("wheelchair", 0)) > 0:
        issues.append({
            "severity": "low",
            "issue": "要配慮者対応の明記",
            "fix": "避難手順に介助役割とバリアフリールートを追加",
            "kb": "kb://accessibility_guideline",
        })
    if cons.get("limited_outdoor"):
        issues.append({
            "severity": "medium",
            "issue": "屋外活動の制限",
            "fix": "屋内で完結する訓練手順を明記",
            "kb": "kb://indoor_safety",
        })
    if "fire" in (hazard.get("types") or []):
        issues.append({
            "severity": "low",
            "issue": "初期消火の安全距離",
            "fix": "消火器使用時は退避線を設定",
            "kb": "kb://fire_extinguisher",
        })
    # Best-effort: attach KB anchors for each issue
    try:
        try:
            from GCP_AI_Agent_hackathon.services.kb_search import KBSearch  # type: ignore
        except Exception:
            import sys
            from pathlib import Path
            sys.path.append(str(Path(__file__).resolve().parents[1]))
            from services.kb_search import KBSearch  # type: ignore

        kb = KBSearch()
        for it in issues:
            q = it.get("issue") or "避難 ガイドライン"
            try:
                it["kb_hits"] = kb.search(q, page_size=2)
            except Exception:
                pass
    except Exception:
        pass

    return {"type": "safety", "issues": issues, "patched": True}


def _build_content(job_payload: Dict[str, Any], scenario_assets: Dict[str, Any], storage: Optional[Storage], job_id: str) -> Dict[str, Any]:
    parts = job_payload.get("participants", {})
    hazard = job_payload.get("hazard", {})
    langs: List[str] = parts.get("languages") or ["ja"]
    types: List[str] = hazard.get("types") or []
    poster_prompts = [f"{','.join(types)} 対応の避難誘導ポスター（{lang}）" for lang in langs]
    video_prompt = f"{','.join(types)} 訓練の60秒VTR（多言語）"
    shotlist = [
        {"description": "集合・点呼の様子", "duration_sec": 10},
        {"description": "初期対応（安全確認/消火）", "duration_sec": 15},
        {"description": "避難誘導（ルート案内）", "duration_sec": 25},
        {"description": "振り返り・注意喚起", "duration_sec": 10},
    ]
    uris: Dict[str, Any] = {}
    by_lang: Dict[str, Any] = {}
    if storage:
        # Load settings for signed URL TTL and filename hints
        try:
            from GCP_AI_Agent_hackathon.services import Settings as _Settings  # type: ignore
        except Exception:
            import sys as _sys
            from pathlib import Path as _Path
            _sys.path.append(str(_Path(__file__).resolve().parents[1]))
            from services import Settings as _Settings  # type: ignore
        settings = _Settings.load()
        # Aggregate files (legacy)
        poster_path = f"jobs/{job_id}/poster_prompts.txt"
        video_prompt_path = f"jobs/{job_id}/video_prompt.txt"
        shotlist_path = f"jobs/{job_id}/video_shotlist.json"
        uris["poster_prompts_uri"] = storage.upload_text(poster_path, "\n".join(poster_prompts), "text/plain")
        uris["video_prompt_uri"] = storage.upload_text(video_prompt_path, video_prompt, "text/plain")
        uris["video_shotlist_uri"] = storage.upload_text(shotlist_path, json.dumps(shotlist, ensure_ascii=False, indent=2), "application/json")
        # Per-language files
        for lang in langs:
            try:
                p_path = f"jobs/{job_id}/{lang}/poster_prompts.txt"
                v_path = f"jobs/{job_id}/{lang}/video_prompt.txt"
                s_path = f"jobs/{job_id}/{lang}/video_shotlist.json"
                # Simple per-language prompts: mirror aggregate but tagged per lang
                p_text = f"{','.join(types)} poster prompts ({lang})"
                v_text = f"60-second drill video ({lang})"
                by_lang.setdefault(lang, {})
                by_lang[lang]["poster_prompts_uri"] = storage.upload_text(p_path, p_text, "text/plain")
                by_lang[lang]["video_prompt_uri"] = storage.upload_text(v_path, v_text, "text/plain")
                by_lang[lang]["video_shotlist_uri"] = storage.upload_text(s_path, json.dumps(shotlist, ensure_ascii=False, indent=2), "application/json")
            except Exception as e:
                logger.exception("content_lang_write_failed: job=%s lang=%s err=%s", job_id, lang, e)
        # Best-effort: signed URLs
        try:
            uris["poster_prompts_url"] = storage.signed_url(poster_path, ttl_seconds=settings.signed_url_ttl, download_name="poster_prompts.txt")
            uris["video_prompt_url"] = storage.signed_url(video_prompt_path, ttl_seconds=settings.signed_url_ttl, download_name="video_prompt.txt")
            uris["video_shotlist_url"] = storage.signed_url(shotlist_path, ttl_seconds=settings.signed_url_ttl, download_name="video_shotlist.json")
            for lang in by_lang.keys():
                try:
                    by_lang[lang]["poster_prompts_url"] = storage.signed_url(f"jobs/{job_id}/{lang}/poster_prompts.txt", ttl_seconds=settings.signed_url_ttl, download_name=f"poster_prompts_{lang}.txt")
                    by_lang[lang]["video_prompt_url"] = storage.signed_url(f"jobs/{job_id}/{lang}/video_prompt.txt", ttl_seconds=settings.signed_url_ttl, download_name=f"video_prompt_{lang}.txt")
                    by_lang[lang]["video_shotlist_url"] = storage.signed_url(f"jobs/{job_id}/{lang}/video_shotlist.json", ttl_seconds=settings.signed_url_ttl, download_name=f"video_shotlist_{lang}.json")
                except Exception as e:
                    logger.exception("content_lang_signed_failed: job=%s lang=%s err=%s", job_id, lang, e)
        except Exception as e:
            logger.exception("signed_url_failed_content: error=%s", e)
    uris["by_language"] = by_lang
    return {"type": "content", "poster_prompts": poster_prompts, "video_prompt": video_prompt, "video_shotlist": shotlist, **uris}
@app.post("/pubsub/push")
def pubsub_push(body: Dict[str, Any], authorization: Optional[str] = Header(default=None)) -> Dict[str, str]:
    try:
        if not _verify_push(authorization):
            return {"status": "ack_error", "detail": "unauthorized"}
        message = body.get("message") or {}
        data_b64 = message.get("data")
        attributes = message.get("attributes") or {}
        if not data_b64:
            raise ValueError("missing data")

        # Optional processing delay for retry backoff; capped to 30s to avoid long handler blocks
        try:
            delay_ms_raw = attributes.get("delay_ms")
            if delay_ms_raw is not None:
                d = int(str(delay_ms_raw))
                if d > 0:
                    time.sleep(min(d, 30000) / 1000.0)
        except Exception:
            pass

        raw = base64.b64decode(data_b64)
        payload = json.loads(raw.decode("utf-8"))
        job_id = payload.get("job_id")
        task = (payload.get("task") or attributes.get("type") or "unknown").lower()
        if not job_id:
            raise ValueError("missing job_id")

        jobs = JobsStore()

        # Idempotency per task: skip only if this task is already completed
        existing = jobs.get(job_id)
        if existing:
            completed_tasks = set(existing.get("completed_tasks") or [])
            if task in completed_tasks:
                return {"status": "ack", "note": "already_completed_task"}

        jobs.update_status(job_id, "processing", {"task": task})

        # Load job payload and optional storage
        job_doc = jobs.get(job_id) or {}
        job_payload: Dict[str, Any] = job_doc.get("payload") or {}
        try:
            storage = Storage()
        except Exception:
            storage = None
        # Load settings and attempt counters
        try:
            settings = Settings.load()
        except Exception:
            settings = None  # pragma: no cover
        attempts_map: Dict[str, int] = {}
        try:
            if isinstance(job_doc.get("attempts"), dict):
                attempts_map = dict(job_doc.get("attempts") or {})
        except Exception:
            attempts_map = {}
        cur_attempt = int(attempts_map.get(task, 0))

        region_ctx = _load_region_context(job_payload)
        context_summary = _plan_context_summary(region_ctx) if region_ctx else None

        # Route by task and build outputs
        if task == "plan":
            plan_payload = _build_plan(job_payload, context_summary)
            result = {"type": "plan", **plan_payload}
        elif task == "scenario":
            result = _build_scenario(job_id, job_payload, storage, context_summary)
        elif task == "safety":
            scenario_assets = (job_doc.get("assets") or {}) or ((job_doc.get("result") or {}).get("assets") or {})
            result = _build_safety(job_payload, scenario_assets)
        elif task == "content":
            scenario_assets = (job_doc.get("assets") or {}) or ((job_doc.get("result") or {}).get("assets") or {})
            result = _build_content(job_payload, scenario_assets, storage, job_id)
        else:
            result = {"type": task, "message": "Unknown task; acknowledged"}

        # Persist result; also persist per-task results history and top-level assets after 'scenario'
        # Merge into results map
        prev_results: Dict[str, Any] = {}
        try:
            if isinstance(job_doc.get("results"), dict):
                prev_results = dict(job_doc.get("results") or {})
        except Exception:
            prev_results = {}
        prev_results[task] = result
        extra_update: Dict[str, Any] = {"result": result, "results": prev_results}
        if task == "scenario" and isinstance(result, dict) and isinstance(result.get("assets"), dict):
            extra_update["assets"] = result["assets"]
        # Mark this task as completed (append to list)
        current_doc = jobs.get(job_id) or {}
        completed_tasks = set((current_doc.get("completed_tasks") or []))
        completed_tasks.add(task)
        completed_sorted = sorted(list(completed_tasks))
        extra_update["completed_tasks"] = completed_sorted
        # Maintain completed_order to preserve execution order
        completed_order = list(current_doc.get("completed_order") or [])
        if task not in completed_order:
            completed_order.append(task)
        extra_update["completed_order"] = completed_order
        # Reset attempts for this task after success
        if task in attempts_map:
            attempts_map.pop(task, None)
        extra_update["attempts"] = attempts_map
        jobs.update_status(job_id, "done", extra_update)

        # Chain next task automatically (best-effort)
        def _next_task(cur: str) -> Optional[str]:
            order = ["plan", "scenario", "safety", "content"]
            try:
                i = order.index(cur)
                return order[i + 1] if i + 1 < len(order) else None
            except ValueError:
                return None

        next_t = _next_task(task)
        if next_t:
            try:
                pub = Publisher()
                pub.publish_json({"job_id": job_id, "task": next_t}, attributes={"type": next_t})
            except Exception:
                pass
        return {"status": "ack"}
    except Exception as e:
        # Best effort: try to record error if we have job_id
        try:
            job_id = job_id if "job_id" in locals() else None
            if job_id:
                js = JobsStore()
                # Update attempts counter
                doc = js.get(job_id) or {}
                amap: Dict[str, int] = {}
                if isinstance(doc.get("attempts"), dict):
                    amap = dict(doc.get("attempts") or {})
                # task may be undefined if decoding failed
                tname = (task if "task" in locals() else "unknown")
                amap[tname] = int(amap.get(tname, 0)) + 1
                update = {"error": str(e), "attempts": amap}
        except Exception:
            pass
        # Basic retry with exponential backoff + jitter if attempts below threshold
        try:
            max_try = getattr(settings, "retry_max_attempts", 3) if settings else 3
            if tname not in {"", "unknown"} and amap[tname] < max_try:
                # backoff seconds: min(30, 2^attempt + jitter[0,1))
                base = 2 ** min(amap[tname], 5)
                delay_sec = min(30.0, float(base) + random.uniform(0.0, 1.0))
                delay_ms = int(delay_sec * 1000)
                pub = Publisher()
                pub.publish_json(
                    {"job_id": job_id, "task": tname},
                    attributes={"type": tname, "delay_ms": str(delay_ms)},
                )
                update["retry"] = {"task": tname, "attempt": amap[tname], "delay_ms": delay_ms}
        except Exception:
            pass
        js.update_status(job_id, "error", update)
        try:
            logger.error(
                "task_failed job_id=%s task=%s attempt=%s error=%s",
                job_id,
                tname,
                amap.get(tname),
                str(e),
            )
        except Exception:
            pass
        # Always return 200 to avoid redelivery storms
        return {"status": "ack_error", "detail": str(e)}
