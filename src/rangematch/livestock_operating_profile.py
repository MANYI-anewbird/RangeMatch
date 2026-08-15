"""Deterministic Livestock Operating Profile projector.

No LLM. No hand-copied canonical numbers. Feed / Drink / Move only.
Contract: docs/LIVESTOCK_OPERATING_PROFILE_CONTRACT.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from rangematch.advisor_contract import canonical_dumps, packet_hash
from rangematch.advisor_packet import F03_FAILED, is_cper_engineering_fixture
from rangematch.advisor_visit import (
    derive_authoritative_visit_purpose,
    field_drawable_objects,
)
from rangematch.livestock_movement import derive_movement_labels
from rangematch.unified_output import sha256_canonical

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "schemas"
    / "livestock_operating_profile.schema.json"
)
_FORBIDDEN_NUMBER_KEYS = {
    "value",
    "magnitude",
    "amount",
    "acres",
    "kg_ha",
    "mm",
    "percent",
    "count",
    "distance_m",
}

PROFILE_SCHEMA = "RANGEMATCH_LIVESTOCK_OPERATING_PROFILE@0.1.0"
PROJECTOR_ID = "DETERMINISTIC_OPERATING_PROFILE@0.1.0"

DOMAIN_FEED = "FEED"
DOMAIN_DRINK = "DRINK"
DOMAIN_MOVE = "MOVE"
POPULATED_DOMAINS = (DOMAIN_FEED, DOMAIN_DRINK, DOMAIN_MOVE)
ATTENTION_FALLBACK = (DOMAIN_DRINK, DOMAIN_MOVE, DOMAIN_FEED)

PORTRAIT_INPUT = "PORTRAIT_INPUT"
ACTION_INPUT = "ACTION_INPUT"
GUARDRAIL_ONLY = "GUARDRAIL_ONLY"

STATEMENT_TYPE_DOMAIN = {
    "MODELED_PRODUCTION_SNAPSHOT": DOMAIN_FEED,
    "PRECIPITATION_CONTEXT": DOMAIN_FEED,
    "MAPPED_HYDROGRAPHY_LEAD_COUNT": DOMAIN_DRINK,
    "DRAWABLE_WATER_LEAD_COUNT": DOMAIN_DRINK,
    "DRAWABLE_WATER_NONE": DOMAIN_DRINK,
    "WATER_INVENTORY_UNAVAILABLE": DOMAIN_DRINK,
    "NO_MAPPED_HYDROGRAPHY_LEADS": DOMAIN_DRINK,
    "PARCEL_AREA_CONTEXT": DOMAIN_MOVE,
    "SLOPE_MEDIAN_CONTEXT": DOMAIN_MOVE,
    "ROAD_BOUNDARY_RELATIONSHIP": DOMAIN_MOVE,
    "PARCEL_COMPACTNESS": DOMAIN_MOVE,
    "PARCEL_FRAGMENTATION": DOMAIN_MOVE,
    "DRAWABLE_WATER_DISTRIBUTION": DOMAIN_MOVE,
}

STATEMENT_NARRATIVE_ROLE = {
    "MODELED_PRODUCTION_SNAPSHOT": PORTRAIT_INPUT,
    "PRECIPITATION_CONTEXT": PORTRAIT_INPUT,
    "MAPPED_HYDROGRAPHY_LEAD_COUNT": PORTRAIT_INPUT,
    "DRAWABLE_WATER_LEAD_COUNT": PORTRAIT_INPUT,
    "DRAWABLE_WATER_NONE": GUARDRAIL_ONLY,
    "WATER_INVENTORY_UNAVAILABLE": GUARDRAIL_ONLY,
    "NO_MAPPED_HYDROGRAPHY_LEADS": ACTION_INPUT,
    "PARCEL_AREA_CONTEXT": PORTRAIT_INPUT,
    "SLOPE_MEDIAN_CONTEXT": PORTRAIT_INPUT,
    "ROAD_BOUNDARY_RELATIONSHIP": PORTRAIT_INPUT,
    "PARCEL_COMPACTNESS": PORTRAIT_INPUT,
    "PARCEL_FRAGMENTATION": PORTRAIT_INPUT,
    "DRAWABLE_WATER_DISTRIBUTION": PORTRAIT_INPUT,
}

DANGEROUS_INFERENCES = frozenset(
    {
        "AVAILABLE_FORAGE",
        "CARRYING_CAPACITY",
        "HERD_SIZE",
        "USABLE_LIVESTOCK_WATER",
        "YEAR_ROUND_RELIABILITY",
        "LEGAL_WATER_RIGHT",
        "LEGAL_ACCESS",
        "USABLE_ENTRANCE",
        "GRAZABLE_ACRES",
        "CLIMATE_ADEQUACY",
        "DROUGHT_RESILIENCE",
        "SUITABILITY",
        "ABSENCE_FROM_FAILED_INVENTORY",
        "FACILITY_INVENTION",
        "TREND_OR_RESILIENCE",
    }
)

STATEMENT_INFERENCE_POLICY: dict[str, dict[str, frozenset[str]]] = {
    "MODELED_PRODUCTION_SNAPSHOT": {
        "allowed": frozenset({"MODELED_VEGETATION_CONTEXT"}),
        "prohibited": frozenset(
            {"AVAILABLE_FORAGE", "CARRYING_CAPACITY", "HERD_SIZE", "TREND_OR_RESILIENCE"}
        ),
    },
    "PRECIPITATION_CONTEXT": {
        "allowed": frozenset({"CLIMATE_LOOKUP_CONTEXT"}),
        "prohibited": frozenset(
            {"CLIMATE_ADEQUACY", "DROUGHT_RESILIENCE", "TREND_OR_RESILIENCE"}
        ),
    },
    "MAPPED_HYDROGRAPHY_LEAD_COUNT": {
        "allowed": frozenset({"MAPPED_HYDROGRAPHY_LEADS"}),
        "prohibited": frozenset(
            {"USABLE_LIVESTOCK_WATER", "YEAR_ROUND_RELIABILITY", "LEGAL_WATER_RIGHT"}
        ),
    },
    "DRAWABLE_WATER_LEAD_COUNT": {
        "allowed": frozenset({"DRAWABLE_WATER_ROUTE_LEADS"}),
        "prohibited": frozenset({"USABLE_LIVESTOCK_WATER", "YEAR_ROUND_RELIABILITY"}),
    },
    "DRAWABLE_WATER_NONE": {
        "allowed": frozenset(),
        "prohibited": frozenset({"USABLE_LIVESTOCK_WATER", "DRAWABLE_WATER_ROUTE_LEADS"}),
    },
    "WATER_INVENTORY_UNAVAILABLE": {
        "allowed": frozenset(),
        "prohibited": frozenset(
            {"ABSENCE_FROM_FAILED_INVENTORY", "USABLE_LIVESTOCK_WATER", "YEAR_ROUND_RELIABILITY"}
        ),
    },
    "NO_MAPPED_HYDROGRAPHY_LEADS": {
        "allowed": frozenset(),
        "prohibited": frozenset({"ABSENCE_FROM_FAILED_INVENTORY", "USABLE_LIVESTOCK_WATER"}),
    },
    "PARCEL_AREA_CONTEXT": {
        "allowed": frozenset({"PARCEL_AREA_CONTEXT"}),
        "prohibited": frozenset({"GRAZABLE_ACRES", "FACILITY_INVENTION"}),
    },
    "SLOPE_MEDIAN_CONTEXT": {
        "allowed": frozenset({"TERRAIN_MEDIAN_CONTEXT"}),
        "prohibited": frozenset({"SUITABILITY"}),
    },
    "ROAD_BOUNDARY_RELATIONSHIP": {
        "allowed": frozenset({"PHYSICAL_ROAD_CONTACT"}),
        "prohibited": frozenset({"LEGAL_ACCESS", "USABLE_ENTRANCE"}),
    },
    "PARCEL_COMPACTNESS": {
        "allowed": frozenset({"PARCEL_SHAPE_CONTEXT"}),
        "prohibited": frozenset({"SUITABILITY", "GRAZABLE_ACRES", "FACILITY_INVENTION"}),
    },
    "PARCEL_FRAGMENTATION": {
        "allowed": frozenset({"PARCEL_SHAPE_CONTEXT"}),
        "prohibited": frozenset({"SUITABILITY", "GRAZABLE_ACRES", "FACILITY_INVENTION"}),
    },
    "DRAWABLE_WATER_DISTRIBUTION": {
        "allowed": frozenset({"WATER_LEAD_SPATIAL_CONTEXT"}),
        "prohibited": frozenset({"USABLE_LIVESTOCK_WATER", "SUITABILITY"}),
    },
}

BOTTLENECK_TO_DOMAIN = {
    "BOTTLENECK_WATER_EVIDENCE": DOMAIN_DRINK,
    "BOTTLENECK_LEGAL_ACCESS": DOMAIN_MOVE,
    "BOTTLENECK_FORAGE_LEAP": DOMAIN_FEED,
    "BOTTLENECK_PARCEL_CONFIRMATION": DOMAIN_MOVE,
}


class OperatingProfileError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _obs_index(packet: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["observation_id"]): dict(row)
        for row in (packet.get("observations") or [])
        if row.get("observation_id")
    }


def _obs_usable(row: Mapping[str, Any] | None) -> bool:
    if not row:
        return False
    if row.get("evidence_state") == "SOURCE_UNAVAILABLE":
        return False
    return row.get("value") is not None


def _drawable_ids(packet: Mapping[str, Any]) -> list[str]:
    return [
        str(row.get("candidate_id"))
        for row in field_drawable_objects(list(packet.get("candidate_objects") or []))
        if row.get("candidate_id")
    ]


def _statement(
    *,
    statement_id: str,
    statement_type: str,
    obs: Mapping[str, Any] | None,
    extra_evidence: list[str] | None = None,
    object_refs: list[str] | None = None,
    qualifiers: list[str] | None = None,
    evidence_state: str | None = None,
) -> dict[str, Any]:
    domain = STATEMENT_TYPE_DOMAIN[statement_type]
    role = STATEMENT_NARRATIVE_ROLE[statement_type]
    policy = STATEMENT_INFERENCE_POLICY[statement_type]
    refs = []
    if obs and obs.get("observation_id"):
        refs.append(str(obs["observation_id"]))
    for item in extra_evidence or []:
        if item not in refs:
            refs.append(item)
    if not refs:
        raise OperatingProfileError("STATEMENT_EVIDENCE_MISSING", statement_id)
    return {
        "statement_id": statement_id,
        "domain": domain,
        "statement_type": statement_type,
        "value_refs": [str(obs["observation_id"])] if obs and obs.get("observation_id") else [],
        "evidence_refs": refs,
        "object_refs": list(object_refs or []),
        "qualifiers": list(qualifiers or []),
        "evidence_state": evidence_state or str((obs or {}).get("evidence_state") or "UNKNOWN"),
        "spatial_scope": "PARCEL",
        "allowed_inferences": sorted(policy["allowed"]),
        "prohibited_inferences": sorted(policy["prohibited"]),
        "displayable": role == PORTRAIT_INPUT,
        "narrative_role": role,
    }


def _project_feed(obs: Mapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rap = obs.get("OBS_RAP_PROD")
    if _obs_usable(rap):
        rows.append(
            _statement(
                statement_id="FEED_MODELED_PRODUCTION_SNAPSHOT",
                statement_type="MODELED_PRODUCTION_SNAPSHOT",
                obs=rap,
                qualifiers=["SINGLE_YEAR_SNAPSHOT"],
            )
        )
    precip = obs.get("OBS_PRECIP")
    if _obs_usable(precip):
        rows.append(
            _statement(
                statement_id="FEED_PRECIPITATION_CONTEXT",
                statement_type="PRECIPITATION_CONTEXT",
                obs=precip,
            )
        )
    return rows


def _project_drink(packet: Mapping[str, Any], obs: Mapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    water = obs.get("OBS_WATER_COUNT")
    f03 = str((packet.get("technical_references") or {}).get("f03_status") or "")
    drawable = _drawable_ids(packet)
    if f03 == F03_FAILED or (water and water.get("evidence_state") == "SOURCE_UNAVAILABLE"):
        if not water:
            raise OperatingProfileError(
                "STATEMENT_EVIDENCE_MISSING",
                "WATER_INVENTORY_UNAVAILABLE requires OBS_WATER_COUNT",
            )
        rows.append(
            _statement(
                statement_id="DRINK_WATER_INVENTORY_UNAVAILABLE",
                statement_type="WATER_INVENTORY_UNAVAILABLE",
                obs=water,
                qualifiers=["NOT_ABSENCE_FINDING"],
                evidence_state="SOURCE_UNAVAILABLE",
            )
        )
        return rows
    if _obs_usable(water) and water.get("value") == 0:
        rows.append(
            _statement(
                statement_id="DRINK_NO_MAPPED_HYDROGRAPHY_LEADS",
                statement_type="NO_MAPPED_HYDROGRAPHY_LEADS",
                obs=water,
                qualifiers=["NOT_ABSENCE_FINDING"],
            )
        )
        return rows
    if _obs_usable(water):
        rows.append(
            _statement(
                statement_id="DRINK_MAPPED_HYDROGRAPHY_LEAD_COUNT",
                statement_type="MAPPED_HYDROGRAPHY_LEAD_COUNT",
                obs=water,
                qualifiers=["LEADS_NOT_INFRASTRUCTURE"],
            )
        )
        if drawable:
            rows.append(
                _statement(
                    statement_id="DRINK_DRAWABLE_WATER_LEAD_COUNT",
                    statement_type="DRAWABLE_WATER_LEAD_COUNT",
                    obs=water,
                    object_refs=drawable,
                )
            )
        else:
            rows.append(
                _statement(
                    statement_id="DRINK_DRAWABLE_WATER_NONE",
                    statement_type="DRAWABLE_WATER_NONE",
                    obs=water,
                    qualifiers=["CATEGORY_LEVEL_PURPOSE_ONLY"],
                )
            )
    return rows


def _project_move(
    packet: Mapping[str, Any],
    obs: Mapping[str, dict[str, Any]],
    unified_output: Mapping[str, Any],
    geometry_hash: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    area = obs.get("OBS_AREA")
    if _obs_usable(area):
        rows.append(
            _statement(
                statement_id="MOVE_PARCEL_AREA_CONTEXT",
                statement_type="PARCEL_AREA_CONTEXT",
                obs=area,
                extra_evidence=[geometry_hash],
            )
        )
    slope = obs.get("OBS_SLOPE")
    if _obs_usable(slope):
        rows.append(
            _statement(
                statement_id="MOVE_SLOPE_MEDIAN_CONTEXT",
                statement_type="SLOPE_MEDIAN_CONTEXT",
                obs=slope,
                extra_evidence=[geometry_hash],
            )
        )
    road = obs.get("OBS_ROAD")
    if road and road.get("evidence_state") == "SOURCE_UNAVAILABLE":
        rows.append(
            _statement(
                statement_id="MOVE_ROAD_BOUNDARY_RELATIONSHIP",
                statement_type="ROAD_BOUNDARY_RELATIONSHIP",
                obs=road,
                extra_evidence=[geometry_hash],
                qualifiers=["NOT_OBTAINED"],
            )
        )
    elif _obs_usable(road):
        try:
            distance = float(road.get("value"))
        except (TypeError, ValueError):
            distance = None
        qualifier = "TOUCHES_BOUNDARY" if distance == 0 else "NEARBY_NOT_TOUCHING"
        rows.append(
            _statement(
                statement_id="MOVE_ROAD_BOUNDARY_RELATIONSHIP",
                statement_type="ROAD_BOUNDARY_RELATIONSHIP",
                obs=road,
                extra_evidence=[geometry_hash],
                qualifiers=[qualifier],
            )
        )
    labels = derive_movement_labels(packet, unified_output, geometry_hash=geometry_hash)
    shape_obs = area or slope or road
    if labels["compactness"]:
        rows.append(
            _statement(
                statement_id="MOVE_PARCEL_COMPACTNESS",
                statement_type="PARCEL_COMPACTNESS",
                obs=shape_obs,
                extra_evidence=[geometry_hash],
                qualifiers=[labels["compactness"]],
                evidence_state="PARCEL_DERIVED",
            )
        )
    if labels["fragmentation"]:
        rows.append(
            _statement(
                statement_id="MOVE_PARCEL_FRAGMENTATION",
                statement_type="PARCEL_FRAGMENTATION",
                obs=shape_obs,
                extra_evidence=[geometry_hash],
                qualifiers=[labels["fragmentation"]],
                evidence_state="PARCEL_DERIVED",
            )
        )
    if labels["drawable_water_distribution"]:
        rows.append(
            _statement(
                statement_id="MOVE_DRAWABLE_WATER_DISTRIBUTION",
                statement_type="DRAWABLE_WATER_DISTRIBUTION",
                obs=obs.get("OBS_WATER_COUNT") or shape_obs,
                extra_evidence=[geometry_hash],
                object_refs=list(labels["drawable_object_refs"] or []),
                qualifiers=[labels["drawable_water_distribution"]],
                evidence_state="PARCEL_DERIVED",
            )
        )
    return rows


def domain_attention_order(packet: Mapping[str, Any], available: list[str]) -> list[str]:
    """Theme order from bottleneck rank. Does not change action execution order."""
    order: list[str] = []
    bottlenecks = sorted(
        packet.get("bottlenecks") or [],
        key=lambda row: int(row.get("bottleneck_rank") or 0),
    )
    for row in bottlenecks:
        domain = BOTTLENECK_TO_DOMAIN.get(str(row.get("bottleneck_id") or ""))
        if domain in available and domain not in order:
            order.append(domain)
    for domain in ATTENTION_FALLBACK:
        if domain in available and domain not in order:
            order.append(domain)
    return order


def _refuse_cper(packet: Mapping[str, Any], unified_output: Mapping[str, Any]) -> None:
    policy = str((packet.get("technical_references") or {}).get("policy") or "")
    scope = str((packet.get("technical_references") or {}).get("policy_scope") or "")
    parcel = packet.get("parcel") or {}
    if (
        is_cper_engineering_fixture(unified_output)
        or parcel.get("is_engineering_test_geometry")
        or scope == "CPER_FIXTURE_ONLY"
        or policy == "build_cper_demo_policy"
    ):
        raise OperatingProfileError(
            "CPER_POLICY_ON_GENERIC_PROFILE",
            "Generic Operating Profile refuses CPER fixture policy",
        )


def profile_hash(profile: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in profile.items() if key != "profile_hash"}
    return sha256_canonical(payload)


def project_livestock_operating_profile(
    packet: Mapping[str, Any],
    unified_output: Mapping[str, Any],
    *,
    species_lens: str = "CATTLE",
) -> dict[str, Any]:
    """Project Feed/Drink/Move statements. Cattle only until Sheep Lens ships."""
    if species_lens != "CATTLE":
        raise OperatingProfileError("SPECIES_LENS_NOT_IN_PHASE_1", species_lens)
    _refuse_cper(packet, unified_output)
    obs = _obs_index(packet)
    parcel = packet.get("parcel") or {}
    geometry_hash = str(parcel.get("geometry_hash") or "")
    if len(geometry_hash) != 64:
        raise OperatingProfileError("GEOMETRY_HASH_REQUIRED", "confirmed geometry_hash is required")
    feed = _project_feed(obs)
    drink = _project_drink(packet, obs)
    move = _project_move(packet, obs, unified_output, geometry_hash)
    buckets = {"feed": feed, "drink": drink, "move": move}
    domains = {key: {"statements": rows} for key, rows in buckets.items() if rows}
    available = [name for name in POPULATED_DOMAINS if name.lower() in domains]
    actions = list(packet.get("actions") or [])
    execution = [
        str(row.get("action_id"))
        for row in sorted(actions, key=lambda item: int(item.get("execution_order") or 0))
        if row.get("action_id")
    ]
    thesis = [
        row["statement_id"]
        for name in available
        for row in domains[name.lower()]["statements"]
        if row.get("narrative_role") == PORTRAIT_INPUT
    ]
    profile: dict[str, Any] = {
        "schema_version": PROFILE_SCHEMA,
        "packet_hash": packet_hash(dict(packet)),
        "unified_output_hash": sha256_canonical(unified_output),
        "parcel_ref": {
            "parcel_id": parcel.get("parcel_id"),
            "geometry_id": parcel.get("geometry_id") or parcel.get("parcel_id"),
            "geometry_hash": geometry_hash,
            "confirmation_status": parcel.get("confirmation_status"),
            "policy_scope": (packet.get("technical_references") or {}).get("policy_scope"),
            "is_engineering_test_geometry": bool(parcel.get("is_engineering_test_geometry")),
        },
        "species_lens": "CATTLE",
        "available_domains": available,
        "operating_domains": domains,
        "operating_thesis_inputs": thesis,
        "domain_attention_order": domain_attention_order(packet, available),
        "action_execution_order": execution,
        "field_visit_purpose": derive_authoritative_visit_purpose(packet),
        "provenance": {
            "projector": PROJECTOR_ID,
            "llm_used": False,
            "policy_scope": (packet.get("technical_references") or {}).get("policy_scope"),
        },
    }
    profile["profile_hash"] = profile_hash(profile)
    violations = validate_operating_profile(profile, packet, unified_output)
    if violations:
        codes = ", ".join(row["code"] for row in violations)
        raise OperatingProfileError("PROFILE_INVALID", codes)
    return profile


def profile_for_llm(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Workbench slice: populated domains, including guardrails. Thesis is portrait-only."""
    domains: dict[str, Any] = {}
    for key, bucket in (profile.get("operating_domains") or {}).items():
        name = key.upper()
        statements = list((bucket or {}).get("statements") or [])
        if name in POPULATED_DOMAINS and statements:
            domains[key] = bucket
    present = [name for name in POPULATED_DOMAINS if name.lower() in domains]
    attention = [
        name for name in (profile.get("domain_attention_order") or []) if name in present
    ]
    thesis = [
        row["statement_id"]
        for name in present
        for row in domains[name.lower()]["statements"]
        if row.get("narrative_role") == PORTRAIT_INPUT
    ]
    return {
        "schema_version": profile.get("schema_version"),
        "profile_hash": profile.get("profile_hash"),
        "species_lens": profile.get("species_lens"),
        "available_domains": present,
        "operating_domains": domains,
        "operating_thesis_inputs": thesis,
        "domain_attention_order": attention,
        "field_visit_purpose": dict(profile.get("field_visit_purpose") or {}),
        "action_execution_order": list(profile.get("action_execution_order") or []),
    }


def _iter_statements(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket in (profile.get("operating_domains") or {}).values():
        rows.extend(list((bucket or {}).get("statements") or []))
    return rows


def _numeric_leak(profile: Mapping[str, Any], packet: Mapping[str, Any]) -> list[str]:
    leaks: list[str] = []
    for statement in _iter_statements(profile):
        for key in _FORBIDDEN_NUMBER_KEYS:
            if key in statement:
                leaks.append(str(statement.get("statement_id")))
        inspect = {
            key: value
            for key, value in statement.items()
            if key not in {"value_refs", "evidence_refs", "object_refs", "statement_id"}
        }
        blob = canonical_dumps(inspect)
        for row in packet.get("observations") or []:
            value = row.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            token = format(value, ".10g")
            if len(token) >= 4 and token in blob:
                leaks.append(str(row.get("observation_id")))
    return leaks


def validate_operating_profile(
    profile: Mapping[str, Any],
    packet: Mapping[str, Any],
    unified_output: Mapping[str, Any],
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []

    def add(code: str, message: str) -> None:
        violations.append({"code": code, "message": message})

    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    for err in sorted(
        Draft202012Validator(schema).iter_errors(dict(profile)),
        key=lambda item: list(item.absolute_path),
    ):
        path = ".".join(str(part) for part in err.absolute_path) or "$"
        add("PROFILE_SCHEMA_INVALID", f"{path}: {err.message}")

    for key in ("packet_hash", "unified_output_hash", "profile_hash"):
        if not profile.get(key):
            add("PROFILE_HASH_MISSING", key)
    if profile.get("packet_hash") != packet_hash(dict(packet)):
        add("PACKET_HASH_MISMATCH", "profile.packet_hash does not match packet")
    if profile.get("unified_output_hash") != sha256_canonical(unified_output):
        add("UNIFIED_OUTPUT_HASH_MISMATCH", "profile.unified_output_hash does not match UO")
    if profile.get("profile_hash") != profile_hash(profile):
        add("PROFILE_HASH_MISMATCH", "profile_hash is stale")
    if profile.get("provenance", {}).get("llm_used"):
        add("LLM_IN_PROJECTOR", "Operating Profile must be deterministic")
    if (profile.get("parcel_ref") or {}).get("is_engineering_test_geometry"):
        add("CPER_POLICY_ON_GENERIC_PROFILE", "engineering test geometry")
    if (profile.get("provenance") or {}).get("policy_scope") == "CPER_FIXTURE_ONLY":
        add("CPER_POLICY_ON_GENERIC_PROFILE", "CPER_FIXTURE_ONLY")

    parcel = packet.get("parcel") or {}
    tech = packet.get("technical_references") or {}
    pref = profile.get("parcel_ref") or {}
    if pref.get("geometry_hash") != parcel.get("geometry_hash"):
        add("PARCEL_REF_MISMATCH", "parcel_ref.geometry_hash")
    if pref.get("parcel_id") != parcel.get("parcel_id"):
        add("PARCEL_REF_MISMATCH", "parcel_ref.parcel_id")
    if pref.get("confirmation_status") != parcel.get("confirmation_status"):
        add("CONFIRMATION_STATUS_MISMATCH", str(pref.get("confirmation_status")))
    if pref.get("policy_scope") != tech.get("policy_scope"):
        add("POLICY_SCOPE_MISMATCH", str(pref.get("policy_scope")))

    obs = _obs_index(packet)
    objects = {
        str(row.get("candidate_id"))
        for row in (packet.get("candidate_objects") or [])
        if row.get("candidate_id")
    }
    drawable_ids = set(_drawable_ids(packet))
    geometry_hash = str(parcel.get("geometry_hash") or "")
    seen_ids: set[str] = set()
    available = list(profile.get("available_domains") or [])
    expected_attention = domain_attention_order(packet, available)
    if list(profile.get("domain_attention_order") or []) != expected_attention:
        add("ATTENTION_ORDER_MISMATCH", "domain_attention_order must follow bottleneck rank")
    for domain in profile.get("domain_attention_order") or []:
        if domain not in available:
            add("ATTENTION_EMPTY_DOMAIN", str(domain))
    for domain in ("contain", "manage"):
        if domain in (profile.get("operating_domains") or {}):
            add("EMPTY_DOMAIN_PRESENT", domain)

    for key, bucket in (profile.get("operating_domains") or {}).items():
        expected = key.upper()
        if expected not in POPULATED_DOMAINS:
            add("UNKNOWN_DOMAIN", key)
            continue
        statements = list((bucket or {}).get("statements") or [])
        if not statements and expected in available:
            add("AVAILABLE_DOMAIN_EMPTY", expected)
        if statements and expected not in available:
            add("POPULATED_DOMAIN_NOT_AVAILABLE", expected)
        for row in statements:
            sid = str(row.get("statement_id") or "")
            stype = str(row.get("statement_type") or "")
            if sid in seen_ids:
                add("DUPLICATE_STATEMENT_ID", sid)
            seen_ids.add(sid)
            if row.get("domain") != expected:
                add("STATEMENT_DOMAIN_MISMATCH", f"{sid} in {key}")
            type_domain = STATEMENT_TYPE_DOMAIN.get(stype)
            if type_domain and (
                row.get("domain") != type_domain or expected != type_domain
            ):
                add("STATEMENT_TYPE_DOMAIN_MISMATCH", f"{sid}:{stype}")
            expected_role = STATEMENT_NARRATIVE_ROLE.get(stype)
            if expected_role and row.get("narrative_role") != expected_role:
                add("NARRATIVE_ROLE_MISMATCH", sid)
            if expected_role == PORTRAIT_INPUT and not row.get("displayable"):
                add("NARRATIVE_ROLE_MISMATCH", f"{sid}:portrait_not_displayable")
            if expected_role in {GUARDRAIL_ONLY, ACTION_INPUT} and row.get("displayable"):
                add("NARRATIVE_ROLE_MISMATCH", f"{sid}:guardrail_displayable")
            policy = STATEMENT_INFERENCE_POLICY.get(stype)
            allowed = list(row.get("allowed_inferences") or [])
            prohibited = list(row.get("prohibited_inferences") or [])
            if set(allowed) & set(prohibited):
                add("ALLOWED_PROHIBITED_OVERLAP", sid)
            if set(allowed) & DANGEROUS_INFERENCES:
                add("DANGEROUS_INFERENCE_ALLOWED", sid)
            if policy:
                if set(allowed) != set(policy["allowed"]) or set(prohibited) != set(
                    policy["prohibited"]
                ):
                    add("STATEMENT_INFERENCE_POLICY_MISMATCH", sid)
            refs = list(row.get("evidence_refs") or [])
            if not refs:
                add("STATEMENT_EVIDENCE_MISSING", sid)
            for ref in refs:
                if ref in obs or ref in objects or ref == geometry_hash:
                    continue
                add("STATEMENT_EVIDENCE_UNKNOWN", f"{sid}:{ref}")
            if expected == DOMAIN_MOVE and geometry_hash and geometry_hash not in refs:
                add("MOVE_GEOMETRY_HASH_MISSING", sid)
            for ref in row.get("value_refs") or []:
                if ref not in obs:
                    add("VALUE_REF_UNKNOWN", f"{sid}:{ref}")
            for ref in row.get("object_refs") or []:
                if ref not in objects:
                    add("OBJECT_REF_UNKNOWN", f"{sid}:{ref}")

    for tid in profile.get("operating_thesis_inputs") or []:
        if tid not in seen_ids:
            add("THESIS_INPUT_UNKNOWN", str(tid))
        else:
            match = next((row for row in _iter_statements(profile) if row.get("statement_id") == tid), None)
            if match and match.get("narrative_role") != PORTRAIT_INPUT:
                add("THESIS_INPUT_UNKNOWN", f"{tid}:not_portrait")

    packet_order = [
        str(row.get("action_id"))
        for row in sorted(
            packet.get("actions") or [],
            key=lambda item: int(item.get("execution_order") or 0),
        )
        if row.get("action_id")
    ]
    if list(profile.get("action_execution_order") or []) != packet_order:
        add("ACTION_ORDER_MISMATCH", "profile action order must copy Packet")

    visit = profile.get("field_visit_purpose") or {}
    expected_visit = derive_authoritative_visit_purpose(packet)
    if visit.get("visit_state") != expected_visit.get("visit_state"):
        add("VISIT_STATE_MISMATCH", str(visit.get("visit_state")))
    if visit.get("purpose_type") != expected_visit.get("purpose_type"):
        add("VISIT_STATE_MISMATCH", str(visit.get("purpose_type")))
    if visit.get("object_refs") and visit.get("purpose_type") in {
        "WATER_INVENTORY_AFTER_ACCESS_DOCUMENT",
        "NO_DEFINED_VISIT_PURPOSE",
        "CONFIRM_PARCEL",
    }:
        add("VISIT_PIN_WITHOUT_DRAWABLE", str(visit.get("purpose_type")))
    for ref in visit.get("object_refs") or []:
        if ref not in objects:
            add("OBJECT_REF_UNKNOWN", f"visit:{ref}")
        elif ref not in drawable_ids:
            add("VISIT_OBJECT_NOT_DRAWABLE", str(ref))

    for obs_id in _numeric_leak(profile, packet):
        add("HAND_COPIED_NUMBER", obs_id)

    return violations
