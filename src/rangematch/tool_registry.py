"""Tool registry for RangeMatch Planner routing (planning metadata only).

No live network execution in this module. Tools describe intended adapters,
authority, and failure behavior for DAG construction.
"""

from __future__ import annotations

from typing import Any

PLANNER_VERSION = "RANGEMATCH_PLANNER@0.1.0"

# Canonical knowledge / report order (not execution order).
CANONICAL_FACTOR_REPORT_ORDER = (
    "F01_TOPOGRAPHY",
    "F02_HERBACEOUS_RESOURCE",
    "F03_LIVESTOCK_WATER",
    "F04_SOIL_WETNESS_ECOLOGICAL_SITE",
    "F05_CLIMATE_DROUGHT_EXPOSURE",
    "F06_PARCEL_CONFIGURATION",
    "F07_ROAD_AND_PHYSICAL_ACCESS",
    "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE",
)

# Peers after geometry + F06 gate.
PEER_FACTORS_AFTER_F06 = (
    "F01_TOPOGRAPHY",
    "F02_HERBACEOUS_RESOURCE",
    "F03_LIVESTOCK_WATER",
    "F04_SOIL_WETNESS_ECOLOGICAL_SITE",
    "F05_CLIMATE_DROUGHT_EXPOSURE",
    "F07_ROAD_AND_PHYSICAL_ACCESS",
)

ACTIONS = ("FETCH", "REUSE", "COMPUTE", "EVALUATE", "PROJECT", "EXPLAIN")

# Explicitly unauthorized in this prototype planner.
UNAUTHORIZED_TOOL_IDS = frozenset(
    {
        "F09_ANY",
        "BATCH_PARCEL_SEARCH",
        "ICP_FINDER",
        "PORTFOLIO_RANKER",
        "REGION_SITE_DISCOVERY",
    }
)


def _tool(
    tool_id: str,
    *,
    purpose: str,
    expected_output_type: str,
    canonical_authority: str,
    failure_behavior: str,
    prohibited_promotions: list[str],
    endpoint: str | None = None,
    factor_id: str | None = None,
    network: bool = False,
) -> dict[str, Any]:
    return {
        "tool_id": tool_id,
        "purpose": purpose,
        "expected_output_type": expected_output_type,
        "canonical_authority": canonical_authority,
        "failure_behavior": failure_behavior,
        "prohibited_promotions": list(prohibited_promotions),
        "endpoint": endpoint,
        "factor_id": factor_id,
        "network_capable": network,
        "authorized_for_prototype": tool_id not in UNAUTHORIZED_TOOL_IDS,
    }


TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "geometry.resolve": _tool(
        "geometry.resolve",
        purpose="Resolve address/APN/geometry to exactly one parcel and bind geometry hash",
        expected_output_type="PARCEL_GEOMETRY_BINDING",
        canonical_authority="GEOMETRY_BINDING",
        failure_behavior="Fail closed; do not invent a parcel; mark UNKNOWN/NEEDS_VERIFICATION",
        prohibited_promotions=["multi-parcel batch binding", "silent geometry repair"],
    ),
    "geometry.validate_one_parcel": _tool(
        "geometry.validate_one_parcel",
        purpose="Reject FeatureCollections with more than one Feature",
        expected_output_type="ONE_PARCEL_VALIDATION",
        canonical_authority="GEOMETRY_VALIDATION",
        failure_behavior="Raise plan error; no batch workflow",
        prohibited_promotions=["batch", "ICP", "portfolio", "region search"],
    ),
    "mireye.property_diligence": _tool(
        "mireye.property_diligence",
        purpose="Property Diligence / lookup for parcel, jurisdiction, zoning, property context",
        expected_output_type="PROPERTY_DILIGENCE_CONTEXT",
        canonical_authority="NON_CANONICAL_CONTEXT",
        failure_behavior="Preserve disposition/parcel_grade/confidence/failures; never invent title",
        prohibited_promotions=[
            "title opinion",
            "legal access certainty",
            "F01-F08 Land Facts",
        ],
        endpoint="/v1/lookup",
        network=True,
    ),
    "mireye.point_land": _tool(
        "mireye.point_land",
        purpose="Point Land Read for terrain and reviewed land-cover fields",
        expected_output_type="POINT_LAND_CONTEXT",
        canonical_authority="NON_CANONICAL_POINT_QA",
        failure_behavior="Keep missing fields explicit; do not promote point to parcel facts",
        prohibited_promotions=[
            "parcel F01 topography Land Facts",
            "parcel F02 herbaceous Land Facts",
            "parcel F04 soil Land Facts",
            "parcel F08 woody Land Facts",
        ],
        endpoint="/v1/fetch",
        network=True,
    ),
    "mireye.point_hazard": _tool(
        "mireye.point_hazard",
        purpose="Point Hazards Read for flood/wetland/wildfire-related triggers",
        expected_output_type="POINT_HAZARD_CONTEXT",
        canonical_authority="NON_CANONICAL_HAZARD_TRIGGER",
        failure_behavior="Preserve partial_failures; never drop silently",
        prohibited_promotions=[
            "final parcel hazard determination",
            "legal compliance conclusion",
        ],
        endpoint="/v1/fetch",
        network=True,
    ),
    "factor.f06_parcel_configuration": _tool(
        "factor.f06_parcel_configuration",
        purpose="Compute parcel geometry validity, hash, area, working CRS, configuration context",
        expected_output_type="F06_FACTOR_RESULT",
        canonical_authority="CANONICAL_FACTOR",
        failure_behavior="Invalid geometry blocks silent measure; mark NEEDS_VERIFICATION/UNKNOWN",
        prohibited_promotions=["fencing cost", "carrying capacity", "suitability"],
        factor_id="F06_PARCEL_CONFIGURATION",
    ),
    "adapter.usgs_3dep": _tool(
        "adapter.usgs_3dep",
        purpose="Parcel topography derivation path for F01",
        expected_output_type="F01_FACTOR_RESULT",
        canonical_authority="CANONICAL_FACTOR",
        failure_behavior="Preserve provenance gaps; no invented DEM stats",
        prohibited_promotions=["suitability threshold from slope alone"],
        factor_id="F01_TOPOGRAPHY",
        network=True,
    ),
    "adapter.rap_cover_production": _tool(
        "adapter.rap_cover_production",
        purpose="RAP coverV3/productionV3 parcel path for F02; produce reusable coverV3 artifact",
        expected_output_type="F02_FACTOR_RESULT_AND_COVERV3_ARTIFACT",
        canonical_authority="CANONICAL_FACTOR",
        failure_behavior="COVERAGE_UNQUANTIFIED remains explicit; no forced sum-to-100",
        prohibited_promotions=["available forage", "palatability", "carrying capacity"],
        factor_id="F02_HERBACEOUS_RESOURCE",
        network=True,
    ),
    "adapter.nhd_water_candidates": _tool(
        "adapter.nhd_water_candidates",
        purpose="Mapped water candidates + remote presence support for F03",
        expected_output_type="F03_FACTOR_RESULT",
        canonical_authority="CANONICAL_FACTOR",
        failure_behavior="Unverified candidates stay NEEDS_VERIFICATION; zero verified ≠ no water",
        prohibited_promotions=["usable livestock water certainty"],
        factor_id="F03_LIVESTOCK_WATER",
        network=True,
    ),
    "adapter.usda_sda": _tool(
        "adapter.usda_sda",
        purpose="Official SDA parcel soil/wetness/ecological-site path for F04",
        expected_output_type="F04_FACTOR_RESULT",
        canonical_authority="CANONICAL_FACTOR",
        failure_behavior="EDIT timeouts remain UNKNOWN; do not invent components",
        prohibited_promotions=["current vegetation state from ecological site alone"],
        factor_id="F04_SOIL_WETNESS_ECOLOGICAL_SITE",
        network=True,
    ),
    "adapter.noaa_ncei_precip": _tool(
        "adapter.noaa_ncei_precip",
        purpose="Canonical precipitation normals + drought context path for F05",
        expected_output_type="F05_FACTOR_RESULT",
        canonical_authority="CANONICAL_FACTOR",
        failure_behavior="Missing normals → NEEDS_VERIFICATION; no climate suitability threshold",
        prohibited_promotions=["climate suitability score", "forage failure certainty"],
        factor_id="F05_CLIMATE_DROUGHT_EXPOSURE",
        network=True,
    ),
    "adapter.tiger_roads": _tool(
        "adapter.tiger_roads",
        purpose="TIGER/Line 2025 All Roads physical-access context for F07",
        expected_output_type="F07_FACTOR_RESULT",
        canonical_authority="CANONICAL_FACTOR",
        failure_behavior="Incomplete county coverage → no silent measure; legal access not inferred",
        prohibited_promotions=["legal access", "usable entrance", "landlocked certainty"],
        factor_id="F07_ROAD_AND_PHYSICAL_ACCESS",
        network=True,
    ),
    "factor.f08_woody_reuse_rap": _tool(
        "factor.f08_woody_reuse_rap",
        purpose="Derive F08 woody fractions by REUSING F02-compatible RAP coverV3 artifact",
        expected_output_type="F08_FACTOR_RESULT",
        canonical_authority="CANONICAL_FACTOR",
        failure_behavior="Missing/mismatched F02 artifact → NEEDS_VERIFICATION; never duplicate RAP FETCH",
        prohibited_promotions=[
            "browse availability",
            "obstruction class",
            "duplicate coverV3 fetch",
        ],
        factor_id="F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE",
        network=False,
    ),
    "profile.assemble": _tool(
        "profile.assemble",
        purpose="Assemble Land Profile Factor payloads in canonical report order F01–F08",
        expected_output_type="LAND_PROFILE",
        canonical_authority="LAND_PROFILE_ASSEMBLY",
        failure_behavior="Missing Factor remains explicit MISSING/UNKNOWN; do not invent",
        prohibited_promotions=["reordering science by completion time"],
    ),
    "engine.evaluate": _tool(
        "engine.evaluate",
        purpose="Run deterministic evaluate_land_profile → MatchResult",
        expected_output_type="MATCH_RESULT",
        canonical_authority="DETERMINISTIC_ENGINE",
        failure_behavior="Engine output authoritative; planner cannot override labels/signals",
        prohibited_promotions=["LLM override of decisions", "numeric suitability score"],
    ),
    "output.project_unified": _tool(
        "output.project_unified",
        purpose="Project Land Profile + MatchResult into RANGEMATCH_UNIFIED_OUTPUT@0.1.0",
        expected_output_type="UNIFIED_OUTPUT_ENVELOPE",
        canonical_authority="UNIFIED_OUTPUT_PROJECTION",
        failure_behavior="Validation errors fail closed; do not invent envelope fields",
        prohibited_promotions=["discarding unknowns or coverage limitations"],
    ),
    "explanation.bind_and_product": _tool(
        "explanation.bind_and_product",
        purpose="Bind explanation to match_result_hash and project five buyer sections",
        expected_output_type="EXPLANATION_AND_BUYER_REPORT",
        canonical_authority="CONSTRAINED_EXPLANATION",
        failure_behavior="Refuse unbound explanation; HOLD ≠ unsuitable",
        prohibited_promotions=["changing engine labels", "legal final opinion"],
    ),
    "diligence.dynamic_from_planned_actions": _tool(
        "diligence.dynamic_from_planned_actions",
        purpose="Route planned_actions into non-canonical dynamic diligence findings only",
        expected_output_type="DYNAMIC_DILIGENCE_FINDINGS",
        canonical_authority="NON_CANONICAL_DILIGENCE",
        failure_behavior="PROFESSIONAL_CONFIRMATION_REQUIRED; never write into F01–F08 Land Facts",
        prohibited_promotions=["F09 Factor", "canonical Land Fact mutation", "final legal advice"],
    ),
}


def get_tool(tool_id: str) -> dict[str, Any]:
    if tool_id not in TOOL_REGISTRY:
        raise KeyError(f"unknown tool_id: {tool_id}")
    if tool_id in UNAUTHORIZED_TOOL_IDS:
        raise PermissionError(f"tool not authorized: {tool_id}")
    return dict(TOOL_REGISTRY[tool_id])


def assert_no_unauthorized_tools(tool_ids: list[str]) -> None:
    bad = [t for t in tool_ids if t in UNAUTHORIZED_TOOL_IDS or t.startswith("F09_")]
    if bad:
        raise PermissionError(f"unauthorized tools in plan: {bad}")
