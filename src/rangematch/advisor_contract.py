"""Acceptance checks for the three-page Advisor workflow contract.

Rejects packets and briefs that would feed the LLM a disconnected graph,
a stale hash, invented pins, or kitchen vocabulary on buyer pages.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

KITCHEN_LEAK = re.compile(
    r"\b(F0[1-8]|HOLD|COVERAGE_UNQUANTIFIED|VAR_F\d|ranking_effect|geometry_hash)\b",
    re.I,
)
EXACT_PIN_LANGUAGE = re.compile(
    r"\b(go to this point|walk these two points|exact pin|gps pin)\b",
    re.I,
)
SOURCE_CANDIDATE_ID = re.compile(r"USGS_NHDPLUS_HR:[A-Za-z]+:[0-9]+")
SUITABILITY = re.compile(
    r"\b(suitable|unsuitable|carrying capacity|stocking rate|buy this|worth flying to)\b",
    re.I,
)
ABSENCE_INVENTORY = re.compile(
    r"\bwe (did not|didn't|could not) (find|verify|locate)\b",
    re.I,
)
ZERO_WATER_INFERENCE = re.compile(
    r"\b(no water|there is no water|没有水|地上没有水|no mapped water means)\b",
    re.I,
)
MAP_PLACEMENT_LANGUAGE = re.compile(
    r"(on the report map|地图标出|mapped water feature areas)",
    re.I,
)


def canonical_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def packet_hash(packet: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_dumps(packet).encode("utf-8")).hexdigest()


class DuplicateLandFactId(ValueError):
    """Two Land Facts share a variable_id; last-write-wins is forbidden."""


class PacketSourceUnavailable(RuntimeError):
    """Canonical Unified Output Land Facts cannot be loaded."""


def land_fact_index(unified_output: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for factor in (unified_output.get("factors") or {}).values():
        if not isinstance(factor, dict):
            continue
        for fact in factor.get("land_facts") or []:
            if not isinstance(fact, dict) or not fact.get("variable_id"):
                continue
            variable_id = str(fact["variable_id"])
            if variable_id in index:
                raise DuplicateLandFactId(
                    f"duplicate Land Fact ID {variable_id}; last-write-wins is forbidden"
                )
            index[variable_id] = fact
    return index


def load_land_facts_for_packet(
    packet: dict[str, Any], *, repo_root: Path | None = None
) -> dict[str, dict[str, Any]]:
    ref = (packet.get("technical_references") or {}).get("unified_output")
    if not ref:
        raise PacketSourceUnavailable("technical_references.unified_output is missing")
    path = Path(ref)
    if not path.is_absolute():
        path = (repo_root or REPO_ROOT) / ref
    if not path.is_file():
        raise PacketSourceUnavailable(f"Unified Output is not available at {path}")
    facts = land_fact_index(json.loads(path.read_text(encoding="utf-8")))
    if not facts:
        raise PacketSourceUnavailable(f"Unified Output at {path} has no Land Facts")
    return facts


def _page_one_text(brief: dict[str, Any]) -> str:
    page = brief.get("page_one_advisor") or {}
    chunks = [
        page.get("how_the_tract_reads") or "",
        page.get("visit_guidance") or "",
        page.get("what_changes_next") or "",
        *list(page.get("listing_outruns_evidence") or []),
        *list(page.get("do_today") or []),
        *list(page.get("what_not_to_recheck") or []),
    ]
    return "\n".join(str(x) for x in chunks)


def _page_two_text(brief: dict[str, Any]) -> str:
    messages = ((brief.get("page_two_actions") or {}).get("messages")) or []
    return "\n".join(str(m.get("body") or "") for m in messages)


def _ids(rows: list[Any], key: str) -> set[str]:
    return {str(row.get(key)) for row in rows if isinstance(row, dict) and row.get(key)}


def _is_cper_fixture_packet(packet: dict[str, Any]) -> bool:
    parcel = packet.get("parcel") or {}
    parcel_id = str(parcel.get("parcel_id") or "")
    return bool(parcel.get("is_engineering_test_geometry")) and (
        "ENGINEERING_TEST_GEOMETRY_CPER" in parcel_id
    )


def has_drawable_geometry(geometry: dict[str, Any] | None) -> bool:
    """True only when a bbox, centroid, or explicit geometry reference can be drawn."""
    geometry = geometry or {}
    bbox = geometry.get("bbox")
    if isinstance(bbox, list) and len(bbox) >= 4:
        return True
    centroid = geometry.get("centroid")
    if isinstance(centroid, list) and len(centroid) >= 2:
        return True
    return bool(geometry.get("geometry_ref") or geometry.get("coordinates"))


def drawable_objects(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in objects if has_drawable_geometry(row.get("geometry") or {})]


def _require_sequence(values: list[int], *, code: str, label: str) -> dict[str, str] | None:
    expected = list(range(1, len(values) + 1))
    if values != expected:
        return {
            "code": code,
            "message": f"{label} must be exactly {expected} in order, got {values}",
        }
    return None


def _add(violations: list[dict[str, str]], code: str, message: str) -> None:
    violations.append({"code": code, "message": message})


def validate_packet(
    packet: dict[str, Any],
    *,
    land_facts: dict[str, dict[str, Any]] | None = None,
    repo_root: Path | None = None,
) -> list[dict[str, str]]:
    """Return violation dicts; empty means the packet may feed the LLM."""
    violations: list[dict[str, str]] = []
    if packet.get("schema_version") != "RANGEMATCH_BUYER_EVIDENCE_PACKET@0.1.0":
        _add(violations, "PACKET_SCHEMA", "unexpected packet schema_version")

    parcel = packet.get("parcel") or {}
    if parcel.get("confirmation_status") != "CONFIRMED":
        _add(violations, "PARCEL_UNCONFIRMED", "full brief requires a confirmed parcel")

    if land_facts is not None:
        facts = land_facts
    else:
        try:
            facts = load_land_facts_for_packet(packet, repo_root=repo_root)
        except PacketSourceUnavailable as exc:
            _add(violations, "PACKET_SOURCE_UNAVAILABLE", str(exc))
            return violations
        except DuplicateLandFactId as exc:
            _add(violations, "DUPLICATE_LAND_FACT_ID", str(exc))
            return violations

    refs = packet.get("technical_references") or {}
    if not _is_cper_fixture_packet(packet) and (
        refs.get("policy_scope") == "CPER_FIXTURE_ONLY"
        or refs.get("policy") == "build_cper_demo_policy"
    ):
        _add(
            violations,
            "CPER_POLICY_ON_REAL_PARCEL",
            "CPER demo policy cannot enter a real-listing packet",
        )
    observations = list(packet.get("observations") or [])
    claims = list(packet.get("listing_claims") or [])
    objects = list(packet.get("candidate_objects") or [])
    bottlenecks = list(packet.get("bottlenecks") or [])
    actions = list(packet.get("actions") or [])
    gaps = list(packet.get("claim_evidence_gaps") or [])
    specs = list(packet.get("copy_ready_message_specs") or [])

    if len(bottlenecks) > 3:
        _add(violations, "TOO_MANY_BOTTLENECKS", "more than three bottlenecks")
    if len(actions) > 3:
        _add(violations, "TOO_MANY_ACTIONS", "more than three actions")

    observation_ids = _ids(observations, "observation_id")
    claim_ids = _ids(claims, "claim_id")
    candidate_ids = _ids(objects, "candidate_id")
    action_ids = _ids(actions, "action_id")
    message_ids = _ids(specs, "message_id")

    ranks = [int(row.get("bottleneck_rank") or 0) for row in bottlenecks]
    orders = [int(row.get("execution_order") or 0) for row in actions]
    rank_issue = _require_sequence(ranks, code="BOTTLENECK_RANK_SEQUENCE", label="bottleneck_rank")
    if rank_issue:
        violations.append(rank_issue)
    order_issue = _require_sequence(orders, code="ACTION_ORDER_SEQUENCE", label="execution_order")
    if order_issue:
        violations.append(order_issue)

    for obs in observations:
        ref = obs.get("land_fact_ref")
        if not ref:
            _add(violations, "LAND_FACT_REF_MISSING", f"{obs.get('observation_id')} has no land_fact_ref")
            continue
        if facts is not None and ref not in facts:
            _add(violations, "LAND_FACT_REF_UNKNOWN", f"{ref} is not in Unified Output")
            continue
        if facts is not None:
            expected = facts[ref].get("value")
            if obs.get("value") != expected:
                _add(
                    violations,
                    "LAND_FACT_VALUE_MISMATCH",
                    f"{ref} packet value {obs.get('value')!r} != canonical {expected!r}",
                )
            unit = facts[ref].get("unit")
            if unit is not None and obs.get("unit") != unit:
                _add(violations, "LAND_FACT_UNIT_MISMATCH", f"{ref} unit {obs.get('unit')!r} != {unit!r}")
            fact_hash = facts[ref].get("geometry_hash")
            parcel_hash = parcel.get("geometry_hash")
            if fact_hash and fact_hash != parcel_hash:
                _add(
                    violations,
                    "GEOMETRY_HASH_MISMATCH",
                    f"{ref} geometry_hash {fact_hash!r} != parcel {parcel_hash!r}",
                )

    for action in actions:
        cid = action.get("candidate_id")
        if str(cid or "").startswith("WATER_CANDIDATE"):
            _add(violations, "MINTED_CANDIDATE_ID", "do not mint WATER_CANDIDATE_* ids")
        if action.get("specificity") == "OBJECT_LEVEL":
            if not cid or cid not in candidate_ids:
                _add(
                    violations,
                    "OBJECT_ACTION_WITHOUT_OBJECT",
                    f"{action.get('action_id')} is OBJECT_LEVEL without a packet object",
                )
            else:
                obj = next(row for row in objects if row.get("candidate_id") == cid)
                if not obj.get("source_feature_id"):
                    _add(
                        violations,
                        "OBJECT_ACTION_MISSING_SOURCE_FEATURE_ID",
                        f"{action.get('action_id')} cannot be object-level without source_feature_id",
                    )
                _check_action_navigation(action, obj, violations)
        elif cid:
            _add(
                violations,
                "CATEGORY_ACTION_HAS_OBJECT",
                f"{action.get('action_id')} is category-level but sets candidate_id",
            )

    for bottleneck in bottlenecks:
        for oid in bottleneck.get("supporting_observation_ids") or []:
            if oid not in observation_ids:
                _add(violations, "DANGLING_OBSERVATION_REF", f"{bottleneck.get('bottleneck_id')} → {oid}")
        for cid in bottleneck.get("affected_candidate_ids") or []:
            if cid not in candidate_ids:
                _add(violations, "DANGLING_CANDIDATE_REF", f"{bottleneck.get('bottleneck_id')} → {cid}")
        for aid in bottleneck.get("next_action_ids") or []:
            if aid not in action_ids:
                _add(violations, "DANGLING_ACTION_REF", f"{bottleneck.get('bottleneck_id')} → {aid}")

    for gap in gaps:
        if gap.get("claim_id") not in claim_ids:
            _add(violations, "DANGLING_CLAIM_REF", f"gap → {gap.get('claim_id')}")
        action_id = gap.get("recommended_action_id")
        if action_id and action_id not in action_ids:
            _add(violations, "DANGLING_GAP_ACTION", f"{gap.get('claim_id')} → {action_id}")
        message_id = gap.get("recommended_message_id")
        if message_id and message_id not in message_ids:
            _add(violations, "DANGLING_GAP_MESSAGE", f"{gap.get('claim_id')} → {message_id}")

    declared_count = (packet.get("technical_references") or {}).get(
        "candidate_object_count_in_packet"
    )
    if declared_count is not None and int(declared_count) != len(objects):
        _add(
            violations,
            "CANDIDATE_COUNT_MISMATCH",
            f"declared {declared_count} candidate objects, packet has {len(objects)}",
        )
    water_obs = next(
        (row for row in observations if row.get("observation_id") == "OBS_WATER_COUNT"),
        None,
    )
    if objects and water_obs is not None and water_obs.get("value") != len(objects):
        _add(
            violations,
            "CANDIDATE_COUNT_MISMATCH",
            f"OBS_WATER_COUNT={water_obs.get('value')} but {len(objects)} objects",
        )
    for obj in objects:
        geometry = obj.get("geometry") or {}
        if geometry.get("centroid") is not None and geometry.get("field_navigation_precision") == "EXACT":
            _add(
                violations,
                "CENTROID_PROMOTED_TO_PIN",
                f"{obj.get('candidate_id')} centroid must not become EXACT",
            )
        drawable = has_drawable_geometry(geometry)
        precision = geometry.get("field_navigation_precision")
        if obj.get("candidate_type") == "FLOWLINE" and geometry.get("kind") != "LINE":
            _add(
                violations,
                "FLOWLINE_MUST_BE_AREA",
                f"{obj.get('candidate_id')} must be LINE",
            )
        if obj.get("candidate_type") == "WATERBODY" and geometry.get("kind") != "BBOX":
            _add(
                violations,
                "WATERBODY_MUST_BE_BBOX_AREA",
                f"{obj.get('candidate_id')} must be BBOX",
            )
        if precision not in {"AREA_ONLY", "NOT_NAVIGABLE", "APPROXIMATE", "EXACT"}:
            _add(
                violations,
                "NAVIGATION_PRECISION_UNKNOWN",
                f"{obj.get('candidate_id')} has unknown field_navigation_precision",
            )
        if drawable and precision == "NOT_NAVIGABLE":
            _add(
                violations,
                "DRAWABLE_MARKED_NOT_NAVIGABLE",
                f"{obj.get('candidate_id')} has drawable geometry and cannot be NOT_NAVIGABLE",
            )
        if not drawable and precision == "AREA_ONLY":
            _add(
                violations,
                "AREA_ONLY_WITHOUT_GEOMETRY",
                f"{obj.get('candidate_id')} is AREA_ONLY but has nothing to draw",
            )
        elif not drawable and precision not in {None, "NOT_NAVIGABLE"}:
            _add(
                violations,
                "EMPTY_GEOMETRY_MUST_BE_NOT_NAVIGABLE",
                f"{obj.get('candidate_id')} has no drawable geometry and must be NOT_NAVIGABLE",
            )
        feature_id = obj.get("source_feature_id")
        layer = obj.get("source_feature_type")
        if feature_id and layer:
            expected = f"USGS_NHDPLUS_HR:{layer}:{feature_id}"
            if obj.get("candidate_id") != expected:
                _add(
                    violations,
                    "CANDIDATE_ID_DRIFT",
                    f"{obj.get('candidate_id')} != {expected}",
                )

    for spec in specs:
        if spec.get("bound_action_id") not in action_ids:
            _add(violations, "MESSAGE_UNBOUND_ACTION", f"{spec.get('message_id')} is not bound to a packet action")
        claim_id = spec.get("bound_claim_id")
        if claim_id and claim_id not in claim_ids:
            _add(violations, "MESSAGE_UNBOUND_CLAIM", f"{spec.get('message_id')} → {claim_id}")

    policy = packet.get("action_policy")
    if not isinstance(policy, dict):
        _add(violations, "ACTION_POLICY_MISSING", "packet requires action_policy")
    else:
        first = [str(item) for item in (policy.get("allowed_first_actions") or [])]
        if not first:
            _add(violations, "ALLOWED_FIRST_ACTIONS_EMPTY", "allowed_first_actions is required")
        for action_id in first:
            if action_id not in action_ids:
                _add(violations, "ALLOWED_FIRST_UNKNOWN", action_id)
        deps = policy.get("action_dependencies") or {}
        if not isinstance(deps, dict):
            _add(violations, "ACTION_DEPENDENCIES_INVALID", "action_dependencies must be an object")
        else:
            for child, parents in deps.items():
                if child not in action_ids:
                    _add(violations, "ACTION_DEPENDENCY_UNKNOWN", str(child))
                for parent in parents or []:
                    if parent not in action_ids:
                        _add(violations, "ACTION_DEPENDENCY_UNKNOWN", str(parent))

    return violations


def _check_action_navigation(
    action: dict[str, Any], obj: dict[str, Any], violations: list[dict[str, str]]
) -> None:
    geometry = obj.get("geometry") or {}
    precision = geometry.get("field_navigation_precision")
    kind = geometry.get("kind")
    if precision == "NOT_NAVIGABLE":
        _add(
            violations,
            "NAVIGATION_NOT_ALLOWED",
            f"{action.get('action_id')} cannot navigate {obj.get('candidate_id')}",
        )
    if precision == "EXACT" and kind != "POINT":
        _add(
            violations,
            "EXACT_PRECISION_NOT_POINT",
            f"{obj.get('candidate_id')} is {kind} and cannot be EXACT",
        )


def _mentions_unbound_object(text: str, objects: list[dict[str, Any]], bound_id: str | None) -> bool:
    lowered = text.lower()
    for obj in objects:
        cid = str(obj.get("candidate_id") or "")
        name = str(obj.get("display_name") or "").strip()
        if cid and cid != bound_id and cid in text:
            return True
        if name and cid != bound_id and name.lower() in lowered:
            return True
    return False


def _navigation_language_violations(
    text: str,
    *,
    objects: list[dict[str, Any]],
    action: dict[str, Any] | None,
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    mentioned_ids = SOURCE_CANDIDATE_ID.findall(text)
    bound_id = (action or {}).get("candidate_id")
    specificity = (action or {}).get("specificity")
    if specificity != "OBJECT_LEVEL":
        if not objects and (
            EXACT_PIN_LANGUAGE.search(text)
            or re.search(r"\blittle owl creek\b", text, re.I)
            or mentioned_ids
        ):
            _add(
                violations,
                "INVENTED_PIN_OR_NAME",
                "no candidate objects in packet; brief must stay category-level",
            )
        elif objects and (
            EXACT_PIN_LANGUAGE.search(text)
            or mentioned_ids
            or _mentions_unbound_object(text, objects, None)
        ):
            _add(
                violations,
                "CATEGORY_MESSAGE_NAMES_OBJECT",
                "category-level copy may not name a candidate object or pin",
            )
        return violations

    bound = next((row for row in objects if row.get("candidate_id") == bound_id), None)
    if bound:
        geometry = bound.get("geometry") or {}
        precision = geometry.get("field_navigation_precision")
        kind = geometry.get("kind")
        if precision in {"AREA_ONLY", "APPROXIMATE", "NOT_NAVIGABLE"} and EXACT_PIN_LANGUAGE.search(
            text
        ):
            _add(
                violations,
                "PIN_LANGUAGE_FOR_AREA_GEOMETRY",
                f"{bound.get('candidate_id')} is {kind}/{precision}; exact-pin language is forbidden",
            )
        for mid in mentioned_ids:
            if mid != bound_id:
                _add(
                    violations,
                    "MESSAGE_NAMES_UNBOUND_CANDIDATE",
                    f"message names {mid} but action is bound to {bound_id}",
                )
        if _mentions_unbound_object(text, objects, bound_id):
            _add(
                violations,
                "MESSAGE_NAMES_UNBOUND_CANDIDATE",
                "message names a candidate that is not the bound action target",
            )
    elif EXACT_PIN_LANGUAGE.search(text) or mentioned_ids:
        _add(
            violations,
            "PIN_LANGUAGE_WITHOUT_BOUND_OBJECT",
            "exact-pin or named-object language requires a bound candidate",
        )
    return violations


def validate_three_page(
    brief: dict[str, Any],
    packet: dict[str, Any],
    *,
    land_facts: dict[str, dict[str, Any]] | None = None,
    repo_root: Path | None = None,
) -> list[dict[str, str]]:
    """Page-one / page-two / page-three acceptance for the Advisor Brief."""
    violations: list[dict[str, str]] = []
    if brief.get("schema_version") != "RANGEMATCH_ADVISOR_THREE_PAGE@0.1.0":
        _add(violations, "BRIEF_SCHEMA", "unexpected brief schema_version")

    expected_hash = packet_hash(packet)
    if brief.get("packet_hash") != expected_hash:
        _add(
            violations,
            "PACKET_HASH_MISMATCH",
            "brief.packet_hash does not match the canonical packet hash",
        )

    kitchen = brief.get("page_three_kitchen") or {}
    appendix = kitchen.get("engine_appendix") or {}
    uo_ref = kitchen.get("unified_output_ref") or appendix.get("unified_output_ref")
    packet_uo = (packet.get("technical_references") or {}).get("unified_output")
    if uo_ref and packet_uo and uo_ref != packet_uo:
        _add(violations, "UNIFIED_OUTPUT_REF_MISMATCH", "page three points at a different Unified Output")
    required_kitchen = (
        "parcel_summary",
        "map_layers",
        "observations",
        "candidate_objects",
        "source_notes",
        "coverage_and_limitations",
        "engine_appendix",
        "validation_record",
    )
    missing_kitchen = [key for key in required_kitchen if key not in kitchen]
    if missing_kitchen:
        _add(
            violations,
            "PAGE_THREE_INCOMPLETE",
            "page three is missing " + ", ".join(missing_kitchen),
        )
    objects = list(packet.get("candidate_objects") or [])
    if objects and not kitchen.get("candidate_objects"):
        _add(
            violations,
            "PAGE_THREE_INCOMPLETE",
            "page three must keep candidate objects in the kitchen inventory",
        )

    page1 = _page_one_text(brief)
    page2 = _page_two_text(brief)
    visible = f"{page1}\n{page2}"
    if KITCHEN_LEAK.search(page1) or KITCHEN_LEAK.search(page2):
        _add(violations, "KITCHEN_ON_BUYER_PAGES", "Factor IDs, HOLD, or coverage enums leaked onto pages 1–2")
    if SUITABILITY.search(visible):
        _add(violations, "SUITABILITY_OR_TRIP_VERDICT", "buyer pages contain suitability, stocking, or 'worth flying to'")
    if ABSENCE_INVENTORY.search(page1):
        _add(violations, "ABSENCE_INVENTORY", "page one inventories what the scan did not find")
    visit_purpose = (brief.get("page_one_advisor") or {}).get("visit_purpose")
    if visit_purpose not in {
        "VISIT_PURPOSE_DEFINED",
        "VISIT_DEPENDS_ON_DOCUMENT",
        "NO_DEFINED_VISIT_PURPOSE_YET",
    }:
        _add(violations, "VISIT_PURPOSE_INVALID", "page one must use the three-state visit_purpose")
    if ZERO_WATER_INFERENCE.search(visible):
        _add(
            violations,
            "ZERO_WATER_INFERENCE",
            "buyer pages treat missing mapped water as no water on the ground",
        )
    kitchen_layers = list(kitchen.get("map_layers") or [])
    for layer in kitchen_layers:
        if not has_drawable_geometry(layer):
            _add(
                violations,
                "MAP_LAYER_NOT_DRAWABLE",
                f"{layer.get('layer_id')} is in map_layers without drawable geometry",
            )
        obj = next(
            (row for row in objects if row.get("candidate_id") == layer.get("layer_id")),
            None,
        )
        if obj and (obj.get("geometry") or {}).get("field_navigation_precision") == "NOT_NAVIGABLE":
            _add(
                violations,
                "MAP_LAYER_NOT_DRAWABLE",
                f"{layer.get('layer_id')} is NOT_NAVIGABLE and cannot enter map_layers",
            )
    if MAP_PLACEMENT_LANGUAGE.search(visible) and not kitchen_layers:
        _add(
            violations,
            "MAP_LANGUAGE_WITHOUT_LAYER",
            "buyer pages mention mapped water on the report map without drawable layers",
        )

    actions = {row.get("action_id"): row for row in (packet.get("actions") or [])}
    specs = {row.get("message_id"): row for row in (packet.get("copy_ready_message_specs") or [])}
    claim_ids = _ids(list(packet.get("listing_claims") or []), "claim_id")

    for message in ((brief.get("page_two_actions") or {}).get("messages")) or []:
        mid = message.get("message_id")
        if mid not in specs:
            _add(violations, "MESSAGE_ID_NOT_IN_PACKET", f"{mid} is not a packet message spec")
        bound_action = message.get("bound_action_id")
        if bound_action not in actions:
            _add(violations, "MESSAGE_UNBOUND", f"{mid} is not bound to a packet action")
        spec = specs.get(mid) or {}
        if spec and spec.get("bound_action_id") != bound_action:
            _add(violations, "MESSAGE_ACTION_MISMATCH", f"{mid} action does not match packet spec")
        claim_id = message.get("bound_claim_id")
        if claim_id and claim_id not in claim_ids:
            _add(violations, "MESSAGE_UNBOUND_CLAIM", f"{mid} → {claim_id}")
        violations.extend(
            _navigation_language_violations(
                str(message.get("body") or ""),
                objects=objects,
                action=actions.get(bound_action),
            )
        )

    violations.extend(
        _navigation_language_violations(page1, objects=objects, action=None)
    )

    hold_flag = kitchen.get("hold_confined_to_appendix")
    if hold_flag is None:
        hold_flag = appendix.get("hold_confined_to_appendix")
    if hold_flag is not True:
        _add(violations, "HOLD_NOT_IN_APPENDIX", "HOLD must stay in the technical appendix")
    page = brief.get("page_one_advisor") or {}
    if len(page.get("do_today") or []) > 2:
        _add(violations, "TOO_MANY_TODAY_ACTIONS", "page one allows at most two do_today lines")
    if len(page.get("listing_outruns_evidence") or []) > 3:
        _add(violations, "TOO_MANY_CLAIM_GAPS", "page one allows at most three claim gaps")

    violations.extend(validate_packet(packet, land_facts=land_facts, repo_root=repo_root))
    displayable = bool((brief.get("report_provenance") or {}).get("displayable"))
    status = brief.get("validation_status")
    content_codes = {row["code"] for row in violations}
    if status == "FAILED" and displayable:
        _add(violations, "DISPLAYABLE_WHILE_FAILED", "FAILED briefs must not be displayable")
    elif displayable and content_codes:
        _add(violations, "DISPLAYABLE_WITH_VIOLATIONS", "unsafe brief must not be displayable")
    if status == "PASSED" and content_codes:
        _add(violations, "STATUS_PASSED_WITH_VIOLATIONS", "validation_status is PASSED but validator found errors")
    return violations
