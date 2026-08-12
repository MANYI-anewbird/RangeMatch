"""Deterministic Unified Output → Buyer Evidence Packet projection.

Observation and F03 object projection are generic. Bottleneck/action policy
for the current fixture is CPER-demo-only and must not be treated as a
production ranker for arbitrary listings.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from rangematch.advisor_contract import has_drawable_geometry, land_fact_index

PACKET_SCHEMA = "RANGEMATCH_BUYER_EVIDENCE_PACKET@0.1.0"
UNIFIED_OUTPUT_REF = "test-data/land-profiles/unified_output_cper_001.json"
F03_INVENTORY_REF = (
    "test-data/live-results/cper/cper_f03_candidate_distance_result_2026-08-07.json"
)
F03_REMOTE_PILOT_REF = (
    "test-data/cross-parcel-validation/XPV_CPER_001/f03_remote_pilot/remote_pilot_result.json"
)

OBSERVATION_SPECS: tuple[dict[str, Any], ...] = (
    {
        "observation_id": "OBS_PRECIP",
        "variable_id": "VAR_F05_MEAN_ANNUAL_PRECIPITATION",
        "label": "Mean annual precipitation",
        "evidence_state": "MEASURED",
        "source_fallback": "NOAA_NCEI_DIRECT_CLIMATE_NORMALS_NETCDF",
        "display_value": None,
        "allowed_support": ["canonical climate lookup is complete"],
        "prohibited_support": ["climate adequacy", "drought resilience", "future performance"],
    },
    {
        "observation_id": "OBS_SLOPE",
        "variable_id": "VAR_F01_SLOPE_MEDIAN_DEGREES",
        "label": "Median slope",
        "evidence_state": "PARCEL_DERIVED",
        "source_fallback": "USGS_3DEP",
        "display_value": None,
        "allowed_support": ["gentle typical slope context"],
        "prohibited_support": ["suitability", "traversability for every animal"],
    },
    {
        "observation_id": "OBS_AREA",
        "variable_id": "VAR_F06_AREA_M2",
        "label": "Mapped geometric area",
        "evidence_state": "PARCEL_DERIVED",
        "source_fallback": "CONFIRMED_GEOMETRY",
        "display_value": None,
        "allowed_support": ["mapped outline size"],
        "prohibited_support": ["grazable acres", "fencing cost", "survey"],
    },
    {
        "observation_id": "OBS_RAP_PROD",
        "variable_id": "VAR_F02_ANNUAL_HERB_PRODUCTION",
        "label": "Modeled annual herbaceous production",
        "evidence_state": "MODELED",
        "source_fallback": "RAP_productionV3",
        "display_value": None,
        "allowed_support": ["modeled vegetation snapshot"],
        "prohibited_support": ["available forage", "carrying capacity", "ready for cattle"],
    },
    {
        "observation_id": "OBS_WATER_COUNT",
        "variable_id": "VAR_F03_MAPPED_WATER_CANDIDATE_COUNT",
        "label": "Mapped hydrography candidate count",
        "evidence_state": "MAPPED_CANDIDATE",
        "source_fallback": "USGS_NHDPLUS_HR",
        "display_value": None,
        "allowed_support": ["mapped water features exist as leads"],
        "prohibited_support": ["usable livestock water", "year-round reliability", "legal right"],
    },
    {
        "observation_id": "OBS_ROAD",
        "variable_id": "VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M",
        "label": "Nearest mapped road distance",
        "evidence_state": "MAPPED_CANDIDATE",
        "source_fallback": "US_CENSUS_TIGER_LINE_2025_ALL_ROADS",
        "display_value": None,
        "allowed_support": ["physical road contact on the map"],
        "prohibited_support": ["legal access", "usable entrance"],
    },
)

PolicyBuilder = Callable[..., dict[str, Any]]
F03_AVAILABLE = "AVAILABLE"
F03_FAILED = "FAILED"
F03_NOT_PROVIDED = "NOT_PROVIDED"


def project_observations(
    unified_output: dict[str, Any], *, f03_status: str = F03_AVAILABLE
) -> list[dict[str, Any]]:
    facts = land_fact_index(unified_output)
    observations: list[dict[str, Any]] = []
    for spec in OBSERVATION_SPECS:
        variable_id = spec["variable_id"]
        if variable_id not in facts:
            raise KeyError(f"Unified Output is missing {variable_id}")
        fact = facts[variable_id]
        evidence_state = spec["evidence_state"]
        value = fact.get("value")
        allowed = list(spec["allowed_support"])
        if spec["observation_id"] == "OBS_WATER_COUNT" and f03_status == F03_FAILED:
            evidence_state = "SOURCE_UNAVAILABLE"
            allowed = ["mapped-water inventory is currently unavailable"]
        observations.append(
            {
                "observation_id": spec["observation_id"],
                "label": spec["label"],
                "value": value,
                "display_value": spec["display_value"],
                "unit": fact.get("unit"),
                "time_period": fact.get("temporal_semantics"),
                "evidence_state": evidence_state,
                "spatial_meaning": fact.get("spatial_semantics") or "parcel_aggregate",
                "source_id": fact.get("source_id") or spec["source_fallback"],
                "land_fact_ref": variable_id,
                "allowed_support": allowed,
                "prohibited_support": list(spec["prohibited_support"]),
            }
        )
    return observations


def _remote_index(remote_pilot: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not remote_pilot:
        return {}
    sampled = {
        str(row.get("candidate_id"))
        for row in ((remote_pilot.get("selection") or {}).get("selection_keys") or [])
        if row.get("candidate_id")
    }
    index: dict[str, dict[str, Any]] = {}
    for row in remote_pilot.get("candidates") or []:
        cid = str(row.get("candidate_id") or "")
        if not cid:
            continue
        bbox = ((row.get("physical_presence") or {}).get("provenance") or {}).get(
            "bbox_wgs84_export"
        )
        index[cid] = {
            "sampled": cid in sampled,
            "after_remote_level": row.get("after_remote_level"),
            "bbox": list(bbox) if isinstance(bbox, list) else [],
            "source_feature_id": row.get("source_feature_id"),
            "gnis_name": row.get("gnis_name"),
        }
    for cid in sampled:
        index.setdefault(cid, {"sampled": True, "after_remote_level": None, "bbox": []})
        index[cid]["sampled"] = True
    return index


def project_candidate_objects(
    inventory: Mapping[str, Any] | list[dict[str, Any]],
    remote_pilot: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Project NHD candidate identity and review state. Never mints IDs or EXACT pins."""
    rows = (
        list(inventory)
        if isinstance(inventory, list)
        else list(inventory.get("candidate_inventory") or [])
    )
    remote = _remote_index(remote_pilot)
    objects: list[dict[str, Any]] = []
    for raw in rows:
        source_feature_id = raw.get("source_feature_id")
        layer = raw.get("source_layer")
        if not source_feature_id or not layer:
            continue
        candidate_id = str(raw.get("candidate_id") or f"USGS_NHDPLUS_HR:{layer}:{source_feature_id}")
        extra = remote.get(candidate_id) or {}
        after = extra.get("after_remote_level")
        if after == "REMOTELY_SUPPORTED_CANDIDATE":
            evidence_state = "REMOTELY_SUPPORTED"
        elif after == "FIELD_VERIFIED_LIVESTOCK_WATER":
            evidence_state = "MAPPED_CANDIDATE"
        else:
            evidence_state = "MAPPED_CANDIDATE"
        if str(layer).endswith("Waterbody") or str(layer) == "NHDArea":
            candidate_type, kind = "WATERBODY", "BBOX"
        else:
            candidate_type, kind = "FLOWLINE", "LINE"
        bbox = extra.get("bbox") or raw.get("bbox") or []
        centroid = extra.get("centroid") or raw.get("centroid")
        geometry = {
            "kind": kind,
            "centroid": centroid,
            "bbox": list(bbox) if isinstance(bbox, list) else [],
            "field_navigation_precision": "AREA_ONLY",
        }
        if has_drawable_geometry(geometry):
            allowed = (
                ["review this waterbody area"]
                if candidate_type == "WATERBODY"
                else ["review this flowline segment as an area"]
            )
        else:
            geometry["field_navigation_precision"] = "NOT_NAVIGABLE"
            allowed = [
                "request a usable location or build a field inventory; this mapped identity cannot be drawn"
            ]
        objects.append(
            {
                "candidate_id": candidate_id,
                "candidate_type": candidate_type,
                "source_feature_type": str(layer),
                "source_feature_id": str(source_feature_id),
                "display_name": extra.get("gnis_name") or raw.get("gnis_name"),
                "geometry": geometry,
                "parcel_relationship": {
                    "intersects": raw.get("intersects_parcel"),
                    "distance_m": None,
                    "relationship_status": "DERIVED",
                },
                "evidence_state": evidence_state,
                "review_status": "SAMPLED" if extra.get("sampled") else "UNREVIEWED",
                "legal_access_status": "NOT_VERIFIED",
                "livestock_use_status": "NOT_VERIFIED",
                "allowed_action_language": allowed,
                "prohibited_inferences": [
                    "usable livestock water",
                    "water-source point",
                    "exact pin",
                    "legal access",
                ],
            }
        )
    objects.sort(key=lambda row: str(row["candidate_id"]))
    return objects


def constrain_actions_to_objects(
    actions: list[dict[str, Any]], objects: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Demote object-level actions whose candidate is missing or has no source id."""
    by_id = {row.get("candidate_id"): row for row in objects}
    constrained: list[dict[str, Any]] = []
    for action in actions:
        item = dict(action)
        if item.get("specificity") == "OBJECT_LEVEL":
            obj = by_id.get(item.get("candidate_id"))
            precision = ((obj or {}).get("geometry") or {}).get("field_navigation_precision")
            if obj is None or not obj.get("source_feature_id") or precision == "NOT_NAVIGABLE":
                item["specificity"] = "CATEGORY_LEVEL"
                item["candidate_id"] = None
        constrained.append(item)
    return constrained


def rank_bottlenecks(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
    raise NotImplementedError(
        "generic bottleneck ranking is not a production policy; use build_cper_demo_policy"
    )


def order_actions(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
    raise NotImplementedError(
        "generic action ordering is not a production policy; use build_cper_demo_policy"
    )


def derive_claim_gaps(
    listing_claims: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Category-level gap shells. Action IDs are filled only by a named policy."""
    gaps: list[dict[str, Any]] = []
    for claim in listing_claims:
        category = claim.get("category")
        claim_id = claim.get("claim_id")
        text = claim.get("text") or ""
        if category == "LIVESTOCK_WATER":
            gaps.append(
                {
                    "claim_id": claim_id,
                    "claim": text,
                    "supported_portion": "Mapped hydrography candidates exist on the tract",
                    "unsupported_portion": [
                        "year-round reliability",
                        "livestock accessibility",
                        "capacity",
                        "quality",
                        "legal right",
                    ],
                    "risk_of_misreading": "HIGH",
                    "recommended_action_id": None,
                    "recommended_message_id": None,
                }
            )
        elif category == "LEGAL_ACCESS":
            gaps.append(
                {
                    "claim_id": claim_id,
                    "claim": text,
                    "supported_portion": "A mapped road contacts the geometry",
                    "unsupported_portion": [
                        "legal entrance",
                        "recorded easement",
                        "buyer right to use",
                    ],
                    "risk_of_misreading": "HIGH",
                    "recommended_action_id": None,
                    "recommended_message_id": None,
                }
            )
        elif category == "FORAGE_OR_PRODUCTION":
            gaps.append(
                {
                    "claim_id": claim_id,
                    "claim": text,
                    "supported_portion": "RAP returned a modeled production snapshot",
                    "unsupported_portion": [
                        "available forage",
                        "carrying capacity",
                        "ready for cattle",
                    ],
                    "risk_of_misreading": "HIGH",
                    "recommended_action_id": None,
                    "recommended_message_id": None,
                }
            )
    return gaps


def _access_action(order: int) -> dict[str, Any]:
    return {
        "action_id": "ACTION_ACCESS_DOCUMENTS",
        "execution_order": order,
        "action_type": "DOCUMENT_REQUEST",
        "specificity": "CATEGORY_LEVEL",
        "target_category": "LEGAL_ACCESS",
        "candidate_id": None,
        "suggested_executor": "buyer or buyer-side broker",
        "cost_class": "DESKTOP",
        "why_now": "Can be requested before travel; cheaper than a flight.",
        "can_establish": ["documentary basis for claimed access"],
        "cannot_establish": [
            "road condition",
            "seasonal passability",
            "final legal interpretation",
        ],
        "success_transition": "ACCESS_DOCUMENT_REVIEW",
        "failure_transition": "PROFESSIONAL_REVIEW_OR_PAUSE",
    }


def _water_action(
    order: int, *, mode: str
) -> dict[str, Any]:
    if mode == "FIELD_MAPPED":
        return {
            "action_id": "ACTION_WATER_FIELD_CATEGORY",
            "execution_order": order,
            "action_type": "FIELD_REVIEW",
            "specificity": "CATEGORY_LEVEL",
            "target_category": "LIVESTOCK_WATER",
            "candidate_id": None,
            "suggested_executor": "buyer or field representative",
            "cost_class": "FIELD_HALF_DAY",
            "why_now": "Largest operating-evidence gap; review mapped water areas, not named pins.",
            "can_establish": [
                "whether mapped water features show visible water and access signs on the visit date"
            ],
            "cannot_establish": [
                "year-round reliability",
                "water quality",
                "legal right to use",
            ],
            "success_transition": "WATER_PRESENCE_OBSERVED",
            "failure_transition": "KEEP_WATER_AS_LEAD_OR_INVENTORY",
        }
    if mode == "LOCATION_OR_INVENTORY":
        return {
            "action_id": "ACTION_WATER_LOCATION_OR_INVENTORY",
            "execution_order": order,
            "action_type": "DOCUMENT_REQUEST",
            "specificity": "CATEGORY_LEVEL",
            "target_category": "LIVESTOCK_WATER",
            "candidate_id": None,
            "suggested_executor": "buyer or buyer-side broker",
            "cost_class": "DESKTOP",
            "why_now": "Mapped identities exist but cannot be placed on a map or walked as areas.",
            "can_establish": ["a usable location or a field inventory plan"],
            "cannot_establish": [
                "usable livestock water",
                "that the ground has no water",
            ],
            "success_transition": "WATER_LOCATION_CAPTURED",
            "failure_transition": "KEEP_WATER_AS_UNLOCATED_IDENTITY",
        }
    if mode == "SOURCE_UNAVAILABLE":
        return {
            "action_id": "ACTION_WATER_SOURCE_UNAVAILABLE",
            "execution_order": order,
            "action_type": "DOCUMENT_REQUEST",
            "specificity": "CATEGORY_LEVEL",
            "target_category": "LIVESTOCK_WATER",
            "candidate_id": None,
            "suggested_executor": "buyer or buyer-side broker",
            "cost_class": "DESKTOP",
            "why_now": "Mapped-water inventory could not be loaded; ask for claimed developed sources.",
            "can_establish": ["whether the seller claims a developed water source and can locate it"],
            "cannot_establish": [
                "that the ground has no water",
                "year-round reliability",
            ],
            "success_transition": "SELLER_WATER_CLAIM_CAPTURED",
            "failure_transition": "RETRY_MAPPED_INVENTORY_OR_PAUSE",
        }
    return {
        "action_id": "ACTION_ASK_SELLER_WATER",
        "execution_order": order,
        "action_type": "DOCUMENT_REQUEST",
        "specificity": "CATEGORY_LEVEL",
        "target_category": "LIVESTOCK_WATER",
        "candidate_id": None,
        "suggested_executor": "buyer or buyer-side broker",
        "cost_class": "DESKTOP",
        "why_now": "Mapped hydrography returned no leads; ask whether a developed source is claimed.",
        "can_establish": ["whether anyone claims a well, tank, pond, or other developed source"],
        "cannot_establish": [
            "that the ground has no water",
            "year-round reliability",
        ],
        "success_transition": "SELLER_WATER_CLAIM_CAPTURED",
        "failure_transition": "CREATE_FIELD_WATER_INVENTORY",
    }


def _confirm_action() -> dict[str, Any]:
    return {
        "action_id": "ACTION_CONFIRM_PARCEL",
        "execution_order": 1,
        "action_type": "CONFIRM_PARCEL",
        "specificity": "CATEGORY_LEVEL",
        "target_category": "PARCEL_IDENTITY",
        "candidate_id": None,
        "suggested_executor": "buyer",
        "cost_class": "DESKTOP",
        "why_now": "No diligence spend is useful until the outline is confirmed.",
        "can_establish": ["buyer confirmation of the working parcel geometry"],
        "cannot_establish": ["access", "water", "forage"],
        "success_transition": "PARCEL_CONFIRMED",
        "failure_transition": "PAUSE_UNTIL_CONFIRMED",
    }


def _water_mode(objects: list[dict[str, Any]], f03_status: str) -> str:
    if f03_status == F03_FAILED:
        return "SOURCE_UNAVAILABLE"
    drawable = [row for row in objects if has_drawable_geometry(row.get("geometry") or {})]
    if drawable:
        return "FIELD_MAPPED"
    if objects:
        return "LOCATION_OR_INVENTORY"
    return "NO_MAPPED_LEADS"


def build_cper_demo_policy(
    listing_claims: list[dict[str, Any]],
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """CPER fixture policy only. Do not use as a general listing ranker."""
    ctx = dict(context or {})
    decision = ctx.get("decision_context") or {}
    objects = list(ctx.get("candidate_objects") or [])
    f03_status = str(ctx.get("f03_status") or F03_AVAILABLE)
    confirmation = str(ctx.get("confirmation_status") or "CONFIRMED")
    stage = str(decision.get("current_stage") or "PRE_VISIT")
    claim_ids = {row.get("claim_id") for row in listing_claims}
    water_mode = _water_mode(objects, f03_status)
    water = _water_action(2, mode=water_mode)
    access = _access_action(1)

    if confirmation != "CONFIRMED" or stage == "PARCEL_CONFIRMATION":
        actions = [_confirm_action()]
    elif stage in {"TITLE_REVIEW_ACTIVE", "DOCUMENT_REVIEW"}:
        water["execution_order"] = 1
        actions = [water]
    elif stage in {"FIELD_VISIT_ALREADY_BOOKED", "FIELD_FOLLOW_UP"}:
        water["execution_order"] = 1
        access["execution_order"] = 2
        actions = [water, access]
    else:
        actions = [access, water]

    action_ids = {row["action_id"] for row in actions}
    water_id = water["action_id"] if water["action_id"] in action_ids else None
    access_id = access["action_id"] if access["action_id"] in action_ids else None

    bottlenecks: list[dict[str, Any]] = []
    if "ACTION_CONFIRM_PARCEL" in action_ids:
        bottlenecks.append(
            {
                "bottleneck_id": "BOTTLENECK_PARCEL_CONFIRMATION",
                "bottleneck_rank": 1,
                "title": "Parcel outline is not confirmed",
                "supporting_observation_ids": ["OBS_AREA"],
                "affected_candidate_ids": [],
                "blocked_inferences": ["any diligence spend on an unconfirmed outline"],
                "decision_impact": "HIGH",
                "information_gain": "HIGH",
                "cost_class": "DESKTOP",
                "next_action_ids": ["ACTION_CONFIRM_PARCEL"],
            }
        )
    else:
        bottlenecks.extend(
            [
                {
                    "bottleneck_id": "BOTTLENECK_WATER_EVIDENCE",
                    "bottleneck_rank": 1,
                    "title": "Livestock-water use is the larger operating-evidence gap",
                    "supporting_observation_ids": ["OBS_WATER_COUNT"],
                    "affected_candidate_ids": [],
                    "blocked_inferences": [
                        "usable livestock water",
                        "seasonal reliability",
                        "missing mapped leads means no water",
                    ],
                    "decision_impact": "HIGH",
                    "information_gain": "HIGH",
                    "cost_class": water["cost_class"],
                    "next_action_ids": [water_id] if water_id else [],
                },
                {
                    "bottleneck_id": "BOTTLENECK_LEGAL_ACCESS",
                    "bottleneck_rank": 2,
                    "title": "Legal entrance is unproven"
                    if access_id
                    else "Legal entrance review is already in motion",
                    "supporting_observation_ids": ["OBS_ROAD"],
                    "affected_candidate_ids": [],
                    "blocked_inferences": ["legal access", "usable entrance"],
                    "decision_impact": "HIGH",
                    "information_gain": "HIGH",
                    "cost_class": "DOCUMENT_REQUEST",
                    "next_action_ids": [access_id] if access_id else [],
                },
                {
                    "bottleneck_id": "BOTTLENECK_FORAGE_LEAP",
                    "bottleneck_rank": 3,
                    "title": "Modeled growth must not be read as stockable forage",
                    "supporting_observation_ids": ["OBS_RAP_PROD"],
                    "affected_candidate_ids": [],
                    "blocked_inferences": ["carrying capacity", "ready for cattle"],
                    "decision_impact": "MEDIUM",
                    "information_gain": "MEDIUM",
                    "cost_class": "DESKTOP",
                    "next_action_ids": [],
                },
            ]
        )

    gaps = derive_claim_gaps(listing_claims)
    for gap in gaps:
        if gap.get("claim_id") and any(
            row.get("claim_id") == gap.get("claim_id") and row.get("category") == "LIVESTOCK_WATER"
            for row in listing_claims
        ):
            if f03_status == F03_FAILED:
                gap["supported_portion"] = "Mapped-water inventory is currently unavailable"
            elif not objects:
                gap["supported_portion"] = "No mapped hydrography leads were returned in the search"
            elif water_mode == "LOCATION_OR_INVENTORY":
                gap["supported_portion"] = (
                    "Mapped hydrography identities exist, but none can be placed on a map"
                )
            if water_id:
                gap["recommended_action_id"] = water_id
                if water_id == "ACTION_WATER_FIELD_CATEGORY" and "CLAIM_WATER_001" in claim_ids:
                    gap["recommended_message_id"] = "MSG_LISTING_WATER"
                else:
                    gap["recommended_message_id"] = "MSG_WATER"
        elif gap.get("claim_id") == "CLAIM_ACCESS_001":
            if access_id:
                gap["recommended_action_id"] = "ACTION_ACCESS_DOCUMENTS"
                gap["recommended_message_id"] = "MSG_TITLE_ACCESS"
            else:
                gap["recommended_action_id"] = None
                gap["recommended_message_id"] = None
        if "ACTION_CONFIRM_PARCEL" in action_ids:
            gap["recommended_action_id"] = "ACTION_CONFIRM_PARCEL"
            gap["recommended_message_id"] = "MSG_CONFIRM_PARCEL"

    messages: list[dict[str, Any]] = []
    water_claim = "CLAIM_WATER_001" if "CLAIM_WATER_001" in claim_ids else None
    access_claim = "CLAIM_ACCESS_001" if "CLAIM_ACCESS_001" in claim_ids else None
    if "ACTION_CONFIRM_PARCEL" in action_ids:
        messages.append(
            {
                "message_id": "MSG_CONFIRM_PARCEL",
                "audience": "PARTNER",
                "bound_action_id": "ACTION_CONFIRM_PARCEL",
                "bound_claim_id": None,
                "template_id": "CONFIRM_PARCEL_BEFORE_DILIGENCE",
            }
        )
        return {
            "bottlenecks": bottlenecks,
            "actions": actions,
            "action_policy": _action_policy_for(actions),
            "claim_evidence_gaps": gaps,
            "copy_ready_message_specs": messages,
        }
    if water_id == "ACTION_WATER_FIELD_CATEGORY":
        if water_claim:
            messages.append(
                {
                    "message_id": "MSG_LISTING_WATER",
                    "audience": "LISTING_BROKER",
                    "bound_action_id": water_id,
                    "bound_claim_id": water_claim,
                    "template_id": "ASK_WATER_TYPE_LOCATION_RECORDS",
                }
            )
        messages.append(
            {
                "message_id": "MSG_FIELD_WATER",
                "audience": "FIELD_VISITOR",
                "bound_action_id": water_id,
                "bound_claim_id": water_claim,
                "template_id": "REVIEW_MAPPED_WATER_AREAS",
            }
        )
    elif water_id == "ACTION_WATER_LOCATION_OR_INVENTORY":
        messages.append(
            {
                "message_id": "MSG_WATER",
                "audience": "LISTING_BROKER" if water_claim else "PARTNER",
                "bound_action_id": water_id,
                "bound_claim_id": water_claim,
                "template_id": "ASK_FOR_WATER_LOCATION_OR_INVENTORY",
            }
        )
    elif water_id == "ACTION_WATER_SOURCE_UNAVAILABLE":
        messages.append(
            {
                "message_id": "MSG_WATER",
                "audience": "LISTING_BROKER" if water_claim else "PARTNER",
                "bound_action_id": water_id,
                "bound_claim_id": water_claim,
                "template_id": "F03_INVENTORY_UNAVAILABLE",
            }
        )
    elif water_id == "ACTION_ASK_SELLER_WATER":
        messages.append(
            {
                "message_id": "MSG_WATER",
                "audience": "LISTING_BROKER" if water_claim else "PARTNER",
                "bound_action_id": water_id,
                "bound_claim_id": water_claim,
                "template_id": "ASK_SELLER_DEVELOPED_WATER",
            }
        )
    if access_id:
        messages.append(
            {
                "message_id": "MSG_TITLE_ACCESS",
                "audience": "TITLE_OR_COUNSEL",
                "bound_action_id": access_id,
                "bound_claim_id": access_claim,
                "template_id": "ASK_RECORDED_ENTRANCE",
            }
        )
        messages.append(
            {
                "message_id": "MSG_PARTNER",
                "audience": "PARTNER",
                "bound_action_id": access_id,
                "bound_claim_id": access_claim,
                "template_id": "WAIT_FOR_ACCESS_PAPER_BEFORE_FLIGHT",
            }
        )
    elif stage in {"TITLE_REVIEW_ACTIVE", "DOCUMENT_REVIEW"}:
        messages.append(
            {
                "message_id": "MSG_PARTNER",
                "audience": "PARTNER",
                "bound_action_id": water_id,
                "bound_claim_id": water_claim,
                "template_id": "TITLE_REVIEW_ALREADY_ACTIVE",
            }
        )
    return {
        "bottlenecks": bottlenecks,
        "actions": actions,
        "action_policy": _action_policy_for(actions),
        "claim_evidence_gaps": gaps,
        "copy_ready_message_specs": messages,
    }


def _action_policy_for(actions: list[dict[str, Any]]) -> dict[str, Any]:
    from rangematch.advisor_insight import build_cper_action_policy

    return build_cper_action_policy(actions)


def _default_decision_context(user_question: str | None) -> dict[str, Any]:
    return {
        "current_stage": "PRE_VISIT",
        "decision_deadline": "THIS_WEEK",
        "candidate_actions": [
            "REQUEST_DOCUMENTS",
            "SCHEDULE_FIELD_VISIT",
            "ENGAGE_PROFESSIONAL",
            "PAUSE_ADDITIONAL_SPEND",
        ],
        "user_question": user_question or "Should I fly to inspect this parcel this weekend?",
        "goal": "CHOOSE_NEXT_DILIGENCE_SPEND_NOT_PURCHASE",
    }


class MissingPolicyError(TypeError):
    """Caller must pass an explicit policy; CPER demo is never a silent default."""


class CperDemoPolicyRejected(ValueError):
    """build_cper_demo_policy may run only on the CPER engineering fixture."""


def is_cper_engineering_fixture(unified_output: Mapping[str, Any]) -> bool:
    geometry_id = str((unified_output.get("parcel") or {}).get("geometry_id") or "")
    return "ENGINEERING_TEST_GEOMETRY_CPER" in geometry_id


def project_cper_buyer_evidence_packet(
    unified_output: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    """CPER fixture assembly. Real listings must not call this."""
    return project_buyer_evidence_packet(
        unified_output, policy=build_cper_demo_policy, **kwargs
    )


def project_buyer_evidence_packet(
    unified_output: dict[str, Any],
    *,
    listing_claims: list[dict[str, Any]] | None = None,
    decision_context: dict[str, Any] | None = None,
    confirmation_status: str = "CONFIRMED",
    unified_output_ref: str = UNIFIED_OUTPUT_REF,
    candidate_inventory: Mapping[str, Any] | list[dict[str, Any]] | None = None,
    remote_pilot: Mapping[str, Any] | None = None,
    policy: PolicyBuilder | None = None,
    f03_status: str | None = None,
) -> dict[str, Any]:
    if policy is None:
        raise MissingPolicyError(
            "policy is required; pass build_cper_demo_policy only for the CPER engineering fixture"
        )
    parcel_in = unified_output.get("parcel") or {}
    geometry_id = parcel_in.get("geometry_id") or "UNKNOWN_PARCEL"
    policy_name = getattr(policy, "__name__", "anonymous_policy")
    if policy_name == "build_cper_demo_policy" and not is_cper_engineering_fixture(
        unified_output
    ):
        raise CperDemoPolicyRejected(
            "build_cper_demo_policy is CPER_FIXTURE_ONLY and cannot run on this parcel"
        )
    claims = list(listing_claims or [])
    if f03_status == F03_FAILED:
        resolved_f03 = F03_FAILED
        objects: list[dict[str, Any]] = []
    elif candidate_inventory is not None:
        resolved_f03 = F03_AVAILABLE
        objects = project_candidate_objects(candidate_inventory, remote_pilot)
    else:
        resolved_f03 = F03_NOT_PROVIDED
        objects = []
    context = {
        "decision_context": decision_context or _default_decision_context(None),
        "candidate_objects": objects,
        "f03_status": resolved_f03,
        "confirmation_status": confirmation_status,
    }
    try:
        graph = policy(claims, context)
    except TypeError:
        graph = policy(claims)
    actions = constrain_actions_to_objects(list(graph["actions"]), objects)
    bottlenecks = [
        {
            **row,
            "affected_candidate_ids": [item["candidate_id"] for item in objects]
            if objects and row.get("bottleneck_id") == "BOTTLENECK_WATER_EVIDENCE"
            else list(row.get("affected_candidate_ids") or []),
        }
        for row in graph["bottlenecks"]
    ]
    return {
        "schema_version": PACKET_SCHEMA,
        "parcel": {
            "parcel_id": geometry_id,
            "geometry_hash": parcel_in.get("geometry_hash"),
            "confirmation_status": confirmation_status,
            "display_label": "CPER engineering test geometry, Weld County, CO"
            if is_cper_engineering_fixture(unified_output)
            else None,
            "is_engineering_test_geometry": is_cper_engineering_fixture(unified_output),
        },
        "decision_context": decision_context or _default_decision_context(None),
        "listing_claims": claims,
        "observations": project_observations(unified_output, f03_status=resolved_f03),
        "candidate_objects": objects,
        "claim_evidence_gaps": graph["claim_evidence_gaps"],
        "bottlenecks": bottlenecks,
        "actions": actions,
        "action_policy": graph.get("action_policy") or _action_policy_for(actions),
        "copy_ready_message_specs": graph["copy_ready_message_specs"],
        "prohibited_inferences": [
            "suitability",
            "carrying_capacity",
            "species_ranking",
            "purchase_recommendation",
            "legal_access_from_road_contact",
            "usable_water_from_mapped_hydrography",
            "missing_verification_means_absent",
            "named_pin_without_candidate_object",
        ],
        "technical_references": {
            "unified_output": unified_output_ref,
            "f03_status": resolved_f03,
            "f03_candidate_inventory": F03_INVENTORY_REF if objects else None,
            "f03_remote_pilot": F03_REMOTE_PILOT_REF if objects else None,
            "candidate_object_count_in_packet": len(objects),
            "drawable_object_count": sum(
                1 for row in objects if has_drawable_geometry(row.get("geometry") or {})
            ),
            "policy": policy_name,
            "policy_scope": "CPER_FIXTURE_ONLY"
            if policy_name == "build_cper_demo_policy"
            else "EXPLICIT_NON_DEMO",
        },
    }
