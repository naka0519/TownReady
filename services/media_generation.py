from __future__ import annotations

import base64
import os
import time
from typing import Any, Dict, Optional

try:
    from vertexai.preview.vision_models import ImageGenerationModel  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    ImageGenerationModel = None  # type: ignore

try:
    import vertexai  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    vertexai = None  # type: ignore

from .config import Settings
from .storage_client import Storage


_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAEElEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
)


class MediaGenerator:
    """Wrapper for Imagen/Veo generation with graceful fallbacks and cost control."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings.load()
        self.use_imagen = getattr(self.settings, "use_imagen", False)
        self.use_veo = getattr(self.settings, "use_veo", False)
        self.cost_image = float(getattr(self.settings, "media_cost_image", 0.02))
        self.cost_video = float(getattr(self.settings, "media_cost_video", 0.2))
        self.media_budget = float(getattr(self.settings, "media_budget_usd", 1.0))
        self._initialized = False

    def _init_vertex(self) -> None:
        if self._initialized:
            return
        if vertexai is None:  # pragma: no cover - optional dependency
            raise RuntimeError("vertexai_sdk_unavailable")
        vertexai.init(project=self.settings.project, location=self.settings.vai_location)  # type: ignore[attr-defined]
        self._initialized = True

    def _remaining_budget(self, costs: Dict[str, float]) -> float:
        spent = sum(costs.values())
        return max(0.0, self.media_budget - spent)

    def generate_poster(
        self,
        job_id: str,
        prompt: str,
        storage: Optional[Storage],
        costs: Dict[str, float],
    ) -> Dict[str, Any]:
        """Attempt to generate a poster via Imagen. Fallbacks when unavailable."""
        result: Dict[str, Any] = {"status": "disabled"}
        if not self.use_imagen:
            return result
        result["status"] = "skipped_budget"
        if self._remaining_budget(costs) < self.cost_image:
            return result
        if storage is None:
            return {"status": "storage_unavailable"}
        try:
            self._init_vertex()
            if ImageGenerationModel is None:
                raise RuntimeError("imagen_model_unavailable")
            model_name = os.getenv("IMAGEN_MODEL", "imagegeneration@006")
            try:
                model = ImageGenerationModel.from_pretrained(model_name)  # type: ignore[arg-type]
            except Exception:
                if "publishers/" not in model_name:
                    alt_name = f"publishers/google/models/{model_name}"
                    model = ImageGenerationModel.from_pretrained(alt_name)  # type: ignore[arg-type]
                else:
                    raise
            response = model.generate_images(  # type: ignore[attr-defined]
                prompt=prompt,
                number_of_images=1,
            )
            image_bytes: Optional[bytes] = None
            image_uri: Optional[str] = None
            try:
                if response and getattr(response, "images", None):
                    image_bytes = response.images[0]._image_bytes  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - SDK differences
                image_bytes = None
            if image_bytes:
                path = f"jobs/{job_id}/poster.png"
                image_uri = storage.upload_bytes(path, image_bytes, content_type="image/png")
            else:
                path = f"jobs/{job_id}/poster_placeholder.png"
                image_uri = storage.upload_bytes(path, _PLACEHOLDER_PNG, content_type="image/png")
                result["status"] = "fallback"
            costs["image"] = costs.get("image", 0.0) + self.cost_image
            result.update({"status": result.get("status", "generated"), "uri": image_uri, "cost": self.cost_image})
            return result
        except Exception as exc:
            path = f"jobs/{job_id}/poster_placeholder.png"
            placeholder_uri = storage.upload_bytes(path, _PLACEHOLDER_PNG, content_type="image/png") if storage else None
            return {
                "status": "fallback",
                "reason": str(exc),
                "uri": placeholder_uri,
                "cost": 0.0,
            }

    def generate_video(
        self,
        job_id: str,
        prompt: str,
        storage: Optional[Storage],
        costs: Dict[str, float],
    ) -> Dict[str, Any]:
        """Return a stub response because video generation is not implemented."""
        return {
            "status": "not_implemented",
            "reason": "Video generation is currently disabled in this release.",
            "uri": None,
            "cost": 0.0,
        }

    def generate_media_bundle(
        self,
        job_id: str,
        poster_prompt: str,
        video_prompt: str,
        storage: Optional[Storage],
    ) -> Dict[str, Any]:
        costs: Dict[str, float] = {}
        poster = self.generate_poster(job_id, poster_prompt, storage, costs)
        video = self.generate_video(job_id, video_prompt, storage, costs)
        total_cost = sum(costs.values())
        return {
            "poster": poster,
            "video": video,
            "total_cost": total_cost,
        }
