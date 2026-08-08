"""F03 field/operator evidence ingestion and deterministic verification.

Implements the Field/Operator Evidence Ingestion Workflow for
docs/F03_VERIFIED_WATER_EVIDENCE_CONTRACT.yaml@0.1.1.

Synthetic fixtures only may demonstrate FIELD_VERIFIED outcomes.
Live XPV parcel profiles must never be written by this module.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from rangematch.f03_verification import (
    CONTRACT_VERSION,
    EVIDENCE_CLASSES,
    FIELD_EVIDENCE_CLASSES,
    evaluate_promotion,
    validate_candidate_record,
)

INGESTION_SPEC_VERSION = "0.1.0"
FACTOR_ID = "F03_LIVESTOCK_WATER"

FIXTURE_TYPE_SYNTHETIC = "SYNTHETIC_ENGINEERING_TEST"
EVIDENCE_USE_LIMIT_TEST_ONLY = "TEST_ONLY"

FIELD_RECORD_PREFERRED_MAX_AGE_DAYS = 365

LIVE_PARCEL_IDS = frozenset(
    {
        "XPV_CPER_001",
        "XPV_KONZA_001",
        "XPV_REYNOLDS_001",
        "XPV_ORDWAY_001",
        "XPV_KBS_MCSE_001",
    }
)

REQUIRED_PACKAGE_FIELDS = (
    "package_id",
    "evidence_class",
    "candidate_id",
    "prior_level",
    "parcel_context",
    "candidate_linkage",
    "evidence_hashes",
    "observed_or_fetched_at",
    "reviewer_or_adapter_id",
    "dimensions",
)

REQUIRED_PARCEL_CONTEXT_FIELDS = (
    "parcel_id",
    "parcel_geometry_hash",
)

REQUIRED_CANDIDATE_LINKAGE_FIELDS = (
    "geometry_or_point_hash",
    "source_reference",
)

REQUIRED_HASH_FIELDS = ("response_or_artifact_hash_or_record_hash",)

REQUIRED_SYNTHETIC_MARKERS = (
    "fixture_type",
    "evidence_use_limit",
)


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value.strip()) >= 32


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _age_days(as_of: str | None, observed_at: str | None) -> float | None:
    end = _parse_dt(as_of) or datetime.now(timezone.utc)
    start = _parse_dt(observed_at)
    if start is None:
        return None
    return (end - start).total_seconds() / 86400.0


def is_live_parcel_id(parcel_id: Any) -> bool:
    if not isinstance(parcel_id, str):
        return False
    if parcel_id in LIVE_PARCEL_IDS:
        return True
    return parcel_id.startswith("XPV_")


def validate_evidence_package(package: Mapping[str, Any]) -> dict[str, Any]:
    """Validate normalized field/operator evidence package structure and hashes."""
    issues: list[str] = []
    blocking: list[str] = []

    for field in REQUIRED_PACKAGE_FIELDS:
        if package.get(field) in (None, "", {}, []):
            issues.append(f"package.{field}_missing")
            blocking.append(f"package.{field}_missing")

    evidence_class = package.get("evidence_class")
    if evidence_class not in EVIDENCE_CLASSES:
        issues.append("package.evidence_class_invalid")
        blocking.append("package.evidence_class_invalid")
    elif evidence_class not in FIELD_EVIDENCE_CLASSES:
        issues.append("package.evidence_class_not_field_eligible")
        blocking.append("package.evidence_class_not_field_eligible")

    parcel = package.get("parcel_context") or {}
    for field in REQUIRED_PARCEL_CONTEXT_FIELDS:
        if parcel.get(field) in (None, ""):
            issues.append(f"parcel_context.{field}_missing")
            blocking.append(f"parcel_context.{field}_missing")
    if not _is_digest(parcel.get("parcel_geometry_hash")):
        issues.append("parcel_context.parcel_geometry_hash_invalid")
        blocking.append("parcel_context.parcel_geometry_hash_invalid")

    linkage = package.get("candidate_linkage") or {}
    for field in REQUIRED_CANDIDATE_LINKAGE_FIELDS:
        if linkage.get(field) in (None, ""):
            issues.append(f"candidate_linkage.{field}_missing")
            blocking.append(f"candidate_linkage.{field}_missing")
    if not _is_digest(linkage.get("geometry_or_point_hash")):
        issues.append("candidate_linkage.geometry_or_point_hash_invalid")
        blocking.append("candidate_linkage.geometry_or_point_hash_invalid")

    hashes = package.get("evidence_hashes") or {}
    digest = hashes.get("response_or_artifact_hash_or_record_hash")
    if digest in (None, ""):
        issues.append("evidence_hashes.response_or_artifact_hash_or_record_hash_missing")
        blocking.append("evidence_hashes.response_or_artifact_hash_or_record_hash_missing")
    elif not _is_digest(digest):
        issues.append("evidence_hashes.response_or_artifact_hash_or_record_hash_invalid")
        blocking.append("evidence_hashes.response_or_artifact_hash_or_record_hash_invalid")

    if not _is_nonempty_str(package.get("observed_or_fetched_at")):
        issues.append("package.observed_or_fetched_at_missing")
        blocking.append("package.observed_or_fetched_at_missing")
    if not _is_nonempty_str(package.get("reviewer_or_adapter_id")):
        issues.append("package.reviewer_or_adapter_id_missing")
        blocking.append("package.reviewer_or_adapter_id_missing")

    # Synthetic isolation markers — required whenever fixture_type is present or
    # when evidence_use_limit asserts TEST_ONLY. Live packages would omit these.
    fixture_type = package.get("fixture_type")
    use_limit = package.get("evidence_use_limit")
    if fixture_type is not None or use_limit is not None:
        if fixture_type != FIXTURE_TYPE_SYNTHETIC:
            issues.append("fixture_type_must_be_SYNTHETIC_ENGINEERING_TEST")
            blocking.append("fixture_type_must_be_SYNTHETIC_ENGINEERING_TEST")
        if use_limit != EVIDENCE_USE_LIMIT_TEST_ONLY:
            issues.append("evidence_use_limit_must_be_TEST_ONLY")
            blocking.append("evidence_use_limit_must_be_TEST_ONLY")

    if is_live_parcel_id(parcel.get("parcel_id")):
        issues.append("LIVE_PARCEL_WRITE_PROHIBITED")
        blocking.append("LIVE_PARCEL_WRITE_PROHIBITED")

    dims = package.get("dimensions") or {}
    dim_validation = validate_candidate_record(
        {
            "dimensions": dims,
            "evidence_class": evidence_class,
            "verification_level": {"evidence_class": evidence_class},
        }
    )
    issues.extend(dim_validation["issues"])
    blocking.extend(dim_validation["blocking_issues"])

    return {
        "ok": not blocking,
        "issues": issues,
        "blocking_issues": blocking,
        "contract_version": CONTRACT_VERSION,
        "ingestion_spec_version": INGESTION_SPEC_VERSION,
    }


def detect_geometry_mismatch(package: Mapping[str, Any]) -> dict[str, Any]:
    """Geometry change invalidates verification until re-linked."""
    parcel = package.get("parcel_context") or {}
    expected = package.get("expected_parcel_geometry_hash") or parcel.get(
        "expected_parcel_geometry_hash"
    )
    current = parcel.get("parcel_geometry_hash")
    linked = package.get("linked_parcel_geometry_hash") or (
        (package.get("candidate_linkage") or {}).get("linked_parcel_geometry_hash")
    )
    mismatch = False
    reason = None
    if expected and current and expected != current:
        mismatch = True
        reason = "PARCEL_GEOMETRY_HASH_CHANGED"
    elif linked and current and linked != current:
        mismatch = True
        reason = "CANDIDATE_LINKED_TO_STALE_PARCEL_GEOMETRY"
    return {
        "mismatch": mismatch,
        "reason": reason,
        "expected_parcel_geometry_hash": expected,
        "current_parcel_geometry_hash": current,
        "linked_parcel_geometry_hash": linked,
    }


def detect_material_conflicts(package: Mapping[str, Any]) -> dict[str, Any]:
    """Return material source conflicts declared or inferred in the package."""
    declared = list(package.get("material_conflicts") or package.get("conflicts") or [])
    dims = package.get("dimensions") or {}
    presence = dims.get("physical_presence") or {}
    legal = dims.get("legal_access") or {}
    seasonal = dims.get("seasonal_reliability") or {}

    inferred: list[dict[str, Any]] = []
    if package.get("unresolved_material_conflict") is True:
        inferred.append(
            {
                "conflict_id": "DECLARED_UNRESOLVED_MATERIAL_CONFLICT",
                "dimensions": ["unspecified"],
            }
        )
    if presence.get("status") == "absent" and package.get("operator_claims_active_use"):
        inferred.append(
            {
                "conflict_id": "IMAGERY_OR_FIELD_ABSENT_VS_OPERATOR_ACTIVE_USE",
                "dimensions": ["physical_presence", "operational_use"],
            }
        )
    if legal.get("status") == "unresolved" and package.get("legal_access_denied") is True:
        # Explicit denial conflict vs claimed physical use.
        if package.get("physical_use_claimed"):
            inferred.append(
                {
                    "conflict_id": "LEGAL_ACCESS_DENIED_VS_PHYSICAL_USE_CLAIMED",
                    "dimensions": ["legal_access", "physical_presence"],
                }
            )
    if package.get("perennial_claim") and seasonal.get("status") == "ephemeral":
        inferred.append(
            {
                "conflict_id": "PERENNIAL_CLAIM_VS_EPHEMERAL_EVIDENCE",
                "dimensions": ["seasonal_reliability"],
            }
        )

    all_conflicts = declared + inferred
    return {
        "has_conflict": bool(all_conflicts) or bool(package.get("unresolved_material_conflict")),
        "conflicts": all_conflicts,
    }


def assess_freshness(package: Mapping[str, Any]) -> dict[str, Any]:
    """Stale field/operator evidence remains usable only with explicit limitation."""
    as_of = (
        ((package.get("verification_level") or {}).get("as_of"))
        or package.get("as_of")
        or package.get("observed_or_fetched_at")
    )
    observed = package.get("observed_or_fetched_at")
    age = _age_days(as_of if as_of != observed else None, observed)
    # If as_of equals observed, compute against review_date or synthetic now.
    if age is None or age == 0:
        review = package.get("review_date") or package.get("as_of")
        age = _age_days(review, observed)
    stale = age is not None and age > FIELD_RECORD_PREFERRED_MAX_AGE_DAYS
    limitations = list(package.get("limitations") or [])
    if stale:
        note = (
            f"STALE_FIELD_OR_OPERATOR_EVIDENCE age_days={age:.1f} "
            f"preferred_max_age_days={FIELD_RECORD_PREFERRED_MAX_AGE_DAYS}"
        )
        if note not in limitations:
            limitations.append(note)
        if not package.get("staleness_review_note") and not any(
            "stale" in str(x).lower() for x in limitations
        ):
            # Contract: may support FIELD_VERIFIED only with explicit staleness limitation.
            pass
    return {
        "age_days": age,
        "stale": stale,
        "preferred_max_age_days": FIELD_RECORD_PREFERRED_MAX_AGE_DAYS,
        "limitations": limitations,
        "staleness_review_note": package.get("staleness_review_note"),
        "allows_field_verified_with_limitation": bool(
            package.get("staleness_review_note")
            or any("stale" in str(x).lower() for x in limitations)
            or (stale and package.get("allow_stale_with_limitation", True))
        ),
    }


def system_context_complete(dims: Mapping[str, Any]) -> bool:
    """True when FIELD_VERIFIED dimensions meet VERIFIED_WATER_SYSTEM_CONTEXT."""
    seasonal = (dims.get("seasonal_reliability") or {}).get("status")
    access = (dims.get("livestock_accessibility") or {}).get("status")
    legal = dims.get("legal_access") or {}
    cq = dims.get("capacity_and_quality") or {}
    capacity = cq.get("capacity") or {}
    water_quality = cq.get("water_quality") or {}
    return (
        seasonal in {"perennial", "intermittent", "ephemeral"}
        and access in {"supported", "constrained"}
        and legal.get("status") in {"verified", "not_applicable"}
        and bool(legal.get("basis"))
        and capacity.get("status") in {"measured", "documented"}
        and capacity.get("value") is not None
        and bool(capacity.get("unit"))
        and bool(capacity.get("scenario_reference"))
        and water_quality.get("status") == "verified"
        and isinstance(water_quality.get("evidence_source_ids"), list)
        and bool(water_quality.get("evidence_source_ids"))
    )


def factor_input_quality_from_ingestion(
    *,
    verification_levels: list[str],
    has_conflict: bool,
    dimensions_by_level: list[Mapping[str, Any]] | None = None,
) -> str:
    """Map ingestion outcomes to F03 Factor input_quality_state."""
    if has_conflict:
        return "CONFLICTING_SOURCES"
    field_dims = [
        dims
        for level, dims in zip(
            verification_levels, dimensions_by_level or [{}] * len(verification_levels)
        )
        if level == "FIELD_VERIFIED_LIVESTOCK_WATER"
    ]
    if any(system_context_complete(dims) for dims in field_dims):
        return "VERIFIED_WATER_SYSTEM_CONTEXT"
    if any(level == "FIELD_VERIFIED_LIVESTOCK_WATER" for level in verification_levels):
        return "PHYSICAL_SOURCE_UNVERIFIED_SYSTEM"
    if verification_levels:
        return "MAPPED_CANDIDATES_ONLY"
    return "MISSING"


def normalize_candidate_record(package: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize an evidence package into an evaluate_promotion record."""
    dims = deepcopy(package.get("dimensions") or {})
    evidence_class = package.get("evidence_class")
    as_of = (
        package.get("as_of")
        or ((package.get("verification_level") or {}).get("as_of"))
        or package.get("observed_or_fetched_at")
    )
    linkage = package.get("candidate_linkage") or {}
    parcel = package.get("parcel_context") or {}
    hashes = package.get("evidence_hashes") or {}

    # Attach identity linkage fields when absent.
    identity = dims.setdefault("feature_identity", {})
    identity.setdefault(
        "geometry_or_point_reference", linkage.get("geometry_or_point_hash")
    )
    if package.get("source_feature_id"):
        identity.setdefault("source_feature_id", package.get("source_feature_id"))

    presence = dims.setdefault("physical_presence", {})
    if evidence_class == "MIXED":
        basis = presence.get("qualified_field_basis") or package.get("qualified_field_basis")
        if basis:
            presence["qualified_field_basis"] = basis

    record = {
        "candidate_id": package.get("candidate_id"),
        "source_feature_id": package.get("source_feature_id"),
        "prior_level": package.get("prior_level") or "REMOTELY_SUPPORTED_CANDIDATE",
        "attempted_level": package.get("attempted_level"),
        "evidence_class": evidence_class,
        "qualified_field_basis_required": bool(
            package.get("qualified_field_basis_required")
            or evidence_class == "MIXED"
            or (presence.get("qualified_field_basis"))
        ),
        "unresolved_material_conflict": bool(package.get("unresolved_material_conflict")),
        "dimensions": dims,
        "verification_level": {
            "evidence_class": evidence_class,
            "as_of": as_of,
            "qualified_field_basis_required": bool(
                package.get("qualified_field_basis_required") or evidence_class == "MIXED"
            ),
        },
        "provenance": {
            "candidate_id": package.get("candidate_id"),
            "geometry_or_point_hash": linkage.get("geometry_or_point_hash"),
            "source_reference": linkage.get("source_reference"),
            "fetched_or_observed_at": package.get("observed_or_fetched_at"),
            "response_or_artifact_hash_or_record_hash": hashes.get(
                "response_or_artifact_hash_or_record_hash"
            ),
            "geometry_hash_of_parcel_context": parcel.get("parcel_geometry_hash"),
            "reviewer_or_adapter_id": package.get("reviewer_or_adapter_id"),
        },
    }
    return record


def ingest_field_evidence_package(package: Mapping[str, Any]) -> dict[str, Any]:
    """Ingest one field/operator evidence package and evaluate promotion.

    Never writes Land Facts. Rejects live XPV parcel targets.
    """
    package = deepcopy(dict(package))
    validation = validate_evidence_package(package)
    geometry = detect_geometry_mismatch(package)
    conflicts = detect_material_conflicts(package)
    freshness = assess_freshness(package)

    result: dict[str, Any] = {
        "ingestion_spec_version": INGESTION_SPEC_VERSION,
        "contract_version": CONTRACT_VERSION,
        "package_id": package.get("package_id"),
        "fixture_type": package.get("fixture_type"),
        "evidence_use_limit": package.get("evidence_use_limit"),
        "parcel_id": (package.get("parcel_context") or {}).get("parcel_id"),
        "candidate_id": package.get("candidate_id"),
        "evidence_class": package.get("evidence_class"),
        "accepted": False,
        "live_parcel_write_attempted": is_live_parcel_id(
            (package.get("parcel_context") or {}).get("parcel_id")
        ),
        "package_validation": validation,
        "geometry_check": geometry,
        "conflict_check": conflicts,
        "freshness": freshness,
        "limitations": list(freshness.get("limitations") or []),
        "prior_level": package.get("prior_level"),
        "verification_level": None,
        "reason_codes": [],
        "factor_input_quality_state": None,
        "ranking_effect": "NONE",
        "suitability_thresholds_added": False,
        "cow_sheep_ranking_added": False,
        "wrote_to_live_parcel_profile": False,
    }

    if result["live_parcel_write_attempted"]:
        result["reason_codes"].append("LIVE_PARCEL_WRITE_PROHIBITED")
        result["factor_input_quality_state"] = "MAPPED_CANDIDATES_ONLY"
        return result

    if not validation["ok"]:
        result["reason_codes"].append("EVIDENCE_PACKAGE_INVALID")
        result["reason_codes"].extend(validation["blocking_issues"][:8])
        result["verification_level"] = package.get("prior_level") or "MAPPED_CANDIDATE"
        result["factor_input_quality_state"] = "MAPPED_CANDIDATES_ONLY"
        return result

    if geometry["mismatch"]:
        result["reason_codes"].append("GEOMETRY_MISMATCH_REQUIRES_RELINK")
        if geometry.get("reason"):
            result["reason_codes"].append(geometry["reason"])
        result["verification_level"] = package.get("prior_level") or "MAPPED_CANDIDATE"
        result["factor_input_quality_state"] = "MAPPED_CANDIDATES_ONLY"
        result["accepted"] = False
        return result

    if conflicts["has_conflict"]:
        result["reason_codes"].append("CONFLICTING_SOURCES")
        result["verification_level"] = package.get("prior_level") or "MAPPED_CANDIDATE"
        result["factor_input_quality_state"] = "CONFLICTING_SOURCES"
        result["accepted"] = True  # package accepted as conflict evidence
        result["limitations"].append("Material source conflict; promotion held/demoted.")
        return result

    if freshness["stale"] and not freshness["allows_field_verified_with_limitation"]:
        result["reason_codes"].append("STALE_EVIDENCE_LIMITATION_REQUIRED")
        result["verification_level"] = package.get("prior_level") or "MAPPED_CANDIDATE"
        result["factor_input_quality_state"] = "MAPPED_CANDIDATES_ONLY"
        return result

    if freshness["stale"]:
        result["reason_codes"].append("STALE_EVIDENCE_RECORDED_AS_LIMITATION")
        result["limitations"] = freshness["limitations"]

    record = normalize_candidate_record(package)
    if freshness["stale"]:
        record.setdefault("dimensions", {}).setdefault("physical_presence", {})
        # Keep presence; attach limitation visibility only.
        record["limitations"] = result["limitations"]

    promotion = evaluate_promotion(record)
    result["promotion_evaluation"] = promotion
    result["verification_level"] = promotion["verification_level"]
    result["reason_codes"].extend(promotion.get("reason_codes") or [])
    result["accepted"] = True

    # Incomplete promotion attempts stay at prior/defensible level.
    if package.get("attempted_level") == "FIELD_VERIFIED_LIVESTOCK_WATER":
        if promotion["verification_level"] != "FIELD_VERIFIED_LIVESTOCK_WATER":
            result["reason_codes"].append("INCOMPLETE_FIELD_VERIFIED_PROMOTION_REJECTED")

    result["factor_input_quality_state"] = factor_input_quality_from_ingestion(
        verification_levels=[promotion["verification_level"]],
        has_conflict=False,
        dimensions_by_level=[record.get("dimensions") or {}],
    )
    result["normalized_record"] = {
        "candidate_id": record.get("candidate_id"),
        "prior_level": record.get("prior_level"),
        "evidence_class": record.get("evidence_class"),
        "verification_level": promotion["verification_level"],
        "dimensions": record.get("dimensions"),
        "provenance": record.get("provenance"),
        "limitations": result["limitations"],
    }
    return result


def run_synthetic_ingestion_suite(packages: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Evaluate a list of synthetic packages; refuse any live parcel write."""
    outcomes = []
    for package in packages:
        outcomes.append(ingest_field_evidence_package(package))

    levels = [o.get("verification_level") for o in outcomes if o.get("verification_level")]
    has_conflict = any(
        o.get("factor_input_quality_state") == "CONFLICTING_SOURCES" for o in outcomes
    )
    dims = [
        (o.get("normalized_record") or {}).get("dimensions") or {}
        for o in outcomes
        if o.get("verification_level") == "FIELD_VERIFIED_LIVESTOCK_WATER"
    ]
    # Aggregate factor state prefers conflict, then richest verified context among accepted.
    aggregate_state = factor_input_quality_from_ingestion(
        verification_levels=[
            o["verification_level"]
            for o in outcomes
            if o.get("accepted") and o.get("verification_level")
        ],
        has_conflict=has_conflict,
        dimensions_by_level=[
            (o.get("normalized_record") or {}).get("dimensions") or {}
            for o in outcomes
            if o.get("accepted") and o.get("verification_level")
        ],
    )

    live_writes = [o for o in outcomes if o.get("wrote_to_live_parcel_profile")]
    live_attempts = [o for o in outcomes if o.get("live_parcel_write_attempted")]

    return {
        "suite_id": "F03_FIELD_EVIDENCE_SYNTHETIC_DEMO",
        "ingestion_spec_version": INGESTION_SPEC_VERSION,
        "contract_version": CONTRACT_VERSION,
        "outcome_count": len(outcomes),
        "outcomes": outcomes,
        "level_histogram": {
            level: levels.count(level) for level in sorted({x for x in levels if x})
        },
        "aggregate_factor_input_quality_state": aggregate_state,
        "field_verified_count": levels.count("FIELD_VERIFIED_LIVESTOCK_WATER"),
        "live_parcel_write_attempts": len(live_attempts),
        "live_parcel_profiles_written": len(live_writes),
        "runtime_rules_changed": False,
        "ranking_effect": "NONE",
        "suitability_thresholds_added": False,
        "cow_sheep_ranking_added": False,
        "synthetic_live_separation_ok": len(live_writes) == 0 and len(live_attempts) == 0,
    }
