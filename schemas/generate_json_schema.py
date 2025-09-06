"""
Generate JSON Schemas for core Pydantic models.

Usage (optional):
  python -m schemas.generate_json_schema
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from .models import (
    Location,
    Participants,
    HazardSpec,
    Constraints,
    RoutePoint,
    Route,
    VideoShot,
    Assets,
    KPIPlan,
    GenerateBaseRequest,
)


def dump_schema(model: type[BaseModel], out_dir: Path) -> None:
    schema = model.model_json_schema()
    path = out_dir / f"{model.__name__}.schema.json"
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2))
    print(f"Wrote: {path}")


def main() -> None:
    out_dir = Path(__file__).resolve().parent / "json"
    out_dir.mkdir(parents=True, exist_ok=True)

    models: list[type[BaseModel]] = [
        Location,
        Participants,
        HazardSpec,
        Constraints,
        RoutePoint,
        Route,
        VideoShot,
        Assets,
        KPIPlan,
        GenerateBaseRequest,
    ]

    for m in models:
        dump_schema(m, out_dir)


if __name__ == "__main__":
    main()

