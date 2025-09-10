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
        task = (payload.get("task") or attributes.get("type") or "unknown").lower()
        if not job_id:
            raise ValueError("missing job_id")

        jobs = JobsStore()

        # Idempotency: if already completed, just ack
        existing = jobs.get(job_id)
        if existing and existing.get("status") in {"done", "error"}:
            return {"status": "ack", "note": "already_completed"}

        jobs.update_status(job_id, "processing", {"task": task})

        # Route by task and produce minimal stub outputs
        if task == "plan":
            result = {"type": "plan", "message": "Plan generated (stub)", "scenarios": [
                {"id": "S1", "title": "地震→火災", "languages": ["ja", "en"]}
            ]}
        elif task == "scenario":
            result = {"type": "scenario", "assets": {
                "script_md": "# 訓練台本\n1. 点呼\n2. 避難\n",
                "roles_csv": "role,name\nLead,田中\nSafety,佐藤\n",
                "routes": [
                    {"name": "Main", "points": [{"lat": 35.0, "lng": 139.0, "label": "A"}]}
                ],
            }}
        elif task == "safety":
            result = {"type": "safety", "issues": [
                {"severity": "medium", "issue": "避難経路の自己交差", "fix": "ルートを分岐", "kb": "kb://example"}
            ], "patched": True}
        elif task == "content":
            result = {"type": "content", "poster_prompts": ["学校向け避難誘導ポスター 日本語/英語"], "video_prompt": "60秒VTR 台本に沿う"}
        else:
            result = {"type": task, "message": "Unknown task; acknowledged"}

        jobs.update_status(job_id, "done", {"result": result})
        return {"status": "ack"}
    except Exception as e:
        # Best effort: try to record error if we have job_id
        try:
            job_id = job_id if "job_id" in locals() else None
            if job_id:
                JobsStore().update_status(job_id, "error", {"error": str(e)})
        except Exception:
            pass
        # Always return 200 to avoid redelivery storms
        return {"status": "ack_error", "detail": str(e)}
