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
    </style>
    </head><body>
    <h2>Job <code>{job_id}</code></h2>
    <div id=\"meta\"></div>
    <h3>Scenario assets</h3>
    <ul id=\"assets\"></ul>
    <h3>Content</h3>
    <ul id=\"content\"></ul>
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

        document.getElementById('raw').textContent = JSON.stringify(j, null, 2);
      }}
      fetchJob();
      setInterval(fetchJob, 2000);
    </script>
    </body></html>
    """
    from fastapi.responses import HTMLResponse
    # Remove any leading whitespace/newline so the first byte is '<'
    html = html.lstrip()
    return HTMLResponse(html)
