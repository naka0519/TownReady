from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class Location(BaseModel):
    """Physical location metadata for a drill site."""

    address: str = Field(..., description="Human-readable address")
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lng: float = Field(..., ge=-180, le=180, description="Longitude")
    site_map_url: Optional[HttpUrl] = Field(
        default=None, description="Optional URL to the site map"
    )
    geojson: Optional[dict] = Field(default=None, description="Optional GeoJSON object")


class Participants(BaseModel):
    """Participant composition and accessibility needs."""

    total: int = Field(..., ge=0)
    children: int = Field(0, ge=0)
    elderly: int = Field(0, ge=0)
    wheelchair: int = Field(0, ge=0)
    languages: List[str] = Field(default_factory=list, description="e.g., ['ja','en']")


class HazardType(str, Enum):
    earthquake = "earthquake"
    fire = "fire"
    flood = "flood"
    tsunami = "tsunami"
    landslide = "landslide"


class HazardSpec(BaseModel):
    """Target hazards and drill context."""

    types: List[HazardType]
    drill_date: date
    indoor: bool
    nighttime: bool


class Constraints(BaseModel):
    """Operational constraints for the drill."""

    max_duration_min: Optional[int] = Field(default=None, ge=1)
    limited_outdoor: Optional[bool] = None


class RoutePoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    label: Optional[str] = None


class Route(BaseModel):
    name: str
    points: List[RoutePoint]
    accessibility_notes: Optional[str] = None


class VideoShot(BaseModel):
    description: str = Field(..., description="Shot description or prompt")
    duration_sec: int = Field(..., ge=1, le=60)


class Assets(BaseModel):
    """Generated assets container (script/roles/routes/media prompts)."""

    script_md: Optional[str] = None
    roles_csv: Optional[str] = None
    routes: List[Route] = Field(default_factory=list)
    poster_prompts: List[str] = Field(default_factory=list)
    video_prompt: Optional[str] = None
    video_shotlist: List[VideoShot] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)


class KPIPlan(BaseModel):
    class Targets(BaseModel):
        attendance_rate: float = Field(..., ge=0, le=1)
        avg_evac_time_sec: int = Field(..., ge=0)
        quiz_score: float = Field(..., ge=0, le=1)

    targets: Targets
    collection: List[str] = Field(
        default_factory=list, description="e.g., ['checkin','route_time','post_quiz','issue_log']"
    )


class GenerateBaseRequest(BaseModel):
    """Common input payload used by generate/plan and generate/scenario."""

    location: Location
    participants: Participants
    hazard: HazardSpec
    constraints: Optional[Constraints] = None
    kb_refs: List[str] = Field(default_factory=list)

