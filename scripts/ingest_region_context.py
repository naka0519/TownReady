#!/usr/bin/env python3
"""RegionContext ingestion tool.

既存の戸塚区向けプロトタイプを一般化し、複数地域の RegionContext JSON と
カタログ index.json を生成するためのユーティリティ。CI から実行しても
差分が安定するよう、出力はソート済み/丸め済みのフィールドのみを含む。
"""
from __future__ import annotations

import argparse
import json
from math import cos, radians
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import unicodedata

TSUNAMI_GEOJSON = Path("kb/tunami.geojson")
SHELTER_GEOJSON = Path("kb/shelter.geojson")
ADMIN_GEOJSON = Path("kb/gyouseiku.geojson")
LANDSLIDE_GEOJSON = Path("kb/hazardarea.geojson")
FLOOD_GEOJSON = Path("kb/flood.geojson")

DEPTH_TOKENS = ["以上", "未満", "〜", "m"]
EARTH_RADIUS_M = 6378137.0

# Rank -> (min_depth_m, max_depth_m) for計画規模浸水深（A31b_101）
FLOOD_DEPTH_RANGES: Dict[int, Tuple[Optional[float], Optional[float]]] = {
    1: (0.0, 0.5),
    2: (0.5, 1.0),
    3: (1.0, 2.0),
    4: (2.0, 3.0),
    5: (3.0, 5.0),
    6: (5.0, None),
}


# --------------------------------------------------------------------------- utils


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RegionContext JSON and index entry.")
    parser.add_argument("--prefecture", default="神奈川県")
    parser.add_argument("--city", default="横浜市")
    parser.add_argument("--ward", default="戸塚区")
    parser.add_argument("--municipal-code", dest="municipal_code", default="14110")
    parser.add_argument("--slug", help="ASCII slug for output file (default: derived from municipal code)")
    parser.add_argument(
        "--output-dir",
        default="kb/region_context",
        help="Directory to store generated RegionContext files",
    )
    parser.add_argument(
        "--index",
        default=None,
        help="Path to catalog index.json (default: <output-dir>/index.json)",
    )
    parser.add_argument(
        "--no-index",
        action="store_true",
        help="Do not update the catalog index file",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Skip file writes and only report derived metadata",
    )
    return parser.parse_args()


def _ascii_token(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_token = "".join(
        ch for ch in normalized if ch.isalnum() and ord(ch) < 128
    ).lower()
    if ascii_token:
        return ascii_token
    return ""


def derive_slug(args: argparse.Namespace) -> str:
    candidates = [args.prefecture, args.city, getattr(args, "ward", None)]
    tokens = [
        _ascii_token(item)
        for item in candidates
        if isinstance(item, str) and item.strip()
    ]
    slug = "-".join(token for token in tokens if token)
    if not slug:
        code = getattr(args, "municipal_code", "")
        if code:
            slug = f"region-{code}"
    if not slug:
        slug = "region"
    return slug


def compute_bbox_and_centroid(context: Dict[str, Any]) -> Tuple[Optional[Tuple[float, float, float, float]], Optional[Tuple[float, float]]]:
    coords: List[Tuple[float, float]] = []

    def collect_geom(geom: Dict[str, Any]) -> None:
        gtype = geom.get("type")
        raw = geom.get("coordinates", [])
        if gtype == "Polygon":
            rings = raw
        elif gtype == "MultiPolygon":
            rings = [ring for poly in raw for ring in poly]
        else:
            return
        for ring in rings:
            for pt in ring:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    try:
                        lng = float(pt[0])
                        lat = float(pt[1])
                        coords.append((lng, lat))
                    except Exception:
                        continue

    for hazard in (context.get("hazards") or {}).values():
        for feat in hazard.get("features", []):
            geom = feat.get("geometry")
            if isinstance(geom, dict):
                collect_geom(geom)

    for shelter in context.get("shelters", []):
        loc = shelter.get("location") or {}
        try:
            coords.append((float(loc["lng"]), float(loc["lat"])))
        except Exception:
            continue

    if not coords:
        return None, None

    min_lng = min(pt[0] for pt in coords)
    min_lat = min(pt[1] for pt in coords)
    max_lng = max(pt[0] for pt in coords)
    max_lat = max(pt[1] for pt in coords)
    centroid = ((max_lng + min_lng) / 2.0, (max_lat + min_lat) / 2.0)
    return (min_lng, min_lat, max_lng, max_lat), centroid


def update_index(
    index_path: Path,
    *,
    entry: Dict[str, Any],
) -> None:
    if index_path.exists():
        try:
            content = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            content = {"regions": []}
    else:
        content = {"regions": []}

    regions = content.get("regions")
    if not isinstance(regions, list):
        regions = []
        content["regions"] = regions

    def _same(existing: Dict[str, Any]) -> bool:
        if entry.get("id") and existing.get("id") == entry.get("id"):
            return True
        if existing.get("path") == entry.get("path"):
            return True
        return False

    updated = False
    for idx, existing in enumerate(list(regions)):
        if isinstance(existing, dict) and _same(existing):
            regions[idx] = entry
            updated = True
            break

    if not updated:
        regions.append(entry)

    regions.sort(key=lambda item: (item.get("id") or item.get("path") or ""))
    index_path.write_text(json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def _bbox_of_coords(coords: Iterable[Iterable[Tuple[float, float]]]) -> Tuple[float, float, float, float]:
    minx = miny = float("inf")
    maxx = maxy = float("-inf")
    for ring in coords:
        for x, y in ring:
            minx = min(minx, x)
            miny = min(miny, y)
            maxx = max(maxx, x)
            maxy = max(maxy, y)
    return minx, miny, maxx, maxy


def _intersects(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return not (ax2 < bx1 or bx2 < ax1 or ay2 < by1 or by2 < ay1)


def _parse_depth_band(label: str) -> Dict[str, float | None | str]:
    clean = label.strip()
    for tok in DEPTH_TOKENS:
        clean = clean.replace(tok, "")
    parts = [p.strip() for p in clean.split("〜") if p.strip()]
    result: Dict[str, float | None | str] = {"label": label, "min": None, "max": None}
    if not parts:
        return result
    try:
        result["min"] = float(parts[0]) if parts[0] else None
    except ValueError:
        pass
    if len(parts) > 1:
        try:
            result["max"] = float(parts[1]) if parts[1] else None
        except ValueError:
            pass
    elif "未満" in label or "\u672a\u6e80" in label:
        try:
            result["max"] = float(parts[0])
            result["min"] = None
        except ValueError:
            pass
    return result


def _build_admin_polygons(
    prefecture: str,
    city: str,
    ward: Optional[str],
) -> Tuple[List[Dict[str, Sequence[Tuple[float, float]]]], Tuple[float, float, float, float]]:
    data = json.loads(ADMIN_GEOJSON.read_text(encoding="utf-8"))
    polys: List[Dict[str, Sequence[Tuple[float, float]]]] = []
    bbox = [float("inf"), float("inf"), float("-inf"), float("-inf")]
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        if props.get("N03_001") and prefecture and props.get("N03_001") != prefecture:
            continue
        if props.get("N03_003") and city and props.get("N03_003") != city:
            continue
        ward_prop = props.get("N03_004")
        if ward and ward_prop and ward_prop != ward:
            continue
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates", [])
        if gtype == "Polygon":
            polygons = [coords]
        elif gtype == "MultiPolygon":
            polygons = coords
        else:
            continue
        for poly in polygons:
            if not poly:
                continue
            outer = [tuple(pt) for pt in poly[0]]
            holes = [[tuple(pt) for pt in ring] for ring in poly[1:]]
            polys.append({"outer": outer, "holes": holes})
            minx, miny, maxx, maxy = _bbox_of_coords(poly)
            bbox[0] = min(bbox[0], minx)
            bbox[1] = min(bbox[1], miny)
            bbox[2] = max(bbox[2], maxx)
            bbox[3] = max(bbox[3], maxy)
    if not polys:
        raise RuntimeError("戸塚区の行政界が gyouseiku.geojson に見つかりません")
    return polys, tuple(bbox)  # type: ignore[return-value]


def _point_in_ring(point: Tuple[float, float], ring: Sequence[Tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        if ((y1 > y) != (y2 > y)):
            x_cross = (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1
            if x < x_cross:
                inside = not inside
    return inside


def _point_in_polygon(point: Tuple[float, float], polygon: Dict[str, Sequence[Tuple[float, float]]]) -> bool:
    if not _point_in_ring(point, polygon["outer"]):
        return False
    for hole in polygon.get("holes", []):
        if _point_in_ring(point, hole):
            return False
    return True


def _point_in_any_polygon(point: Tuple[float, float], polygons: List[Dict[str, Sequence[Tuple[float, float]]]]) -> bool:
    return any(_point_in_polygon(point, poly) for poly in polygons)


def _simplify_ring(ring: Sequence[Tuple[float, float]], tol: float = 1e-5) -> List[Tuple[float, float]]:
    simplified: List[Tuple[float, float]] = []
    for x, y in ring:
        rx, ry = round(x, 6), round(y, 6)
        if simplified:
            px, py = simplified[-1]
            if abs(rx - px) < tol and abs(ry - py) < tol:
                continue
        simplified.append((rx, ry))
    if simplified and simplified[0] != simplified[-1]:
        simplified.append(simplified[0])
    return simplified


def _simplify_geometry(geom: Dict[str, Any]) -> Dict[str, Any]:
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])
    if gtype == "Polygon":
        new_coords = [[list(pt) for pt in _simplify_ring(ring)] for ring in coords]
    elif gtype == "MultiPolygon":
        new_coords = []
        for poly in coords:
            new_coords.append([[list(pt) for pt in _simplify_ring(ring)] for ring in poly])
    else:
        return geom
    return {"type": gtype, "coordinates": new_coords}


def load_tsunami_features(polygons: List[Dict[str, Sequence[Tuple[float, float]]]], admin_bbox: Tuple[float, float, float, float]) -> List[Dict[str, Any]]:
    data = json.loads(TSUNAMI_GEOJSON.read_text(encoding="utf-8"))
    output: List[Dict[str, Any]] = []
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        if gtype == "Polygon":
            rings = geom.get("coordinates", [])
        elif gtype == "MultiPolygon":
            rings = [ring for poly in geom.get("coordinates", []) for ring in poly]
        else:
            continue
        feat_bbox = _bbox_of_coords(rings)
        if not _intersects(feat_bbox, admin_bbox):
            continue
        points = [pt for ring in rings for pt in ring]
        if not points:
            continue
        cx = sum(pt[0] for pt in points) / len(points)
        cy = sum(pt[1] for pt in points) / len(points)
        if not _point_in_any_polygon((cx, cy), polygons):
            continue
        depth_label = feat.get("properties", {}).get("A40_003", "")
        band = _parse_depth_band(depth_label)
        output.append(
            {
                "geometry": _simplify_geometry(geom),
                "depth_label": depth_label,
                "depth_min_m": band.get("min"),
                "depth_max_m": band.get("max"),
            }
        )
    return output


def load_shelter_points(polygons: List[Dict[str, Sequence[Tuple[float, float]]]], admin_bbox: Tuple[float, float, float, float]) -> List[Dict[str, Any]]:
    data = json.loads(SHELTER_GEOJSON.read_text(encoding="utf-8"))
    output: List[Dict[str, Any]] = []
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates")
        if not coords or len(coords) < 2:
            continue
        lon, lat = coords[:2]
        if not (admin_bbox[0] <= lon <= admin_bbox[2] and admin_bbox[1] <= lat <= admin_bbox[3]):
            continue
        if not _point_in_any_polygon((lon, lat), polygons):
            continue
        props = feat.get("properties", {})
        output.append(
            {
                "id": props.get("共通ID") or props.get("NO"),
                "name": props.get("施設・場所名"),
                "location": {"lat": lat, "lng": lon},
            }
        )
    return output


def load_landslide_features(polygons: List[Dict[str, Sequence[Tuple[float, float]]]], admin_bbox: Tuple[float, float, float, float]) -> List[Dict[str, Any]]:
    data = json.loads(LANDSLIDE_GEOJSON.read_text(encoding="utf-8"))
    output: List[Dict[str, Any]] = []
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        if gtype == "Polygon":
            rings = geom.get("coordinates", [])
        elif gtype == "MultiPolygon":
            rings = [ring for poly in geom.get("coordinates", []) for ring in poly]
        else:
            continue
        feat_bbox = _bbox_of_coords(rings)
        if not _intersects(feat_bbox, admin_bbox):
            continue
        points = [pt for ring in rings for pt in ring]
        if not points:
            continue
        cx = sum(pt[0] for pt in points) / len(points)
        cy = sum(pt[1] for pt in points) / len(points)
        if not _point_in_any_polygon((cx, cy), polygons):
            continue
        props = feat.get("properties", {})
        hazard_type = props.get("A48_008", "")
        ordinance = props.get("A48_010")
        output.append(
            {
                "geometry": _simplify_geometry(geom),
                "hazard_type": hazard_type,
                "ordinance": ordinance,
            }
        )
    return output


def load_flood_features(polygons: List[Dict[str, Sequence[Tuple[float, float]]]], admin_bbox: Tuple[float, float, float, float]) -> List[Dict[str, Any]]:
    data = json.loads(FLOOD_GEOJSON.read_text(encoding="utf-8"))
    output: List[Dict[str, Any]] = []
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        if gtype == "Polygon":
            rings = geom.get("coordinates", [])
        elif gtype == "MultiPolygon":
            rings = [ring for poly in geom.get("coordinates", []) for ring in poly]
        else:
            continue
        feat_bbox = _bbox_of_coords(rings)
        if not _intersects(feat_bbox, admin_bbox):
            continue
        points = [pt for ring in rings for pt in ring]
        if not points:
            continue
        cx = sum(pt[0] for pt in points) / len(points)
        cy = sum(pt[1] for pt in points) / len(points)
        if not _point_in_any_polygon((cx, cy), polygons):
            continue
        rank = feat.get("properties", {}).get("A31b_101")
        if isinstance(rank, bool):  # guard wrong types
            rank = int(rank)
        rank_int: Optional[int] = int(rank) if isinstance(rank, (int, float)) else None
        depth_range = FLOOD_DEPTH_RANGES.get(rank_int) if rank_int is not None else (None, None)
        output.append(
            {
                "geometry": _simplify_geometry(geom),
                "rank": rank_int,
                "depth_min_m": depth_range[0] if depth_range else None,
                "depth_max_m": depth_range[1] if depth_range else None,
            }
        )
    return output


def _to_xy(lon: float, lat: float, lat0_rad: float) -> Tuple[float, float]:
    lon_rad = radians(lon)
    lat_rad = radians(lat)
    x = EARTH_RADIUS_M * lon_rad * cos(lat0_rad)
    y = EARTH_RADIUS_M * lat_rad
    return x, y


def _ring_area_sqkm(ring: Sequence[Tuple[float, float]]) -> float:
    if len(ring) < 4:
        return 0.0
    lat0_rad = radians(sum(pt[1] for pt in ring) / len(ring))
    area = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = _to_xy(ring[i][0], ring[i][1], lat0_rad)
        x2, y2 = _to_xy(ring[i + 1][0], ring[i + 1][1], lat0_rad)
        area += x1 * y2 - x2 * y1
    return abs(area) / 2_000_000_000.0  # convert m^2 to km^2 (divide by 1e6)


def _geometry_area_sqkm(geom: Dict[str, Any]) -> float:
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])
    if gtype == "Polygon":
        outer = coords[0] if coords else []
        holes = coords[1:]
        area = _ring_area_sqkm(outer)
        for hole in holes:
            area -= _ring_area_sqkm(hole)
        return max(area, 0.0)
    if gtype == "MultiPolygon":
        total = 0.0
        for poly in coords:
            if not poly:
                continue
            outer = poly[0]
            holes = poly[1:]
            total += _ring_area_sqkm(outer)
            for hole in holes:
                total -= _ring_area_sqkm(hole)
        return max(total, 0.0)
    return 0.0


def compute_hazard_scores(tsunami: List[Dict[str, Any]], landslide: List[Dict[str, Any]], flood: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    scores: Dict[str, Dict[str, float]] = {}
    if tsunami:
        coverage = sum(_geometry_area_sqkm(feat["geometry"]) for feat in tsunami)
        max_depth_candidates = [
            val
            for feat in tsunami
            for val in [feat.get("depth_max_m"), feat.get("depth_min_m")]
            if isinstance(val, (int, float))
        ]
        max_depth = max(max_depth_candidates) if max_depth_candidates else None
        entry = {
            "feature_count": float(len(tsunami)),
            "coverage_km2": round(coverage, 4),
        }
        if max_depth is not None:
            entry["max_depth_m"] = float(max_depth)
        scores["tsunami"] = entry
    if landslide:
        coverage = sum(_geometry_area_sqkm(feat["geometry"]) for feat in landslide)
        entry = {
            "feature_count": float(len(landslide)),
            "coverage_km2": round(coverage, 4),
        }
        # Count hazard types
        counts: Dict[str, int] = {}
        for feat in landslide:
            htype = feat.get("hazard_type") or "unknown"
            counts[htype] = counts.get(htype, 0) + 1
        # keep top 3 hazard types for quick reference
        for idx, (htype, cnt) in enumerate(sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:3]):
            entry[f"top_type_{idx + 1}"] = float(cnt)
        scores["landslide"] = entry
    if flood:
        coverage = sum(_geometry_area_sqkm(feat["geometry"]) for feat in flood)
        entry = {
            "feature_count": float(len(flood)),
            "coverage_km2": round(coverage, 4),
        }
        max_depth_candidates = [
            val
            for feat in flood
            for val in [feat.get("depth_max_m"), feat.get("depth_min_m")]
            if isinstance(val, (int, float))
        ]
        if max_depth_candidates:
            entry["max_depth_m"] = float(max(max_depth_candidates))
        counts: Dict[str, int] = {}
        for feat in flood:
            rank = feat.get("rank")
            key = f"rank_{int(rank)}" if isinstance(rank, (int, float)) else "rank_unknown"
            counts[key] = counts.get(key, 0) + 1
        for key, cnt in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:3]:
            entry[f"top_{key}"] = float(cnt)
        scores["flood_plan"] = entry
    return scores


def main() -> None:
    args = parse_args()
    try:
        polygons, admin_bbox = _build_admin_polygons(args.prefecture, args.city, getattr(args, "ward", None))
    except RuntimeError as exc:  # pragma: no cover
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)

    tsunami = load_tsunami_features(polygons, admin_bbox)
    shelters = load_shelter_points(polygons, admin_bbox)
    landslide = load_landslide_features(polygons, admin_bbox)
    flood = load_flood_features(polygons, admin_bbox)
    hazard_scores = compute_hazard_scores(tsunami, landslide, flood)

    payload = {
        "region": {
            "prefecture": args.prefecture,
            "city": args.city,
            "ward": getattr(args, "ward", None),
        },
        "hazards": {
            "tsunami": {
                "crs": "EPSG:4326 (converted from EPSG:6668)",
                "features": tsunami,
            },
            "landslide": {
                "crs": "EPSG:4326 (converted from EPSG:6668)",
                "features": landslide,
            },
            "flood_plan": {
                "crs": "EPSG:4326 (converted from EPSG:6668)",
                "features": flood,
            },
        },
        "hazard_scores": hazard_scores,
        "shelters": shelters,
        "meta": {
            "source_files": [
                str(TSUNAMI_GEOJSON),
                str(LANDSLIDE_GEOJSON),
                str(FLOOD_GEOJSON),
                str(SHELTER_GEOJSON),
                str(ADMIN_GEOJSON),
            ],
            "admin_bbox": admin_bbox,
            "notes": "Centroid-based clip; consider polygon intersection for higher fidelity.",
        },
    }

    slug = args.slug or derive_slug(args)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = (out_dir / f"{slug}.json").resolve()

    if not args.check_only:
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            "Wrote {path} (tsunami={tsunami_count}, landslide={landslide_count}, flood={flood_count}, shelters={shelter_count})".format(
                path=output_path,
                tsunami_count=len(tsunami),
                landslide_count=len(landslide),
                flood_count=len(flood),
                shelter_count=len(shelters),
            )
        )

    bbox, centroid = compute_bbox_and_centroid(payload)
    if not args.no_index and not args.check_only:
        index_path = Path(args.index) if args.index else (out_dir / "index.json")
        try:
            rel_path = output_path.relative_to(out_dir)
            rel_str = str(rel_path)
        except ValueError:
            rel_str = output_path.name

        entry: Dict[str, Any] = {
            "id": f"region-{args.municipal_code}" if getattr(args, "municipal_code", None) else None,
            "slug": slug,
            "path": rel_str,
            "preferred_names": [
                item
                for item in [args.prefecture, args.city, getattr(args, "ward", None)]
                if item
            ],
            "keywords": [item for item in [args.city, getattr(args, "ward", None)] if item],
            "hazards": sorted(list(payload.get("hazards", {}).keys())),
            "municipal_code": getattr(args, "municipal_code", None) or None,
        }
        if bbox:
            entry["bbox"] = [round(val, 6) for val in bbox]
        if centroid:
            entry["centroid"] = [round(val, 6) for val in centroid]
        entry = {k: v for k, v in entry.items() if v not in (None, [], {})}
        update_index(index_path, entry=entry)
        print(f"Updated {index_path} with entry {entry.get('id') or entry.get('slug')}")

    if args.check_only:
        print(json.dumps({"slug": slug, "hazard_counts": {
            "tsunami": len(tsunami),
            "landslide": len(landslide),
            "flood": len(flood),
            "shelters": len(shelters),
        }}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
