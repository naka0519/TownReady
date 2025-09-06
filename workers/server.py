from __future__ import annotations

import base64
import json
from typing import Any, Dict

from fastapi import FastAPI, HTTPException

try:
    from GCP_AI_Agent_hackathon.services import JobsStore
except Exception:
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from services import JobsStore  # type: ignore


app = FastAPI(title="TownReady Worker", version="0.1.0")


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/pubsub/push")
def pubsub_push(body: Dict[str, Any]) -> Dict[str, str]:
    try:
        message = body.get("message") or {}
        data_b64 = message.get("data")
        attributes = message.get("attributes") or {}
        if not data_b64:
            raise ValueError("missing data")

        raw = base64.b64decode(data_b64)
        payload = json.loads(raw.decode("utf-8"))
        job_id = payload.get("job_id")
        task = payload.get("task") or attributes.get("type")
        if not job_id:
            raise ValueError("missing job_id")

        jobs = JobsStore()
        jobs.update_status(job_id, "processing", {"task": task})

        # Simulate quick completion for MVP
        result = {"message": f"Processed task {task}", "stub": True}
        jobs.update_status(job_id, "done", {"result": result})

        return {"status": "ack"}
    except Exception as e:
        # Return 200 to avoid redelivery storms; log in real app
        raise HTTPException(status_code=200, detail=str(e))

