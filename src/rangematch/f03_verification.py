"""Deterministic F03 verified-water schema validation and promotion evaluation.

Implements docs/F03_VERIFIED_WATER_EVIDENCE_CONTRACT.yaml@0.1.1.
Does not invent FIELD_VERIFIED outcomes from remote/open data alone.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

CONTRACT_VERSION = "0.1.1"
FACTOR_ID = "F03_LIVESTOCK_WATER"

VERIFICATION_LEVELS = (
    "MAPPED_CANDIDATE",
    "REMOTELY_SUPPORTED_CANDIDATE",
    "FIELD_VERIFIED_LIVESTOCK_WATER",
    "REJECTED_AS_SOURCE",
)

FEATURE_TYPES = {
    "pond",
    "reservoir",
    "stream",
    "spring",
    "well",
    "tank",
    "trough",
    "pipeline_outlet",
    "canal",
    "other",
}

PRESENCE_SOURCES = {
    "imagery",
    "hydrography",
    "records",
    "field",
    "hydrography_plus_independent_record",
    "operator_record_equivalent",
    "reviewed_equivalent",
}

REMOTE_PRESENCE_SOURCES = {
    "imagery",
    "hydrography_plus_independent_record",
    "records",
    "reviewed_equivalent",
}

FIELD_PRESENCE_SOURCES = {
    "field",
    "operator_record_equivalent",
    "reviewed_equivalent",
}

EVIDENCE_CLASSES = {
    "REMOTE_ONLY",
    "FIELD_OBSERVATION",
    "OPERATOR_OWNER_OPERATIONAL_RECORD",
    "REVIEWED_EQUIVALENT",
    "MIXED",
}

FIELD_EVIDENCE_CLASSES = {
    "FIELD_OBSERVATION",
    "OPERATOR_OWNER_OPERATIONAL_RECORD",
    "REVIEWED_EQUIVALENT",
    "MIXED",
}

# Presence sources that require reproducible remote provenance for REMOTELY_SUPPORTED.
PROVENANCE_REQUIRED_PRESENCE_SOURCES = {
    "imagery",
    "reviewed_equivalent",
    "hydrography_plus_independent_record",
}

REQUIRED_REMOTE_PRESENCE_PROVENANCE_FIELDS = (
    "provider",
    "product_name",
    "source_url",
    "item_id_or_artifact_reference",
    "imagery_acquisition_date",
    "review_date",
    "reviewer_or_adapter_id",
    "candidate_geometry_hash",
    "parcel_geometry_hash",
    "response_or_artifact_hash",
    "supported_claim",
    "unsupported_claims",
    "limitations",
    "freshness_status",
)


def remote_presence_provenance_complete(provenance: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return completeness of remote physical-presence provenance."""
    if not provenance:
        return {
            "complete": False,
            "missing_fields": list(REQUIRED_REMOTE_PRESENCE_PROVENANCE_FIELDS),
        }
    missing = [
        field
        for field in REQUIRED_REMOTE_PRESENCE_PROVENANCE_FIELDS
        if provenance.get(field) in (None, "", [], {})
    ]
    # Accept either source_url or item_id_or_artifact_reference already required;
    # response_or_artifact_hash must be a non-trivial digest string.
    digest = provenance.get("response_or_artifact_hash")
    if digest is not None and not (isinstance(digest, str) and len(digest) >= 32):
        if "response_or_artifact_hash" not in missing:
            missing.append("response_or_artifact_hash")
    return {"complete": not missing, "missing_fields": missing}


def _unknown_capacity(*, rationale: str | None = None) -> dict[str, Any]:
    return {
        "status": "unknown",
        "value": None,
        "unit": None,
        "scenario_reference": None,
        "unknown_rationale": rationale,
    }


def _unknown_water_quality() -> dict[str, Any]:
    return {
        "status": "unknown",
        "diligence_required": True,
        "evidence_source_ids": [],
    }


def default_mapped_dimensions(*, feature_type: str = "other") -> dict[str, Any]:
    """Minimal evaluated dimensions for a fresh MAPPED_CANDIDATE."""
    return {
        "feature_identity": {"type": feature_type},
        "physical_presence": {"status": "uncertain", "source": "hydrography"},
        "seasonal_reliability": {"status": "unknown"},
        "livestock_accessibility": {"status": "unknown"},
        "capacity_and_quality": {
            "capacity": _unknown_capacity(
                rationale="Capacity not measured or documented for this candidate."
            ),
            "water_quality": _unknown_water_quality(),
        },
        "legal_access": {"status": "unresolved"},
    }


def validate_candidate_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate dimension schema. Does not compute promotion."""
    issues: list[str] = []
    dims = record.get("dimensions") or {}

    identity = dims.get("feature_identity") or {}
    feature_type = identity.get("type")
    if feature_type not in FEATURE_TYPES:
        issues.append("feature_identity.type_invalid_or_missing")

    presence = dims.get("physical_presence") or {}
    if presence.get("status") not in {"confirmed", "uncertain", "absent"}:
        issues.append("physical_presence.status_invalid_or_missing")
    if presence.get("source") not in PRESENCE_SOURCES:
        issues.append("physical_presence.source_invalid_or_missing")

    seasonal = dims.get("seasonal_reliability") or {}
    if seasonal.get("status") not in {"perennial", "intermittent", "ephemeral", "unknown"}:
        issues.append("seasonal_reliability.status_invalid_or_missing")
    if seasonal.get("status") not in (None, "unknown") and not seasonal.get("observation_period"):
        # Soft requirement: warn but allow if observation_period omitted in tests.
        issues.append("seasonal_reliability.observation_period_missing_when_status_known")

    access = dims.get("livestock_accessibility") or {}
    if access.get("status") not in {"supported", "constrained", "unknown"}:
        issues.append("livestock_accessibility.status_invalid_or_missing")

    cq = dims.get("capacity_and_quality") or {}
    capacity = cq.get("capacity") or {}
    if capacity.get("status") not in {"measured", "documented", "unknown"}:
        issues.append("capacity.status_invalid_or_missing")
    elif capacity.get("status") in {"measured", "documented"}:
        if capacity.get("value") is None:
            issues.append("capacity.value_required_when_measured_or_documented")
        if not capacity.get("unit"):
            issues.append("capacity.unit_required_when_measured_or_documented")
        if not capacity.get("scenario_reference"):
            issues.append("capacity.scenario_reference_required_when_measured_or_documented")
    elif capacity.get("status") == "unknown":
        # Rationale required only when asserting field-verified path; schema still
        # prefers rationale whenever unknown is explicit.
        if capacity.get("unknown_rationale") in (None, ""):
            issues.append("capacity.unknown_rationale_missing")

    water_quality = cq.get("water_quality") or {}
    if water_quality.get("status") not in {"verified", "unknown"}:
        issues.append("water_quality.status_invalid_or_missing")
    else:
        diligence = water_quality.get("diligence_required")
        if not isinstance(diligence, bool):
            issues.append("water_quality.diligence_required_missing")
        elif water_quality.get("status") == "unknown" and diligence is not True:
            issues.append("water_quality.diligence_required_must_be_true_when_unknown")
        if water_quality.get("status") == "verified":
            ids = water_quality.get("evidence_source_ids")
            if not isinstance(ids, list) or not ids:
                issues.append("water_quality.evidence_source_ids_required_when_verified")

    legal = dims.get("legal_access") or {}
    if legal.get("status") not in {"verified", "unresolved", "not_applicable"}:
        issues.append("legal_access.status_invalid_or_missing")
    if legal.get("status") in {"verified", "not_applicable"} and not legal.get("basis"):
        issues.append("legal_access.basis_required")

    level = record.get("verification_level") or {}
    evidence_class = level.get("evidence_class") or record.get("evidence_class")
    if evidence_class is not None and evidence_class not in EVIDENCE_CLASSES:
        issues.append("evidence_class_invalid")

    # Treat observation_period soft-issue as non-blocking for schema_ok used by promotion.
    blocking = [i for i in issues if i != "seasonal_reliability.observation_period_missing_when_status_known"]
    return {
        "ok": not blocking,
        "issues": issues,
        "blocking_issues": blocking,
        "contract_version": CONTRACT_VERSION,
    }


def _at_least_one_remote_attribute(dims: Mapping[str, Any]) -> bool:
    seasonal = (dims.get("seasonal_reliability") or {}).get("status")
    if seasonal in {"perennial", "intermittent", "ephemeral"}:
        return True
    access = (dims.get("livestock_accessibility") or {}).get("status")
    if access in {"supported", "constrained"}:
        return True
    capacity = ((dims.get("capacity_and_quality") or {}).get("capacity") or {}).get("status")
    if capacity in {"measured", "documented"}:
        return True
    water_quality = ((dims.get("capacity_and_quality") or {}).get("water_quality") or {}).get(
        "status"
    )
    return water_quality == "verified"


def _field_presence_basis_ok(record: Mapping[str, Any], dims: Mapping[str, Any]) -> bool:
    presence = dims.get("physical_presence") or {}
    evidence_class = (record.get("verification_level") or {}).get("evidence_class") or record.get(
        "evidence_class"
    )
    if presence.get("source") in FIELD_PRESENCE_SOURCES and evidence_class != "MIXED":
        return True
    if evidence_class == "MIXED":
        if not record.get("qualified_field_basis_required", False) and not (
            record.get("verification_level") or {}
        ).get("qualified_field_basis_required", False):
            # Also accept basis nested under physical_presence.
            pass
        basis = presence.get("qualified_field_basis") or record.get("qualified_field_basis") or {}
        required_flag = bool(
            record.get("qualified_field_basis_required")
            or (record.get("verification_level") or {}).get("qualified_field_basis_required")
            or basis
        )
        if not required_flag:
            return False
        return (
            basis.get("source") in {"field", "operator_record_equivalent", "reviewed_equivalent"}
            and bool(basis.get("as_of"))
            and bool(basis.get("record_or_observation_hash"))
        )
    if presence.get("source") in FIELD_PRESENCE_SOURCES:
        return True
    return False


def _capacity_field_ok(capacity: Mapping[str, Any]) -> bool:
    status = capacity.get("status")
    if status in {"measured", "documented"}:
        return (
            capacity.get("value") is not None
            and bool(capacity.get("unit"))
            and bool(capacity.get("scenario_reference"))
        )
    if status == "unknown":
        return bool(capacity.get("unknown_rationale"))
    return False


def _water_quality_field_ok(water_quality: Mapping[str, Any]) -> bool:
    status = water_quality.get("status")
    if status == "verified":
        ids = water_quality.get("evidence_source_ids")
        return isinstance(ids, list) and bool(ids) and water_quality.get("diligence_required") in (
            True,
            False,
        )
    if status == "unknown":
        return water_quality.get("diligence_required") is True
    return False


def evaluate_promotion(record: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate verification_level from dimensions under contract v0.1.1."""
    validation = validate_candidate_record(record)
    dims = record.get("dimensions") or {}
    presence = dims.get("physical_presence") or {}
    seasonal = dims.get("seasonal_reliability") or {}
    access = dims.get("livestock_accessibility") or {}
    legal = dims.get("legal_access") or {}
    cq = dims.get("capacity_and_quality") or {}
    capacity = cq.get("capacity") or {}
    water_quality = cq.get("water_quality") or {}
    evidence_class = (record.get("verification_level") or {}).get("evidence_class") or record.get(
        "evidence_class"
    )
    prior = record.get("prior_level") or "MAPPED_CANDIDATE"
    attempted = record.get("attempted_level")

    result: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "schema_validation": validation,
        "verification_level": "MAPPED_CANDIDATE",
        "reason_codes": [],
        "promoted_to_remotely_supported": False,
        "promoted_to_field_verified": False,
        "transition_allowed": True,
        "ranking_effect": "NONE",
    }

    if attempted == "FIELD_VERIFIED_LIVESTOCK_WATER" and prior == "MAPPED_CANDIDATE":
        result["transition_allowed"] = False
        result["reason_codes"].append("SKIP_REMOTELY_SUPPORTED_PROHIBITED")
        result["verification_level"] = "MAPPED_CANDIDATE"
        return result

    if record.get("only_evidence_is_euclidean_proximity") or (
        record.get("euclidean_distance_m") is not None
        and record.get("dimensions_unchanged_from_mapped")
    ):
        result["reason_codes"].append("DISTANCE_NOT_PRESENCE_OR_ACCESS")
        result["verification_level"] = "MAPPED_CANDIDATE"
        result["promoted"] = False
        return result

    if presence.get("status") == "absent":
        result["verification_level"] = "REJECTED_AS_SOURCE"
        result["reason_codes"].append("PHYSICAL_PRESENCE_ABSENT")
        return result

    # Remote promotion — imagery/reviewed_equivalent require provenance completeness.
    provenance = presence.get("provenance") or record.get("presence_provenance")
    provenance_gate = remote_presence_provenance_complete(provenance)
    needs_provenance = presence.get("source") in PROVENANCE_REQUIRED_PRESENCE_SOURCES
    remote_ok = (
        presence.get("status") == "confirmed"
        and presence.get("source") in REMOTE_PRESENCE_SOURCES
        and _at_least_one_remote_attribute(dims)
        and not record.get("unresolved_material_conflict")
        and (not needs_provenance or provenance_gate["complete"])
    )
    if (
        presence.get("status") == "confirmed"
        and needs_provenance
        and not provenance_gate["complete"]
    ):
        result["reason_codes"].append("REMOTE_PRESENCE_PROVENANCE_INCOMPLETE")
        result["provenance_missing_fields"] = provenance_gate["missing_fields"]

    # Field promotion
    field_ok = False
    field_reason = None
    if evidence_class == "REMOTE_ONLY":
        field_reason = "REMOTE_EVIDENCE_CEILING"
    elif evidence_class not in FIELD_EVIDENCE_CLASSES:
        field_reason = "FIELD_EVIDENCE_CLASS_REQUIRED"
    elif prior not in {"REMOTELY_SUPPORTED_CANDIDATE", "FIELD_VERIFIED_LIVESTOCK_WATER"} and not remote_ok:
        # Must not skip remotely supported when starting from mapped-only evidence.
        if prior == "MAPPED_CANDIDATE":
            field_reason = "SKIP_REMOTELY_SUPPORTED_PROHIBITED"
    else:
        if presence.get("status") != "confirmed":
            field_reason = "PRESENCE_NOT_CONFIRMED"
        elif not _field_presence_basis_ok(record, dims):
            field_reason = "FIELD_OR_MIXED_BASIS_REQUIRED"
        elif seasonal.get("status") == "unknown":
            field_reason = "SEASONAL_UNKNOWN_BLOCKS_FIELD_VERIFIED"
        elif access.get("status") not in {"supported", "constrained"}:
            field_reason = "ACCESSIBILITY_UNKNOWN_BLOCKS_FIELD_VERIFIED"
        elif legal.get("status") not in {"verified", "not_applicable"}:
            field_reason = "LEGAL_ACCESS_UNRESOLVED"
        elif not _capacity_field_ok(capacity):
            if capacity.get("status") == "unknown" and not capacity.get("unknown_rationale"):
                field_reason = "CAPACITY_UNKNOWN_RATIONALE_REQUIRED"
            else:
                field_reason = "CAPACITY_SCHEMA_INCOMPLETE"
        elif not _water_quality_field_ok(water_quality):
            field_reason = "WATER_QUALITY_SCHEMA_INCOMPLETE"
        elif evidence_class == "MIXED" and not _field_presence_basis_ok(record, dims):
            field_reason = "MIXED_REQUIRES_QUALIFIED_FIELD_BASIS"
        else:
            # prior must be remotely supported (or already field); allow if remote_ok
            # simultaneously established in same evaluation from mapped.
            if prior == "MAPPED_CANDIDATE" and not remote_ok:
                field_reason = "SKIP_REMOTELY_SUPPORTED_PROHIBITED"
            else:
                field_ok = True

    if field_ok:
        result["verification_level"] = "FIELD_VERIFIED_LIVESTOCK_WATER"
        result["promoted_to_field_verified"] = True
        result["promoted_to_remotely_supported"] = True
        result["reason_codes"].append("FIELD_VERIFIED_CRITERIA_MET")
        return result

    if remote_ok:
        result["verification_level"] = "REMOTELY_SUPPORTED_CANDIDATE"
        result["promoted_to_remotely_supported"] = True
        if field_reason:
            result["reason_codes"].append(field_reason)
        else:
            result["reason_codes"].append("REMOTE_CRITERIA_MET")
        return result

    # Preserve an already-earned remote tier when field promotion fails.
    if prior == "REMOTELY_SUPPORTED_CANDIDATE":
        result["verification_level"] = "REMOTELY_SUPPORTED_CANDIDATE"
        result["promoted_to_remotely_supported"] = True
        if field_reason:
            result["reason_codes"].append(field_reason)
        return result

    result["verification_level"] = "MAPPED_CANDIDATE"
    if field_reason:
        result["reason_codes"].append(field_reason)
    if not remote_ok:
        result["reason_codes"].append("REMOTE_CRITERIA_NOT_MET")
    return result


def map_nhd_fcode_to_seasonal(fcode: Any) -> dict[str, Any] | None:
    """Map common NHD FCodes to seasonal_reliability for remote enrichment only."""
    try:
        code = int(fcode)
    except (TypeError, ValueError):
        return None
    mapping = {
        46006: "perennial",
        46003: "intermittent",
        46007: "ephemeral",
    }
    status = mapping.get(code)
    if not status:
        return None
    return {
        "status": status,
        "observation_period": f"nhd_fcode_{code}",
        "evidence_source_ids": ["USGS_NHDPLUS_HR_FCODE"],
        "note": "Hydrography permanence attribute only; not livestock usability.",
    }


def map_nhd_ftype_to_feature_type(ftype: Any, fcode: Any = None) -> str:
    try:
        ft = int(ftype) if ftype is not None else None
    except (TypeError, ValueError):
        ft = None
    try:
        fc = int(fcode) if fcode is not None else None
    except (TypeError, ValueError):
        fc = None
    if ft == 390 or (fc is not None and 39000 <= fc < 39100):
        return "pond"
    if ft in {460, 558} or (fc is not None and 46000 <= fc < 46100):
        return "stream"
    if ft == 336:
        return "canal"
    return "other"


def build_mapped_candidate_from_nhd(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize an NHD inventory row to a contract candidate at MAPPED level."""
    feature_type = map_nhd_ftype_to_feature_type(raw.get("ftype"), raw.get("fcode"))
    dims = default_mapped_dimensions(feature_type=feature_type)
    record = {
        "candidate_id": raw.get("candidate_id"),
        "source": raw.get("source") or "USGS_NHDPLUS_HR",
        "source_layer": raw.get("source_layer"),
        "source_feature_id": raw.get("source_feature_id"),
        "fcode": raw.get("fcode"),
        "ftype": raw.get("ftype"),
        "gnis_name": raw.get("gnis_name"),
        "intersects_parcel": raw.get("intersects_parcel"),
        "prior_level": "MAPPED_CANDIDATE",
        "evidence_class": "REMOTE_ONLY",
        "dimensions": dims,
        "verification_level": {
            "status": "MAPPED_CANDIDATE",
            "evidence_class": "REMOTE_ONLY",
            "as_of": raw.get("as_of") or "1970-01-01T00:00:00Z",
        },
    }
    return record


def apply_remote_enrichment(
    record: Mapping[str, Any],
    *,
    seasonal_from_fcode: bool = True,
    reviewed_presence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach remote-only enrichment and re-evaluate promotion.

    Never sets FIELD_VERIFIED. reviewed_presence may lift presence to confirmed
    with source reviewed_equivalent only when provenance is complete; otherwise
    the candidate remains MAPPED_CANDIDATE with ENGINEERING_VALIDATION_ONLY.
    """
    out = deepcopy(dict(record))
    out["evidence_class"] = "REMOTE_ONLY"
    out.setdefault("verification_level", {})
    out["verification_level"]["evidence_class"] = "REMOTE_ONLY"
    dims = out.setdefault("dimensions", {})

    if seasonal_from_fcode:
        seasonal = map_nhd_fcode_to_seasonal(out.get("fcode"))
        if seasonal:
            dims["seasonal_reliability"] = {
                "status": seasonal["status"],
                "observation_period": seasonal["observation_period"],
                "evidence_source_ids": seasonal["evidence_source_ids"],
                "note": seasonal["note"],
            }

    evidence_use_limit = None
    if reviewed_presence:
        provenance = reviewed_presence.get("provenance") or {}
        gate = remote_presence_provenance_complete(provenance)
        if gate["complete"]:
            dims["physical_presence"] = {
                "status": "confirmed",
                "source": reviewed_presence.get("source") or "imagery",
                "observation_date": reviewed_presence.get("observation_date")
                or provenance.get("imagery_acquisition_date"),
                "review_note": reviewed_presence.get("review_note"),
                "evidence_source_ids": reviewed_presence.get("evidence_source_ids")
                or ["REMOTE_IMAGERY_PROVENANCE_PACKAGE"],
                "provenance": dict(provenance),
            }
        else:
            evidence_use_limit = "ENGINEERING_VALIDATION_ONLY"
            dims["physical_presence"] = {
                "status": "uncertain",
                "source": "hydrography",
                "evidence_use_limit": evidence_use_limit,
                "rejected_reviewed_presence_reason": "REMOTE_PRESENCE_PROVENANCE_INCOMPLETE",
                "provenance_missing_fields": gate["missing_fields"],
                "provisional_review_note": reviewed_presence.get("review_note"),
            }

    evaluation = evaluate_promotion(out)
    # Hard ceiling for this enrichment helper.
    if evaluation["verification_level"] == "FIELD_VERIFIED_LIVESTOCK_WATER":
        evaluation["verification_level"] = "REMOTELY_SUPPORTED_CANDIDATE"
        evaluation["promoted_to_field_verified"] = False
        evaluation["reason_codes"].append("REMOTE_PILOT_CEILING_ENFORCED")
    out["verification_level"]["status"] = evaluation["verification_level"]
    out["promotion_evaluation"] = evaluation
    if evidence_use_limit:
        out["evidence_use_limit"] = evidence_use_limit
    return out


def factor_input_quality_from_levels(levels: list[str]) -> str:
    """Map candidate verification levels to existing F03 parcel input_quality_state."""
    if any(level == "FIELD_VERIFIED_LIVESTOCK_WATER" for level in levels):
        return "PHYSICAL_SOURCE_UNVERIFIED_SYSTEM"
    if not levels:
        return "MISSING"
    return "MAPPED_CANDIDATES_ONLY"


SELECTION_METHOD_STABLE_CANDIDATE_ID_ORDER = (
    "STABLE_CANDIDATE_ID_ORDER_MAX_3"
)


def stable_sample_f03_candidates(
    inventory: list[Mapping[str, Any]],
    *,
    max_n: int = 3,
) -> dict[str, Any]:
    """Deterministic F03 remote-collection sampling.

    Orders by candidate_id, then source_layer, source_feature_id, object_id.
    Does not prefer expected promotion outcomes.
    """
    ordered = sorted(
        list(inventory),
        key=lambda row: (
            str(row.get("candidate_id") or ""),
            str(row.get("source_layer") or ""),
            str(row.get("source_feature_id") or ""),
            str(row.get("object_id") or ""),
        ),
    )
    selected = ordered[: max(0, int(max_n))]
    return {
        "selection_method": SELECTION_METHOD_STABLE_CANDIDATE_ID_ORDER,
        "max_n": max_n,
        "available_count": len(inventory),
        "sampled_count": len(selected),
        "selected": selected,
        "selection_keys": [
            {
                "candidate_id": row.get("candidate_id"),
                "source_layer": row.get("source_layer"),
                "source_feature_id": row.get("source_feature_id"),
            }
            for row in selected
        ],
    }
