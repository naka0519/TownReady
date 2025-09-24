from __future__ import annotations

import json
from typing import Any, Dict, Optional
import concurrent.futures
import time

from .config import Settings


class Gemini:
    """Thin wrapper for Vertex AI Gemini with graceful fallback.

    If the runtime lacks the Vertex AI SDK or permissions, callers should
    catch exceptions and fallback to deterministic builders.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings.load()
        # Lazy init vertexai on each call to avoid import errors at import-time

    def _get_model(self):  # type: ignore[no-any-unimported]
        try:
            import vertexai  # type: ignore
            from vertexai.generative_models import GenerativeModel  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(f"vertexai_import_failed: {e}")
        vertexai.init(project=self.settings.project, location=self.settings.vai_location)
        return GenerativeModel(self.settings.gemini_model)

    def _gen_json(self, prompt: str, schema_hint: Optional[str] = None) -> Dict[str, Any]:
        """Ask Gemini for strict JSON and parse it.

        Uses response_mime_type=application/json to coerce JSON-only output.
        Falls back to best-effort extraction if provider still returns wrappers.
        """
        model = self._get_model()
        try:
            from vertexai.generative_models import GenerationConfig  # type: ignore
        except Exception:  # pragma: no cover
            GenerationConfig = None  # type: ignore

        sys_inst = (
            "You are a helpful planning assistant. Output MUST be a single valid JSON object. "
            "Do not add any commentary, markdown fences, or extra keys. "
            "All string values MUST be valid JSON strings with escaped newlines (\\n)."
        )
        hint = f"Schema hint: {schema_hint}" if schema_hint else ""
        parts = [sys_inst, hint, prompt]
        gen_cfg = {"response_mime_type": "application/json", "temperature": 0.2}
        if GenerationConfig is not None:
            gen_cfg = GenerationConfig(response_mime_type="application/json", temperature=0.2)  # type: ignore
        # Run with timeout + retries
        timeout_s = max(5, int(getattr(self.settings, "gemini_timeout_sec", 25)))
        max_retries = max(0, int(getattr(self.settings, "gemini_max_retries", 2)))

        def _call():
            return model.generate_content(parts, generation_config=gen_cfg)  # type: ignore

        last_err: Optional[Exception] = None
        for attempt in range(0, max_retries + 1):
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(_call)
                    resp = fut.result(timeout=timeout_s)
                text = getattr(resp, "text", None) or getattr(resp.candidates[0].content.parts[0], "text", "")  # type: ignore
                break
            except Exception as e:  # pragma: no cover
                last_err = e
                # backoff: 0.5, 1.0 seconds
                time.sleep(0.5 * (attempt + 1))
        else:
            raise RuntimeError(f"gemini_call_failed: {last_err}")
        # Primary parse
        try:
            return json.loads(text)
        except Exception:
            # Best-effort: strip code fences or prefix/suffix noise, then parse
            cleaned = (text or "").strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`\n ")
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].lstrip()
            # Extract first {...} block
            try:
                start = cleaned.find("{")
                end = cleaned.rfind("}")
                if start != -1 and end != -1 and end > start:
                    block = cleaned[start : end + 1]
                    return json.loads(block)
            except Exception:
                pass
            raise RuntimeError(f"gemini_parse_failed: could not parse JSON; raw={cleaned[:400]}")

    def generate_plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        loc = payload.get("location", {})
        parts = payload.get("participants", {})
        hazard = payload.get("hazard", {})
        region_ctx = payload.get("region_context") or {}
        languages = parts.get("languages") or ["ja"]
        prompt = f"""
You are an incident drill planner. Create a JSON object describing a localized PlanSpec.
Always include these keys:
  scenarios: array of objects {{ id (string), title (string), languages (array of strings) }}. Provide at least one scenario.
  acceptance: object with keys:
    must_include: array of hazard-aware checklist items (include flood/landslide actions when applicable).
    kpi_plan: object with targets (attendance_rate, avg_evac_time_sec, quiz_score) and collection (array of measurement channels).
  handoff: object {{ to: "Scenario Agent", with: {{ scenario_id: "S1" }} }}
  highlights: array of strings summarizing local risks. Include the key even if the array is empty.

Inputs:
  Location: {json.dumps(loc, ensure_ascii=False)}
  Participants: {json.dumps(parts, ensure_ascii=False)}
  Hazards: {json.dumps(hazard, ensure_ascii=False)}
  RegionContext: {json.dumps(region_ctx, ensure_ascii=False)}

Output MUST be valid JSON matching the schema above. Do not include extra keys. Escape newlines as \\n.
"""
        raw = self._gen_json(prompt)
        # Minimal validation: require scenarios[] and acceptance/handoff keys
        if not isinstance(raw, dict):
            raise RuntimeError("gemini_invalid_plan: not an object")
        if not isinstance(raw.get("scenarios"), list) or len(raw.get("scenarios")) == 0:
            raise RuntimeError("gemini_invalid_plan: scenarios missing")
        if not isinstance(raw.get("acceptance"), dict):
            raise RuntimeError("gemini_invalid_plan: acceptance missing")
        if not isinstance(raw.get("handoff"), dict):
            raise RuntimeError("gemini_invalid_plan: handoff missing")
        return raw

    def generate_scenario(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        loc = payload.get("location", {})
        hazard = payload.get("hazard", {})
        parts = payload.get("participants", {})
        region_ctx = payload.get("region_context") or {}
        langs = parts.get("languages") or ["ja"]
        prompt = f"""
Generate scenario assets tailored to the inputs.
Inputs:
  Location: {json.dumps(loc, ensure_ascii=False)}
  Hazards: {json.dumps(hazard, ensure_ascii=False)}
  Participants: {json.dumps(parts, ensure_ascii=False)}
  RegionContext: {json.dumps(region_ctx, ensure_ascii=False)}
You MUST return JSON of the form {{ "assets": {{ ... }} }} including:
  script_md: markdown string with sections `## Steps` and `## Local Risk Highlights` (or Japanese equivalent) reflecting hazard details.
  roles_csv: CSV string with headers role,name,responsibility and entries for lead/marshal/assistants.
  routes: array of objects each with name, type (main|accessible|alternate), points (array of {{lat,lng,label}}), notes. Include an alternate high-ground route when flood risk exists.
  timeline: array of objects {{ step, timestamp_offset_sec, description }} with hazard-aware checkpoints.
  resource_checklist: array of strings listing equipment/tasks.
  languages: {langs}
  highlights: array of summary strings (include even if empty).
All strings must escape newlines as \\n. Do not add extra keys or markdown fences.
"""
        raw = self._gen_json(prompt)
        # Minimal validation: assets.script_md/roles_csv strings
        assets = raw.get("assets") if isinstance(raw, dict) else None
        if not isinstance(assets, dict):
            raise RuntimeError("gemini_invalid_scenario: assets missing")
        if not isinstance(assets.get("script_md"), str) or not isinstance(assets.get("roles_csv"), str):
            raise RuntimeError("gemini_invalid_scenario: script_md/roles_csv must be strings")
        routes = assets.get("routes")
        if routes is not None and not isinstance(routes, list):
            raise RuntimeError("gemini_invalid_scenario: routes must be a list")
        return raw
