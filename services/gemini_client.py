from __future__ import annotations

import json
from typing import Any, Dict, Optional

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
        resp = model.generate_content(parts, generation_config=gen_cfg)  # type: ignore
        text = getattr(resp, "text", None) or getattr(resp.candidates[0].content.parts[0], "text", "")  # type: ignore
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
        languages = parts.get("languages") or ["ja"]
        prompt = f"""
Create a drill PlanSpec for the following.
Location: {json.dumps(loc, ensure_ascii=False)}
Participants: {json.dumps(parts, ensure_ascii=False)}
Hazard: {json.dumps(hazard, ensure_ascii=False)}
Return strictly a JSON object with keys:
  scenarios: [{{"id": "S1", "title": "...", "languages": {languages}}}],
  acceptance: {{"must_include": ["..."], "kpi_plan": {{"targets": {{"attendance_rate": 0.6, "avg_evac_time_sec": 300, "quiz_score": 0.7}}, "collection": ["checkin","route_time","post_quiz"]}}}},
  handoff: {{"to": "Scenario Agent", "with": {{"scenario_id": "S1"}}}}
No markdown fences. Ensure strings are valid JSON strings (escape newlines as \\n).
"""
        return self._gen_json(prompt)

    def generate_scenario(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        loc = payload.get("location", {})
        hazard = payload.get("hazard", {})
        parts = payload.get("participants", {})
        langs = parts.get("languages") or ["ja"]
        prompt = f"""
Create a scenario assets bundle.
Location: {json.dumps(loc, ensure_ascii=False)}
Hazard: {json.dumps(hazard, ensure_ascii=False)}
Participants: {json.dumps(parts, ensure_ascii=False)}
Return strictly a JSON object with key "assets": {{
  "script_md": "# Title\\n...",  // markdown as a single JSON string (newlines escaped)
  "roles_csv": "role,name\\nLead,Name...", // CSV as a single JSON string
  "routes": [{{"name": "Main", "points": [{{"lat": 0, "lng": 0, "label": "Start"}}], "accessibility_notes": "..."}}],
  "languages": {langs}
}}.
No markdown code fences. All strings must be valid JSON strings with escaped newlines (\\n).
"""
        return self._gen_json(prompt)
