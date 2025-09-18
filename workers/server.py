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
    from GCP_AI_Agent_hackathon.services import JobsStore, Settings, Storage, Publisher
    from GCP_AI_Agent_hackathon.services.gemini_client import Gemini  # type: ignore
except Exception:
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from services import JobsStore, Settings, Storage, Publisher  # type: ignore
    try:
        from services.gemini_client import Gemini  # type: ignore
    except Exception:  # pragma: no cover
        Gemini = None  # type: ignore


app = FastAPI(title="TownReady Worker", version="0.2.0")
logger = logging.getLogger("townready.worker")


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


def _build_plan(job_payload: Dict[str, Any]) -> Dict[str, Any]:
    # Optional Gemini generation (staged via env)
    try:
        settings = Settings.load()
        if getattr(settings, "use_gemini", False) and Gemini is not None:
            g = Gemini(settings)
            raw = g.generate_plan(job_payload)
            # normalize minimal keys
            scenarios = raw.get("scenarios") or []
            acceptance = raw.get("acceptance") or {}
            handoff = raw.get("handoff") or {"to": "Scenario Agent", "with": {}}
            return {"scenarios": scenarios, "acceptance": acceptance, "handoff": handoff}
    except Exception as e:
        logger.exception("gemini_plan_failed: %s", e)
    loc = job_payload.get("location", {})
    parts = job_payload.get("participants", {})
    hazard = job_payload.get("hazard", {})
    langs: List[str] = parts.get("languages") or ["ja"]
    types: List[str] = hazard.get("types") or []

    titles: List[str] = []
    if "earthquake" in types and "fire" in types:
        titles.append("地震→火災")
    elif "earthquake" in types:
        titles.append("地震")
    elif "fire" in types:
        titles.append("火災")
    else:
        titles.append("避難誘導")

    scenarios = [
        {"id": f"S{i+1}", "title": t, "languages": langs} for i, t in enumerate(titles)
    ]
    kpi = {
        "targets": {"attendance_rate": 0.6, "avg_evac_time_sec": 300, "quiz_score": 0.7},
        "collection": ["checkin", "route_time", "post_quiz"],
    }
    acceptance = {"must_include": ["要配慮者ルート", "多言語掲示", "役割表CSV"], "kpi_plan": kpi}
    return {
        "scenarios": scenarios,
        "acceptance": acceptance,
        "handoff": {"to": "Scenario Agent", "with": {"scenario_id": scenarios[0]["id"]}},
        "location": {"address": loc.get("address"), "lat": loc.get("lat"), "lng": loc.get("lng")},
    }


def _build_scenario(job_id: str, job_payload: Dict[str, Any], storage: Optional[Storage]) -> Dict[str, Any]:
    # Optional Gemini generation (staged via env)
    try:
        settings = Settings.load()
        if getattr(settings, "use_gemini", False) and Gemini is not None:
            g = Gemini(settings)
            raw = g.generate_scenario(job_payload) or {}
            assets_in = raw.get("assets") or raw
            # Coerce to expected structure
            script_md = assets_in.get("script_md") or ""
            roles_csv = assets_in.get("roles_csv") or "role,name\nLead,田中\nSafety,佐藤\n"
            routes = assets_in.get("routes") or []
            langs = assets_in.get("languages") or (job_payload.get("participants", {}).get("languages") or ["ja"])
            assets: Dict[str, Any] = {"script_md": script_md, "roles_csv": roles_csv, "routes": routes, "languages": langs}
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
    langs: List[str] = parts.get("languages") or ["ja"]

    def _script_for(lang: str) -> str:
        if lang == "en":
            return (
                f"# Drill Script\n\n"
                f"- Location: {loc.get('address','')}\n"
                f"- Hazards: {', '.join(hazard.get('types', []))}\n\n"
                "## Steps\n"
                "1. Roll call\n"
                "2. Initial response (safety check / fire suppression)\n"
                "3. Evacuation guidance (assist persons with special needs)\n"
                "4. Safety check & debrief\n"
            )
        # default: ja
        return (
            f"# 訓練台本\n\n"
            f"- 場所: {loc.get('address','')}\n"
            f"- 想定: {', '.join(hazard.get('types', []))}\n\n"
            "## 手順\n"
            "1. 集合・点呼\n"
            "2. 初期対応（安全確認/初期消火）\n"
            "3. 避難誘導（要配慮者を先導）\n"
            "4. 安全確認・振り返り\n"
        )

    def _roles_for(lang: str) -> str:
        if lang == "en":
            return "role,name\nLead,Tanaka\nSafety,Sato\nFirstAid,Suzuki\n"
        return "role,name\nLead,田中\nSafety,佐藤\nFirstAid,鈴木\n"

    routes = [
        {
            "name": "Main",
            "points": [
                {"lat": loc.get("lat"), "lng": loc.get("lng"), "label": "Start"},
            ],
            "accessibility_notes": "段差回避、車椅子優先ルート",
        }
    ]
    # Base assets and per-language containers
    assets: Dict[str, Any] = {"routes": routes, "languages": langs}
    by_lang: Dict[str, Any] = {}
    primary = (langs[0] if len(langs) else "ja")
    if storage:
        routes_path = f"jobs/{job_id}/routes.json"
        assets["routes_json_uri"] = storage.upload_text(
            routes_path, json.dumps(routes, ensure_ascii=False, indent=2), "application/json"
        )
    # Generate per-language script/roles
    for lang in langs:
        script = _script_for(lang)
        roles = _roles_for(lang)
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

        # Route by task and build outputs
        if task == "plan":
            result = {"type": "plan", **_build_plan(job_payload)}
        elif task == "scenario":
            result = _build_scenario(job_id, job_payload, storage)
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
