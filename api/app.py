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
