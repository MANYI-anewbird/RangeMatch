"""Phase 3 minimal livestock movement derivation.

Labels only. Reuses F06 compactness / part count. Does not invent
livestock-to-water distance, terrain zones, gates, or paddocks.
"""

from __future__ import annotations

from typing import Any, Mapping

from shapely.geometry import Point, box, shape

from rangematch.advisor_visit import field_drawable_objects

COMPACTNESS_COMPACT_MIN = 0.60
BOUNDARY_BAND_FRACTION = 0.15
CONCENTRATED_SPAN_FRACTION = 0.25

COMPACT = "COMPACT"
ELONGATED = "ELONGATED"
FRAGMENTED_MULTIPART = "FRAGMENTED_MULTIPART"
SINGLE_PART = "SINGLE_PART"
MULTIPART = "MULTIPART"
DISTRIBUTED = "DISTRIBUTED"
CONCENTRATED = "CONCENTRATED"
BOUNDARY_ADJACENT = "BOUNDARY_ADJACENT"


def _f06_extras(unified_output: Mapping[str, Any]) -> dict[str, Any]:
    factor = (unified_output.get("factors") or {}).get("F06_PARCEL_CONFIGURATION") or {}
    extras = dict(factor.get("evaluation_extras") or {})
    if not extras:
        extras = {
            "compactness": factor.get("compactness"),
            "polygon_part_count": factor.get("polygon_part_count"),
        }
    provenance = factor.get("provenance") or {}
    extras.setdefault("geometry_hash", provenance.get("geometry_hash"))
    return extras


def classify_compactness(compactness: float | None, part_count: int | None) -> str | None:
    if part_count is not None and part_count > 1:
        return FRAGMENTED_MULTIPART
    if compactness is None:
        return None
    if compactness >= COMPACTNESS_COMPACT_MIN:
        return COMPACT
    return ELONGATED


def classify_fragmentation(part_count: int | None) -> str | None:
    if part_count is None:
        return None
    return MULTIPART if part_count > 1 else SINGLE_PART


def _object_point(obj: Mapping[str, Any]) -> tuple[float, float] | None:
    geometry = obj.get("geometry") or {}
    centroid = geometry.get("centroid")
    if isinstance(centroid, list) and len(centroid) >= 2:
        return float(centroid[0]), float(centroid[1])
    bbox = geometry.get("bbox")
    if isinstance(bbox, list) and len(bbox) >= 4:
        return (float(bbox[0]) + float(bbox[2])) / 2.0, (float(bbox[1]) + float(bbox[3])) / 2.0
    return None


def _parcel_shape(unified_output: Mapping[str, Any]):
    for candidate in (
        unified_output.get("geometry"),
        (unified_output.get("parcel") or {}).get("geometry"),
        (unified_output.get("parcel") or {}).get("parcel_geometry"),
    ):
        if isinstance(candidate, Mapping) and candidate.get("type"):
            try:
                return shape(dict(candidate))
            except (TypeError, ValueError):
                return None
    return None


def classify_drawable_water_distribution(
    unified_output: Mapping[str, Any],
    packet: Mapping[str, Any],
) -> tuple[str | None, list[str]]:
    drawable = field_drawable_objects(list(packet.get("candidate_objects") or []))
    points: list[tuple[float, float]] = []
    refs: list[str] = []
    for obj in drawable:
        point = _object_point(obj)
        cid = str(obj.get("candidate_id") or "")
        if point is None or not cid:
            continue
        points.append(point)
        refs.append(cid)
    if not points:
        return None, []
    parcel = _parcel_shape(unified_output)
    if parcel is None or parcel.is_empty:
        return None, refs
    minx, miny, maxx, maxy = parcel.bounds
    width = max(maxx - minx, 0.0)
    height = max(maxy - miny, 0.0)
    characteristic = max(width, height)
    if characteristic <= 0:
        return CONCENTRATED, refs
    band = characteristic * BOUNDARY_BAND_FRACTION
    envelope = box(minx, miny, maxx, maxy)
    def near_edge(x: float, y: float) -> bool:
        return envelope.exterior.distance(Point(x, y)) <= band

    if all(near_edge(x, y) for x, y in points):
        return BOUNDARY_ADJACENT, refs
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    if span <= characteristic * CONCENTRATED_SPAN_FRACTION:
        return CONCENTRATED, refs
    return DISTRIBUTED, refs


def derive_movement_labels(
    packet: Mapping[str, Any],
    unified_output: Mapping[str, Any],
    *,
    geometry_hash: str,
) -> dict[str, Any]:
    """Return label records bound to the current geometry_hash. No numeric copies."""
    extras = _f06_extras(unified_output)
    extras_hash = str(extras.get("geometry_hash") or "")
    compactness_value = extras.get("compactness")
    part_count = extras.get("polygon_part_count")
    try:
        compactness_value = float(compactness_value) if compactness_value is not None else None
    except (TypeError, ValueError):
        compactness_value = None
    try:
        part_count = int(part_count) if part_count is not None else None
    except (TypeError, ValueError):
        part_count = None
    f06_fresh = (not extras_hash) or extras_hash == geometry_hash
    compactness = classify_compactness(compactness_value, part_count) if f06_fresh else None
    fragmentation = classify_fragmentation(part_count) if f06_fresh else None
    distribution, object_refs = classify_drawable_water_distribution(unified_output, packet)
    return {
        "geometry_hash": geometry_hash,
        "compactness": compactness,
        "fragmentation": fragmentation,
        "drawable_water_distribution": distribution,
        "drawable_object_refs": object_refs,
    }
