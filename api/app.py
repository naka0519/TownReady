from __future__ import annotations

from typing import Any, Dict, List, Optional
import time

from fastapi import FastAPI, HTTPException
try:
    # Load .env located at project root for local development
    from dotenv import load_dotenv
    from pathlib import Path as _Path

    load_dotenv(_Path(__file__).resolve().parents[1] / ".env")
except Exception:
    # dotenv is optional at runtime; environment may already be set
    pass
from pydantic import BaseModel, Field

# Try importing shared schemas; add parent dir to path if needed for local runs.
try:  # run as package: `uvicorn GCP_AI_Agent_hackathon.api.app:app --reload`
    from GCP_AI_Agent_hackathon.schemas import (
        Assets,
        GenerateBaseRequest,
        HazardSpec,
    )
except Exception:  # pragma: no cover - local dev fallback from api/ directory
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from schemas import Assets, GenerateBaseRequest, HazardSpec  # type: ignore


app = FastAPI(title="TownReady API", version="0.1.0")


class SafetyReviewRequest(BaseModel):
    hazard: HazardSpec
    assets: Assets
    kb_refs: List[str] = Field(default_factory=list)


class ContentRequest(BaseModel):
    assets: Assets
    languages: Optional[List[str]] = None


# @app.get("/healthz")
# def healthz() -> Dict[str, str]:
#     return {"status": "ok"}


# Alias to avoid any potential frontend handling of "/healthz"
@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/health/firestore")
def health_firestore() -> Dict[str, str]:
    try:
        try:
            from GCP_AI_Agent_hackathon.services import JobsStore, Settings
        except Exception:
            import sys
            from pathlib import Path

            sys.path.append(str(Path(__file__).resolve().parents[1]))
            from services import JobsStore, Settings  # type: ignore

        settings = Settings.load()
        _ = JobsStore(settings)  # init client
        return {"status": "ok", "database": settings.firestore_db, "project": settings.project}
    except Exception as e:  # pragma: no cover
        return {"status": "error", "message": str(e)}


@app.post("/api/generate/plan")
def generate_plan(payload: GenerateBaseRequest) -> Dict[str, Any]:
    # Create a job entry for downstream workers to pick up (stub).
    try:
        from GCP_AI_Agent_hackathon.services import JobsStore
    except Exception:
        import sys
        from pathlib import Path

        sys.path.append(str(Path(__file__).resolve().parents[1]))
        from services import JobsStore  # type: ignore

    jobs = JobsStore()
    try:
        job_id = jobs.create(payload.model_dump(mode="json"), status="queued")
    except Exception as e:
        # Surface error to help diagnose Firestore write issues
        raise HTTPException(status_code=500, detail=f"firestore_create_failed: {e}")

    # Publish a message for workers
    try:
        try:
            from GCP_AI_Agent_hackathon.services import Publisher
        except Exception:
            import sys
            from pathlib import Path

            sys.path.append(str(Path(__file__).resolve().parents[1]))
            from services import Publisher  # type: ignore

        pub = Publisher()
        pub.publish_json({"job_id": job_id, "task": "plan"}, attributes={"type": "plan"})
    except Exception:
        # Publishing failure should not 500 the request in MVP
        pass

    return {"job_id": job_id, "status": "queued"}


@app.post("/api/generate/scenario")
def generate_scenario(payload: GenerateBaseRequest) -> Dict[str, Any]:
    # Create job and publish to workers
    try:
        from GCP_AI_Agent_hackathon.services import JobsStore
    except Exception:
        import sys
        from pathlib import Path

        sys.path.append(str(Path(__file__).resolve().parents[1]))
        from services import JobsStore  # type: ignore

    jobs = JobsStore()
    try:
        job_id = jobs.create({"endpoint": "generate/scenario", **payload.model_dump(mode="json")}, status="queued")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"firestore_create_failed: {e}")

    try:
        try:
            from GCP_AI_Agent_hackathon.services import Publisher
        except Exception:
            import sys
            from pathlib import Path

            sys.path.append(str(Path(__file__).resolve().parents[1]))
            from services import Publisher  # type: ignore

        pub = Publisher()
        pub.publish_json({"job_id": job_id, "task": "scenario"}, attributes={"type": "scenario"})
    except Exception:
        pass

    return {"job_id": job_id, "status": "queued"}


@app.post("/api/review/safety")
def review_safety(payload: SafetyReviewRequest) -> Dict[str, Any]:
    try:
        from GCP_AI_Agent_hackathon.services import JobsStore
    except Exception:
        import sys
        from pathlib import Path

        sys.path.append(str(Path(__file__).resolve().parents[1]))
        from services import JobsStore  # type: ignore

    jobs = JobsStore()
    try:
        job_id = jobs.create({"endpoint": "review/safety", **payload.model_dump(mode="json")}, status="queued")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"firestore_create_failed: {e}")

    try:
        try:
            from GCP_AI_Agent_hackathon.services import Publisher
        except Exception:
            import sys
            from pathlib import Path

            sys.path.append(str(Path(__file__).resolve().parents[1]))
            from services import Publisher  # type: ignore

        pub = Publisher()
        pub.publish_json({"job_id": job_id, "task": "safety"}, attributes={"type": "safety"})
    except Exception:
        pass

    return {"job_id": job_id, "status": "queued"}


@app.post("/api/generate/content")
def generate_content(payload: ContentRequest) -> Dict[str, Any]:
    try:
        from GCP_AI_Agent_hackathon.services import JobsStore
    except Exception:
        import sys
        from pathlib import Path

        sys.path.append(str(Path(__file__).resolve().parents[1]))
        from services import JobsStore  # type: ignore

    jobs = JobsStore()
    try:
        job_id = jobs.create({"endpoint": "generate/content", **payload.model_dump(mode="json")}, status="queued")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"firestore_create_failed: {e}")

    # Publish a message for workers
    try:
        try:
            from GCP_AI_Agent_hackathon.services import Publisher
        except Exception:
            import sys
            from pathlib import Path

            sys.path.append(str(Path(__file__).resolve().parents[1]))
            from services import Publisher  # type: ignore

        pub = Publisher()
        pub.publish_json({"job_id": job_id, "task": "content"}, attributes={"type": "content"})
    except Exception:
        # Publishing failure should not 500 the request in MVP
        pass

    return {"job_id": job_id, "status": "queued"}

@app.get("/health/firestore_write")
def health_firestore_write() -> Dict[str, Any]:
    """Attempt a minimal write to Firestore to verify permissions."""
    try:
        try:
            from GCP_AI_Agent_hackathon.services import JobsStore
        except Exception:
            import sys
            from pathlib import Path
            sys.path.append(str(Path(__file__).resolve().parents[1]))
            from services import JobsStore  # type: ignore

        jobs = JobsStore()
        # Write to a deterministic doc id to avoid clutter
        jobs.update_status("_health", "ok", {"ts": int(time.time())})
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

    


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, Any]:
    try:
        from GCP_AI_Agent_hackathon.services import JobsStore
    except Exception:
        import sys
        from pathlib import Path

        sys.path.append(str(Path(__file__).resolve().parents[1]))
        from services import JobsStore  # type: ignore

    jobs = JobsStore()
    doc = jobs.get(job_id)
    if not doc:
        raise HTTPException(status_code=404, detail="job not found")
    return doc


@app.post("/webhook/forms")
def webhook_forms(payload: Dict[str, Any]) -> Dict[str, str]:
    return {"status": "received"}


@app.post("/webhook/checkin")
def webhook_checkin(payload: Dict[str, Any]) -> Dict[str, str]:
    return {"status": "received"}
@app.get("/api/kb/search")
def kb_search(q: str, n: int = 3) -> Dict[str, Any]:
    try:
        try:
            from GCP_AI_Agent_hackathon.services.kb_search import KBSearch
        except Exception:
            import sys
            from pathlib import Path

            sys.path.append(str(Path(__file__).resolve().parents[1]))
            from services.kb_search import KBSearch  # type: ignore

        kb = KBSearch()
        hits = kb.search(q, page_size=n)
        return {"status": "ok", "hits": hits}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# --- Minimal job status view (HTML) ---
@app.get("/view/jobs/{job_id}", response_model=None)
def view_job(job_id: str) -> Any:  # returns HTML
    """Minimal job status/asset view for quick manual verification.

    This renders a simple HTML that polls GET /api/jobs/{job_id} and shows
    status, tasks, and download links (signed URLs if available).
    """
    try:
        from GCP_AI_Agent_hackathon.services import JobsStore
    except Exception:
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).resolve().parents[1]))
        from services import JobsStore  # type: ignore

    jobs = JobsStore()
    doc = jobs.get(job_id)
    if not doc:
        raise HTTPException(status_code=404, detail="job not found")

    html = f"""
    <!doctype html>
    <html lang=\"ja\"><head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>TownReady Job {job_id}</title>
    <style>
      body {{ font-family: system-ui, sans-serif; padding: 16px; line-height: 1.5; }}
      code, pre {{ background:#f5f5f7; padding:2px 4px; border-radius:4px; }}
      .ok {{ color: #0a7; }} .warn {{ color:#c80; }} .err {{ color:#c33; }}
      ul {{ padding-left: 20px; }} a {{ word-break: break-all; }}
      button {{ padding: 6px 10px; border: 1px solid #ccc; border-radius: 6px; background: #fff; cursor: pointer; }}
      button:hover {{ background: #f5f5f7; }}
      .row {{ display: flex; gap: 8px; align-items: center; margin: 8px 0; }}
    </style>
    </head><body>
    <div class=\"row\">
      <h2 style=\"margin:0\">Job <code>{job_id}</code></h2>
      <a href=\"/view/start\" style=\"margin-left:auto\">+ 新規ジョブ</a>
    </div>
    <div id=\"meta\"></div>
    <div class=\"row\">
      <h3 style=\"margin:0\">Scenario assets</h3>
      <button id=\"btnRefresh\">リンク再発行</button>
    </div>
    <ul id=\"assets\"></ul>
    <h3>Content</h3>
    <ul id=\"content\"></ul>
    <h3>Safety issues</h3>
    <ul id=\"safety\"></ul>
    <h3>Raw</h3>
    <pre id=\"raw\" style=\"white-space:pre-wrap\"></pre>
    <script>
      const jobId = {job_id!r};
      async function fetchJob() {{
        const res = await fetch(`/api/jobs/${{jobId}}`);
        if (!res.ok) return;
        const j = await res.json();
        document.getElementById('meta').innerHTML = `
          <div>Status: <b>${{j.status}}</b> / Task: <code>${{j.task || ''}}</code></div>
          <div>Completed: <code>${{(j.completed_order||j.completed_tasks||[]).join(', ')}}</code></div>
          <div>Updated: <code>${{j.updated_at}}</code></div>
        `;
        const A = [];
        const as = (j.assets||{{}});
        if (as.script_md_url) A.push(`<li><a href="${{as.script_md_url}}" target="_blank">script.md</a></li>`);
        if (as.roles_csv_url) A.push(`<li><a href="${{as.roles_csv_url}}" target="_blank">roles.csv</a></li>`);
        if (as.routes_json_url) A.push(`<li><a href="${{as.routes_json_url}}" target="_blank">routes.json</a></li>`);
        document.getElementById('assets').innerHTML = A.join('') || '<li>（なし）</li>';

        const C = [];
        const content = (j.results && j.results.content) || (j.result && j.result.type==='content' && j.result) || {{}};
        if (content.poster_prompts_url) C.push(`<li><a href="${{content.poster_prompts_url}}" target="_blank">poster_prompts.txt</a></li>`);
        if (content.video_prompt_url) C.push(`<li><a href="${{content.video_prompt_url}}" target="_blank">video_prompt.txt</a></li>`);
        if (content.video_shotlist_url) C.push(`<li><a href="${{content.video_shotlist_url}}" target="_blank">video_shotlist.json</a></li>`);
        document.getElementById('content').innerHTML = C.join('') || '<li>（なし）</li>';
        const S = [];
        const safety = (j.results && j.results.safety) || (j.result && j.result.type==='safety' && j.result) || {{}};
        (safety.issues||[]).forEach((it)=>{{
          const kb = (it.kb_hits||[]).map(h=>`<div style=\"margin-left:12px;\">- <a href=\"${{h.link||h.url||'#'}}\" target=\"_blank\">${{h.title||h.id||'ref'}}</a><br/><small>${{(h.snippet||'').replaceAll('<','&lt;')}}</small></div>`).join('');
          S.push(`<li><b>[${{it.severity||'n/a'}}]</b> ${{it.issue||''}}<br/><small>fix: ${{it.fix||''}}</small>${{kb}}</li>`);
        }});
        document.getElementById('safety').innerHTML = S.join('') || '<li>（なし）</li>';
        document.getElementById('raw').textContent = JSON.stringify(j, null, 2);
      }}
      fetchJob();
      setInterval(fetchJob, 2000);
      document.getElementById('btnRefresh').onclick = async () => {{
        try {{
          const res = await fetch(`/api/jobs/${{jobId}}/assets/refresh`, {{ method: 'POST' }});
          if (!res.ok) alert('再発行に失敗しました');
          await fetchJob();
        }} catch (e) {{
          alert('再発行エラー: '+ e);
        }}
      }};
    </script>
    </body></html>
    """
    from fastapi.responses import HTMLResponse
    # Remove any leading whitespace/newline so the first byte is '<'
    html = html.lstrip()
    return HTMLResponse(html)
@app.get("/view/start", response_model=None)
def view_start() -> Any:  # returns HTML
    html = """
    <!doctype html>
    <html lang=\"ja\"><head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>TownReady Start</title>
    <style>
      body { font-family: system-ui, sans-serif; padding: 16px; line-height: 1.5; }
      label { display:block; margin: 8px 0 4px; }
      input, select { padding:6px 8px; width: 320px; max-width: 100%; }
      button { padding: 8px 12px; border: 1px solid #ccc; border-radius: 6px; background: #fff; cursor: pointer; }
      button:hover { background: #f5f5f7; }
    </style>
    </head><body>
    <h2>新規ジョブの開始</h2>
    <p>住所や属性を入力して <code>/api/generate/plan</code> を起動します。</p>
    <div>
      <label>住所</label>
      <input id=\"address\" value=\"横浜市瀬谷区＊＊＊\" />
      <div style=\"display:flex; gap:8px;\">
        <div><label>lat</label><input id=\"lat\" value=\"35.47\"/></div>
        <div><label>lng</label><input id=\"lng\" value=\"139.49\"/></div>
      </div>
      <label>言語（カンマ区切り）</label>
      <input id=\"langs\" value=\"ja,en\" />
      <label>ハザード（カンマ区切り）</label>
      <input id=\"hazards\" value=\"earthquake,fire\" />
    </div>
    <div style=\"margin-top:12px;\"><button id=\"btn\">開始</button></div>
    <script>
      document.getElementById('btn').onclick = async () => {
        const address = document.getElementById('address').value;
        const lat = parseFloat(document.getElementById('lat').value);
        const lng = parseFloat(document.getElementById('lng').value);
        const langs = document.getElementById('langs').value.split(',').map(s=>s.trim()).filter(Boolean);
        const hazardTypes = document.getElementById('hazards').value.split(',').map(s=>s.trim()).filter(Boolean);
        const payload = {
          location: { address, lat, lng },
          participants: { total: 100, children: 10, elderly: 10, wheelchair: 2, languages: langs },
          hazard: { types: hazardTypes, drill_date: '2025-10-12', indoor: true, nighttime: false },
          constraints: { max_duration_min: 45, limited_outdoor: true },
          kb_refs: []
        };
        const res = await fetch('/api/generate/plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        if (!res.ok) { alert('起動に失敗しました'); return; }
        const j = await res.json();
        location.href = `/view/jobs/${j.job_id}`;
      };
    </script>
    </body></html>
    """
    from fastapi.responses import HTMLResponse
    return HTMLResponse(html.strip())


# --- Signed URL refresh endpoint ---
def _parse_gs_path(gs_uri: str) -> str:
    if not isinstance(gs_uri, str) or not gs_uri.startswith("gs://"):
        raise ValueError("not a gs:// uri")
    without = gs_uri[len("gs://"):]
    parts = without.split("/", 1)
    if len(parts) != 2:
        raise ValueError("invalid gs uri")
    return parts[1]


@app.post("/api/jobs/{job_id}/assets/refresh")
def refresh_signed_urls(job_id: str) -> Dict[str, Any]:
    """Re-issue signed URLs for known assets of a job (scenario/content)."""
    try:
        try:
            from GCP_AI_Agent_hackathon.services import JobsStore, Storage, Settings
        except Exception:
            import sys
            from pathlib import Path
            sys.path.append(str(Path(__file__).resolve().parents[1]))
            from services import JobsStore, Storage, Settings  # type: ignore

        jobs = JobsStore()
        doc = jobs.get(job_id)
        if not doc:
            raise HTTPException(status_code=404, detail="job not found")
        settings = Settings.load()
        store = Storage(settings)

        updated_assets: Dict[str, Any] = dict(doc.get("assets") or {})
        # Scenario assets under top-level assets
        for src_key in ["script_md_uri", "roles_csv_uri", "routes_json_uri"]:
            gs = updated_assets.get(src_key)
            if isinstance(gs, str) and gs.startswith("gs://"):
                try:
                    path = _parse_gs_path(gs)
                    download_name = path.split("/")[-1]
                    url_key = src_key.replace("_uri", "_url")
                    updated_assets[url_key] = store.signed_url(
                        path,
                        ttl_seconds=settings.signed_url_ttl,
                        download_name=download_name,
                    )
                except Exception:
                    pass

        # Content assets under results.content
        results = dict(doc.get("results") or {})
        content = dict((results.get("content") or {}))
        for src_key in ["poster_prompts_uri", "video_prompt_uri", "video_shotlist_uri"]:
            gs = content.get(src_key)
            if isinstance(gs, str) and gs.startswith("gs://"):
                try:
                    path = _parse_gs_path(gs)
                    download_name = path.split("/")[-1]
                    url_key = src_key.replace("_uri", "_url")
                    content[url_key] = store.signed_url(
                        path,
                        ttl_seconds=settings.signed_url_ttl,
                        download_name=download_name,
                    )
                except Exception:
                    pass

        import time as _t
        counters = {
            "assets_refreshed_at": int(_t.time()),
            "assets_refresh_count": int(doc.get("assets_refresh_count", 0)) + 1,
        }
        patch = {"assets": updated_assets, "results": {**results, "content": content}, **counters}
        jobs.update_status(job_id, doc.get("status", "done"), patch)

        return {"status": "ok", "assets": updated_assets, "content": content, **counters}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"refresh_failed: {e}")
