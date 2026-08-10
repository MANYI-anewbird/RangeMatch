"""Deterministic F04 soil/wetness/ecological-site derivation from SDA fixtures."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


DERIVATION_SPEC_VERSION = "F04_SOIL_SITE_DERIVATION_SPEC.yaml@0.1.0"
GEOMETRY_HASH_CPER = "932edc9b3cb36b49b5a8fdd5ffa52cba17874720947865e0916ba069fad5f309"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _is_metadata_row(row: Sequence[Any]) -> bool:
    return bool(row) and isinstance(row[0], str) and row[0].startswith("ColumnOrdinal=")


def parse_sda_table(table_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Parse an SDA JSON Table payload, skipping the schema metadata row."""
    table = table_payload.get("Table") or []
    if not table:
        return []
    header = table[0]
    rows: list[dict[str, Any]] = []
    for row in table[1:]:
        if _is_metadata_row(row):
            continue
        rows.append(dict(zip(header, row)))
    return rows


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _clamp_unit_fraction(value: float) -> float:
    if value > 1.0 and value <= 1.0 + 1e-9:
        return 1.0
    if value < 0.0 and value >= -1e-9:
        return 0.0
    return value


def _category_key(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    return str(value)


def horizon_overlap_cm(
    hzdept_r: float | None,
    hzdepb_r: float | None,
    interval_top: float,
    interval_bottom: float,
) -> float:
    if hzdept_r is None or hzdepb_r is None:
        return 0.0
    return max(0.0, min(hzdepb_r, interval_bottom) - max(hzdept_r, interval_top))


def ecological_site_access_status(access: Mapping[str, Any] | None) -> str:
    """Classify public ecological-site description access without overclaiming.

    Timeout and other unresolved fetch failures remain UNKNOWN. NOT_ACCESSIBLE is
    reserved for an explicit, confirmed negative access result.
    """
    if not access:
        return "UNKNOWN"
    if access.get("public_description_accessible") is True:
        return "ACCESSIBLE"

    error_type = str(access.get("error_type") or "").lower()
    unresolved_tokens = (
        "timeout",
        "timedout",
        "timed_out",
        "connection",
        "temporary",
        "unavailable",
    )
    if any(token in error_type for token in unresolved_tokens):
        return "UNKNOWN"

    http_status = access.get("http_status")
    if access.get("public_description_accessible") is False:
        if http_status in {401, 403, 404, 410}:
            return "NOT_ACCESSIBLE"
        if http_status is None and not error_type:
            return "NOT_ACCESSIBLE"
        return "UNKNOWN"

    return "UNKNOWN"


def derive_available_water_storage(
    horizons: Sequence[Mapping[str, Any]],
    *,
    declared_depth_interval_cm: tuple[float, float] | None,
    component_support_weights: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Derive AWC-based storage for an explicitly declared depth interval.

    No default depth interval is applied. Missing AWC reduces depth coverage and
    is never imputed. Component-support coverage counts only components that
    contribute at least one AWC-represented overlap within the interval.
    """
    if declared_depth_interval_cm is None:
        return {
            "status": "METHOD_INPUT_REQUIRED",
            "derived_storage_mm": None,
            "target_depth_cm": None,
            "represented_depth_cm": None,
            "depth_coverage_fraction": None,
            "component_support_coverage_fraction": None,
            "component_results": [],
            "limitations": [
                "Available-water storage requires an explicitly declared depth interval.",
                "AWC is not forage production or operation suitability.",
            ],
        }

    interval_top, interval_bottom = declared_depth_interval_cm
    if interval_bottom <= interval_top:
        raise ValueError("declared_depth_interval_cm bottom must exceed top")

    target_depth = float(interval_bottom - interval_top)
    by_component: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for horizon in horizons:
        cokey = str(horizon["cokey"])
        by_component[cokey].append(horizon)

    if component_support_weights is not None:
        cokeys = set(str(key) for key in component_support_weights) | set(by_component)
        total_weight = sum(float(weight) for weight in component_support_weights.values())
    else:
        cokeys = set(by_component)
        total_weight = float(len(cokeys))

    component_results = []
    weighted_storage = 0.0
    weighted_represented = 0.0
    weight_with_awc = 0.0

    for cokey in sorted(cokeys):
        if component_support_weights is not None:
            weight = float(component_support_weights.get(cokey, 0.0))
        else:
            weight = 1.0

        storage_mm = 0.0
        represented_depth = 0.0
        for horizon in by_component.get(cokey, []):
            overlap = horizon_overlap_cm(
                _as_float(horizon.get("hzdept_r")),
                _as_float(horizon.get("hzdepb_r")),
                interval_top,
                interval_bottom,
            )
            awc = _as_float(horizon.get("awc_r"))
            if awc is None:
                continue
            represented_depth += overlap
            storage_mm += awc * overlap * 10.0

        depth_coverage = (
            represented_depth / target_depth if target_depth > 0 else None
        )
        component_results.append(
            {
                "cokey": cokey,
                "component_support_weight": weight,
                "storage_mm": storage_mm,
                "represented_depth_cm": represented_depth,
                "depth_coverage_fraction": depth_coverage,
                "contributes_awc": represented_depth > 0,
            }
        )
        weighted_storage += storage_mm * weight
        weighted_represented += represented_depth * weight
        if represented_depth > 0:
            weight_with_awc += weight

    support_coverage = (
        weight_with_awc / total_weight if total_weight > 0 else None
    )
    if total_weight > 0:
        parcel_storage = weighted_storage
        parcel_represented = weighted_represented
    else:
        parcel_storage = None
        parcel_represented = None
    parcel_depth_coverage = (
        parcel_represented / target_depth
        if parcel_represented is not None and target_depth > 0
        else None
    )

    return {
        "status": "DERIVED",
        "derived_storage_mm": parcel_storage,
        "target_depth_cm": target_depth,
        "interval_top_cm": interval_top,
        "interval_bottom_cm": interval_bottom,
        "represented_depth_cm": parcel_represented,
        "depth_coverage_fraction": parcel_depth_coverage,
        "component_support_coverage_fraction": support_coverage,
        "component_results": component_results,
        "limitations": [
            "Missing AWC horizons are excluded from storage and reduce depth coverage.",
            "Component-support coverage counts only components with AWC-represented overlap.",
            "AWC is not forage production or operation suitability.",
        ],
    }


def _weighted_category_distribution(
    items: Iterable[tuple[Any, float]],
) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for value, weight in items:
        totals[_category_key(value)] += float(weight)
    return {key: totals[key] for key in sorted(totals)}


def derive_f04_parcel_facts(
    *,
    spatial_coverage: Mapping[str, Any],
    components_table: Mapping[str, Any],
    horizons_table: Mapping[str, Any],
    restrictions_table: Mapping[str, Any],
    monthly_wetness_table: Mapping[str, Any],
    ecological_site_access: Sequence[Mapping[str, Any]],
    mireye_point: Mapping[str, Any] | None = None,
    geometry_hash: str = GEOMETRY_HASH_CPER,
    fetched_at: str = "2026-08-07T22:30:00Z",
    source_fixture_references: Sequence[str] | None = None,
    declared_awc_depth_interval_cm: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Derive parcel-level F04 facts from saved USDA SDA fixtures."""
    components = parse_sda_table(components_table)
    horizons = parse_sda_table(horizons_table)
    restrictions = parse_sda_table(restrictions_table)
    monthly = parse_sda_table(monthly_wetness_table)

    requested_area = float(spatial_coverage["requested_area_m2"])
    covered_area = float(spatial_coverage["covered_area_m2"])
    coverage_fraction = _clamp_unit_fraction(
        float(spatial_coverage["coverage_fraction"])
    )
    uncovered_area = max(0.0, requested_area - covered_area)

    mu_areas = {
        str(item["mukey"]): float(item["intersection_area_m2"])
        for item in spatial_coverage["mapunit_intersection_areas"]
    }
    raw_mapunit_area_sum = sum(mu_areas.values())
    spatial_overlap_normalization_factor = 1.0
    if covered_area > 0 and raw_mapunit_area_sum > covered_area * (1.0 + 1e-9):
        # Overlapping WFS survey polygons can otherwise allocate more than the
        # parcel's covered area. Preserve the raw diagnostic and proportionally
        # reconcile only the spatial support weights to the union-covered area.
        spatial_overlap_normalization_factor = covered_area / raw_mapunit_area_sum
        mu_areas = {
            mukey: area * spatial_overlap_normalization_factor
            for mukey, area in mu_areas.items()
        }
    mapunit_area_distribution = {
        mukey: (area / requested_area if requested_area else 0.0)
        for mukey, area in sorted(mu_areas.items())
    }

    # SDA's LEFT JOIN to ecological-class records may return more than one row
    # for the same soil component. Component percentage is a property of the
    # component, not of each joined ecological record, so count each cokey once.
    components_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_component_rows = 0
    for component in components:
        key = (str(component["mukey"]), str(component["cokey"]))
        if key in components_by_key:
            duplicate_component_rows += 1
            existing = components_by_key[key]
            for field in ("ecoclassid", "ecoclassname", "ecoclasstypename"):
                if not existing.get(field) and component.get(field):
                    existing[field] = component[field]
            continue
        components_by_key[key] = dict(component)
    components_by_mu: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for component in components_by_key.values():
        components_by_mu[str(component["mukey"])].append(component)

    component_support_weights: list[dict[str, Any]] = []
    support_by_cokey: dict[str, float] = {}
    known_component_share = 0.0
    unaccounted_component_share = 0.0

    for mukey, mu_fraction in mapunit_area_distribution.items():
        mu_components = components_by_mu.get(mukey, [])
        pct_sum = 0.0
        for component in mu_components:
            pct = _as_float(component.get("comppct_r")) or 0.0
            pct_sum += pct
            weight = mu_fraction * (pct / 100.0)
            cokey = str(component["cokey"])
            support_by_cokey[cokey] = weight
            known_component_share += weight
            component_support_weights.append(
                {
                    "mukey": mukey,
                    "cokey": cokey,
                    "compname": component.get("compname"),
                    "comppct_r": pct,
                    "majcompflag": (component.get("majcompflag") or "").strip() or None,
                    "mapunit_parcel_area_fraction": mu_fraction,
                    "component_support_weight": weight,
                    "drainagecl": component.get("drainagecl"),
                    "hydgrp": component.get("hydgrp"),
                    "ecoclassid": component.get("ecoclassid"),
                    "ecoclassname": component.get("ecoclassname"),
                    "ecoclasstypename": component.get("ecoclasstypename"),
                }
            )
        unaccounted_component_share += mu_fraction * max(0.0, 1.0 - (pct_sum / 100.0))

    component_support_weights.sort(key=lambda item: (-item["component_support_weight"], item["cokey"]))
    known_component_share_before_guard = known_component_share
    known_component_share = min(1.0, max(0.0, known_component_share))
    unaccounted_component_share = _clamp_unit_fraction(unaccounted_component_share)

    drainage_class_distribution = _weighted_category_distribution(
        (item["drainagecl"], item["component_support_weight"])
        for item in component_support_weights
    )
    hydrologic_soil_group_distribution = _weighted_category_distribution(
        (item["hydgrp"], item["component_support_weight"])
        for item in component_support_weights
    )

    months_by_cokey: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in monthly:
        months_by_cokey[str(row["cokey"])].append(row)

    ponding_items: list[tuple[Any, float]] = []
    flooding_items: list[tuple[Any, float]] = []
    monthly_records: list[dict[str, Any]] = []
    for cokey, rows in sorted(months_by_cokey.items()):
        weight = support_by_cokey.get(cokey, 0.0)
        month_count = len(rows) or 1
        month_weight = weight / month_count
        for row in sorted(rows, key=lambda item: _as_int(item.get("monthseq")) or 0):
            pond = row.get("pondfreqcl")
            flood = row.get("flodfreqcl")
            ponding_items.append((pond, month_weight))
            flooding_items.append((flood, month_weight))
            monthly_records.append(
                {
                    "cokey": cokey,
                    "monthseq": _as_int(row.get("monthseq")),
                    "pondfreqcl": "UNKNOWN" if pond is None else pond,
                    "flodfreqcl": "UNKNOWN" if flood is None else flood,
                    "interpreted_null_as_none": False,
                }
            )

    ponding_frequency_distribution = _weighted_category_distribution(ponding_items)
    flooding_frequency_distribution = _weighted_category_distribution(flooding_items)

    restriction_by_cokey = {str(row["cokey"]): row for row in restrictions}
    restrictive_records: list[dict[str, Any]] = []
    restrictive_distribution_items: list[tuple[str, float]] = []
    for item in component_support_weights:
        cokey = item["cokey"]
        row = restriction_by_cokey.get(cokey)
        if row is None or (row.get("reskind") is None and row.get("resdept_r") is None):
            status = "UNKNOWN"
            kind = None
            depth = None
            distribution_key = "UNKNOWN"
        else:
            status = "KNOWN"
            kind = row.get("reskind")
            depth = _as_float(row.get("resdept_r"))
            distribution_key = f"{kind}|{depth}"
        restrictive_records.append(
            {
                "cokey": cokey,
                "component_support_weight": item["component_support_weight"],
                "restrictive_layer_status": status,
                "reskind": kind,
                "resdept_r_cm": depth,
                "interpreted_as_unrestricted": False,
            }
        )
        restrictive_distribution_items.append(
            (distribution_key, item["component_support_weight"])
        )
    restrictive_layer_distribution = _weighted_category_distribution(
        restrictive_distribution_items
    )

    access_by_id = {
        str(item["ecological_site_id"]): item for item in ecological_site_access
    }
    ecological_site_weights: dict[str, dict[str, Any]] = {}
    ecological_unknown_share = 0.0
    for item in component_support_weights:
        site_id = item.get("ecoclassid")
        weight = item["component_support_weight"]
        if site_id is None:
            ecological_unknown_share += weight
            continue
        site_id = str(site_id)
        access = access_by_id.get(site_id) or {}
        bucket = ecological_site_weights.setdefault(
            site_id,
            {
                "ecological_site_id": site_id,
                "ecological_site_name": item.get("ecoclassname"),
                "ecological_site_type": item.get("ecoclasstypename"),
                "component_support_weight": 0.0,
                "public_description_access_status": ecological_site_access_status(access),
                "access_error_type": access.get("error_type"),
                "source_url": access.get("final_url") or access.get("requested_url"),
                "retrieval_timestamp": fetched_at,
                "response_hash": access.get("response_sha256"),
                "current_vegetation_state": "UNKNOWN",
                "operation_ranking_effect": "NONE",
            },
        )
        bucket["component_support_weight"] += weight

    ecological_site_references = sorted(
        ecological_site_weights.values(),
        key=lambda item: (-item["component_support_weight"], item["ecological_site_id"]),
    )

    awc_result = derive_available_water_storage(
        horizons,
        declared_depth_interval_cm=declared_awc_depth_interval_cm,
        component_support_weights=support_by_cokey,
    )

    if coverage_fraction >= 1.0 - 1e-9:
        coverage_status = "COMPLETE"
        coverage_detail = "COMPLETE_WITH_NUMERIC_TOLERANCE"
        input_quality_state = "PARCEL_COMPLETE"
    elif coverage_fraction > 0:
        coverage_status = "PARTIAL"
        coverage_detail = "PARTIAL"
        input_quality_state = "PARCEL_INCOMPLETE"
    else:
        coverage_status = "UNKNOWN"
        coverage_detail = "UNKNOWN"
        input_quality_state = "PARCEL_INCOMPLETE"

    fixture_refs = list(
        source_fixture_references
        or [
            "test-data/live-results/cper/cper_sda_spatial_coverage_2026-08-07.json",
            "test-data/live-results/cper/cper_sda_mapunit_component_ecosite_2026-08-07.json",
            "test-data/live-results/cper/cper_sda_horizons_2026-08-07.json",
            "test-data/live-results/cper/cper_sda_restrictions_2026-08-07.json",
            "test-data/live-results/cper/cper_sda_monthly_wetness_2026-08-07.json",
            "test-data/live-results/cper/cper_ecological_site_access_2026-08-07.json",
        ]
    )
    artifact_hash = _sha256_json(
        {
            "spatial_coverage": spatial_coverage,
            "components": components,
            "horizons": horizons,
            "restrictions": restrictions,
            "monthly": monthly,
            "ecological_site_access": list(ecological_site_access),
        }
    )

    mireye_point_qa = None
    if mireye_point is not None:
        mireye_point_qa = {
            "role": "POINT_DISPLAY_AND_QA_ONLY",
            "may_represent_whole_parcel": False,
            "fetched_at": mireye_point.get("fetched_at"),
            "fields": mireye_point.get("fields"),
            "partial_failures": mireye_point.get("partial_failures") or [],
        }

    unknowns = [
        "Within-map-unit component locations are unknown.",
        "Null restrictive-layer records remain UNKNOWN and do not prove unrestricted depth.",
        "Null monthly ponding/flooding classes remain UNKNOWN and are not interpreted as None.",
        "Ecological-site references do not establish current vegetation state.",
        "No approved depth interval exists for parcel available-water storage in the Land Profile.",
    ]
    if ecological_unknown_share > 0:
        unknowns.append(
            "Some components lack ecological-site linkage; absent linkage remains UNKNOWN."
        )
    if duplicate_component_rows:
        unknowns.append(
            f"{duplicate_component_rows} duplicate SDA component join rows were deduplicated by mukey+cokey."
        )
    if spatial_overlap_normalization_factor < 1.0:
        unknowns.append(
            "Overlapping SDA WFS map-unit intersections were proportionally reconciled to union-covered parcel area."
        )

    return {
        "factor_id": "F04_SOIL_WETNESS_ECOLOGICAL_SITE",
        "derivation_spec_version": DERIVATION_SPEC_VERSION,
        "input_quality_state": input_quality_state,
        "source_fixture_references": fixture_refs,
        "parcel_coverage": {
            "status": coverage_status,
            "detail": coverage_detail,
            "requested_area_m2": requested_area,
            "covered_area_m2": covered_area,
            "uncovered_area_m2": uncovered_area,
            "coverage_fraction": coverage_fraction,
            "coverage_calculated_from_polygon_intersection": True,
            "successful_query_implies_complete_coverage": False,
            "intersecting_mapunit_count": int(
                spatial_coverage.get("intersecting_mapunit_count") or len(mu_areas)
            ),
        },
        "mapunit_area_distribution": mapunit_area_distribution,
        "raw_mapunit_intersection_area_sum_m2": raw_mapunit_area_sum,
        "spatial_overlap_normalization_factor": spatial_overlap_normalization_factor,
        "component_support_weights": component_support_weights,
        "known_component_share": known_component_share,
        "known_component_share_before_guard": known_component_share_before_guard,
        "duplicate_component_rows_deduplicated": duplicate_component_rows,
        "unaccounted_component_share": unaccounted_component_share,
        "component_percentages_renormalized": False,
        "drainage_class_distribution": drainage_class_distribution,
        "hydrologic_soil_group_distribution": hydrologic_soil_group_distribution,
        "ponding_frequency_distribution": ponding_frequency_distribution,
        "flooding_frequency_distribution": flooding_frequency_distribution,
        "monthly_wetness_records": monthly_records,
        "restrictive_layer_records": restrictive_records,
        "restrictive_layer_distribution": restrictive_layer_distribution,
        "ecological_site_references": ecological_site_references,
        "ecological_site_unknown_share": ecological_unknown_share,
        "available_water_storage": awc_result,
        "mireye_point_qa": mireye_point_qa,
        "applicability": {
            "domain_status": "IN_DOCUMENTED_PRODUCT_SCOPE",
            "review_status": "VERIFIED",
            "basis": ["F04_SOIL_SITE_ATOMICITY_AND_SOURCE_AUDIT", "CPER_LIVE_DATA_GATE"],
            "notes": "F04 v0.1 is data-quality and context only; no directional suitability signal is approved.",
        },
        "coverage": {
            "status": coverage_status,
            "requested_area_m2": requested_area,
            "valid_area_m2": covered_area,
            "valid_coverage_fraction": coverage_fraction,
            "adapter_status": "SDA_POLYGON_AND_TABULAR_VERIFIED",
        },
        "quality": {
            "confidence_state": "SUPPORTED" if input_quality_state == "PARCEL_COMPLETE" else "NEEDS_VERIFICATION",
            "modeled": False,
            "component_count": len(component_support_weights),
            "horizon_record_count": len(horizons),
            "restriction_record_count": len(restrictions),
            "monthly_wetness_record_count": len(monthly),
            "components_with_ecological_site_linkage": sum(
                1 for item in component_support_weights if item.get("ecoclassid")
            ),
            "derivation_contract_verified": True,
            "numeric_average_of_controlled_categories": False,
        },
        "provenance": {
            "source_reference": "USDA_NRCS_SDA_SSURGO_AND_EDIT",
            "fetched_at": fetched_at,
            "geometry_hash": geometry_hash,
            "response_or_artifact_hash": artifact_hash,
            "derivation_spec_version": DERIVATION_SPEC_VERSION,
            "primary_path": "OFFICIAL_SDA_PARCEL_POLYGONS_COMPONENTS_HORIZONS",
            "mireye_role": "POINT_DISPLAY_AND_QA_ONLY",
        },
        "limitations": [
            "No composite soil score is created.",
            "Controlled categories are preserved as distributions, not ordinal averages.",
            "Flooding frequency is soil/site context only and is not a FEMA flood-hazard determination.",
            "Ecological-site names do not imply current vegetation or operation ranking.",
            "Mireye centroid soil fields must not replace parcel-wide F04 evidence.",
            "Available-water storage is omitted from profile evidence until a depth interval is approved.",
        ],
        "unknowns": unknowns,
        "ranking_effect": "NONE",
        "directional_signal_allowed": False,
    }


def derive_f04_from_fixture_dir(fixture_dir: str | Path) -> dict[str, Any]:
    """Load CPER F04 fixtures from disk and derive parcel facts."""
    root = Path(fixture_dir)
    spatial = json.loads((root / "cper_sda_spatial_coverage_2026-08-07.json").read_text())
    components = json.loads(
        (root / "cper_sda_mapunit_component_ecosite_2026-08-07.json").read_text()
    )
    horizons = json.loads((root / "cper_sda_horizons_2026-08-07.json").read_text())
    restrictions = json.loads((root / "cper_sda_restrictions_2026-08-07.json").read_text())
    monthly = json.loads((root / "cper_sda_monthly_wetness_2026-08-07.json").read_text())
    ecological = json.loads((root / "cper_ecological_site_access_2026-08-07.json").read_text())
    mireye = json.loads((root / "cper_mireye_f04_centroid_2026-08-07.json").read_text())
    return derive_f04_parcel_facts(
        spatial_coverage=spatial,
        components_table=components,
        horizons_table=horizons,
        restrictions_table=restrictions,
        monthly_wetness_table=monthly,
        ecological_site_access=ecological,
        mireye_point=mireye,
    )


def land_profile_f04_section(derived: Mapping[str, Any]) -> dict[str, Any]:
    """Shape derivation output for inclusion in a Land Profile fixture."""
    return {
        "input_quality_state": derived["input_quality_state"],
        "derivation_spec": derived["derivation_spec_version"],
        "result_reference": "test-data/live-results/cper/f04_derivation_result_2026-08-07.json",
        "source_fixture_references": derived["source_fixture_references"],
        "parcel_coverage": derived["parcel_coverage"],
        "mapunit_area_distribution": derived["mapunit_area_distribution"],
        "component_support_weights": derived["component_support_weights"],
        "known_component_share": derived["known_component_share"],
        "unaccounted_component_share": derived["unaccounted_component_share"],
        "component_percentages_renormalized": derived["component_percentages_renormalized"],
        "drainage_class_distribution": derived["drainage_class_distribution"],
        "hydrologic_soil_group_distribution": derived["hydrologic_soil_group_distribution"],
        "ponding_frequency_distribution": derived["ponding_frequency_distribution"],
        "flooding_frequency_distribution": derived["flooding_frequency_distribution"],
        "restrictive_layer_records": derived["restrictive_layer_records"],
        "restrictive_layer_distribution": derived["restrictive_layer_distribution"],
        "ecological_site_references": derived["ecological_site_references"],
        "ecological_site_unknown_share": derived["ecological_site_unknown_share"],
        "available_water_storage": {
            "status": derived["available_water_storage"]["status"],
            "derived_storage_mm": derived["available_water_storage"]["derived_storage_mm"],
            "note": "Reusable AWC derivation exists; no approved depth interval is applied in this Land Profile.",
        },
        "mireye_point_qa": derived["mireye_point_qa"],
        "applicability": derived["applicability"],
        "coverage": derived["coverage"],
        "quality": derived["quality"],
        "provenance": derived["provenance"],
        "limitations": derived["limitations"],
        "unknowns": derived["unknowns"],
        "ranking_effect": "NONE",
    }
