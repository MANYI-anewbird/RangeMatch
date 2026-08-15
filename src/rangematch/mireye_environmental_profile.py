"""Mireye Environmental Profile — Phase 1 projector and catalog drift gate.

Builds a schema-valid cattle-environment profile from confirmed parcel refs and
Mireye field payloads. Does not invoke F01-F08 or change the Advisor live path.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from rangematch.unified_output import sha256_canonical

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "docs" / "mireye_cattle_environment_field_manifest.json"
SCHEMA_PATH = (
    REPO_ROOT / "docs" / "schemas" / "mireye_environmental_profile.schema.json"
)
PINNED_CATALOG_PATH = REPO_ROOT / "mireye" / "fixtures" / "field_catalog_v0.14.0.json"

SCHEMA_VERSION = "mireye_environmental_profile@1.0.0"
PROJECTOR_ID = "MIREYE_ENVIRONMENTAL_PROFILE_PROJECTOR@1.0.0"
PROVIDER = "MIREYE"

SPATIAL_POINT = "POINT"
SPATIAL_PARCEL = "PARCEL"
SPATIAL_CONTEXT = "CONTEXT"
ALLOWED_SPATIAL = frozenset({SPATIAL_POINT, SPATIAL_PARCEL, SPATIAL_CONTEXT})

STATUS_RETRIEVED = "RETRIEVED"
STATUS_PARTIAL = "PARTIAL"
STATUS_MISSING = "MISSING"
STATUS_SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
STATUS_NOT_APPLICABLE = "NOT_APPLICABLE"
STATUS_REJECTED = "REJECTED_BY_SEMANTICS_GATE"

BUYER_VISIBLE_STATUSES = frozenset({STATUS_RETRIEVED, STATUS_PARTIAL})


class MireyeEnvironmentalProfileError(ValueError):
    """Fail-closed profile / catalog error."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


@lru_cache(maxsize=1)
def load_field_manifest() -> dict[str, Any]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    stored = payload.get("manifest_hash")
    recomputed = compute_manifest_hash(payload)
    if stored != recomputed:
        raise MireyeEnvironmentalProfileError(
            "manifest_hash_mismatch",
            f"stored={stored} recomputed={recomputed}",
        )
    return payload


@lru_cache(maxsize=1)
def load_profile_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def compute_manifest_hash(manifest: Mapping[str, Any]) -> str:
    body = {k: v for k, v in dict(manifest).items() if k != "manifest_hash"}
    return sha256_canonical(body)


def manifest_field_index(
    manifest: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    doc = manifest or load_field_manifest()
    return {str(item["field_id"]): dict(item) for item in doc["fields"]}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _field_payload(raw: Any) -> dict[str, Any]:
    """Normalize a Mireye field value into a dict with optional metadata."""
    if raw is None:
        return {"value": None}
    if isinstance(raw, Mapping):
        return dict(raw)
    return {"value": raw}


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def resolve_spatial_semantics(
    *,
    expected: str,
    returned: str | None,
) -> tuple[str, str | None]:
    """Return (effective_semantics, rejection_reason). Never promote POINT/CONTEXT to PARCEL."""
    if expected not in ALLOWED_SPATIAL:
        return expected, f"invalid_expected_semantics:{expected}"
    if returned is None or returned == "":
        return expected, None
    if returned not in ALLOWED_SPATIAL:
        return expected, f"invalid_returned_semantics:{returned}"
    if returned == expected:
        return expected, None
    # Never silently promote weaker evidence to PARCEL.
    if expected == SPATIAL_PARCEL and returned != SPATIAL_PARCEL:
        return returned, f"refused_promotion:{returned}_to_PARCEL"
    if returned == SPATIAL_PARCEL and expected != SPATIAL_PARCEL:
        return expected, f"rejected_unexpected_parcel_claim:expected_{expected}"
    # Downgrade / mismatch between POINT and CONTEXT is recorded, not promoted.
    return returned, f"semantics_mismatch:expected_{expected}_got_{returned}"


def assign_canonical_for_parcel_facts(
    *,
    expected_semantics: str,
    effective_semantics: str,
    rejection_reason: str | None,
    confirmed_geometry_hash: str,
    observation_geometry_hash: str | None,
) -> bool:
    if rejection_reason:
        return False
    if expected_semantics != SPATIAL_PARCEL:
        return False
    if effective_semantics != SPATIAL_PARCEL:
        return False
    if not confirmed_geometry_hash:
        return False
    if observation_geometry_hash != confirmed_geometry_hash:
        return False
    return True


def evaluate_catalog_drift(
    catalog: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare a live or fixture catalog against the frozen cattle-environment manifest.

    Major version drift or missing/mismatched required fields fail closed.
    """
    doc = manifest or load_field_manifest()
    pinned_version = str((doc.get("catalog_ref") or {}).get("version") or "")
    observed_version = str(catalog.get("version") or "")
    pinned_major = _major(pinned_version)
    observed_major = _major(observed_version)

    catalog_fields = {
        str(item["name"]): item
        for item in (catalog.get("fields") or [])
        if isinstance(item, Mapping) and item.get("name")
    }

    missing_fields: list[str] = []
    unit_mismatches: list[dict[str, Any]] = []
    type_mismatches: list[dict[str, Any]] = []
    for field in doc["fields"]:
        field_id = str(field["field_id"])
        observed = catalog_fields.get(field_id)
        if observed is None:
            if field.get("required"):
                missing_fields.append(field_id)
            continue
        if field.get("expected_unit") != observed.get("unit"):
            unit_mismatches.append(
                {
                    "field_id": field_id,
                    "expected": field.get("expected_unit"),
                    "observed": observed.get("unit"),
                }
            )
        if field.get("expected_type") != observed.get("type"):
            type_mismatches.append(
                {
                    "field_id": field_id,
                    "expected": field.get("expected_type"),
                    "observed": observed.get("type"),
                }
            )

    fail_closed = False
    reasons: list[str] = []
    if pinned_major is not None and observed_major is not None and observed_major != pinned_major:
        fail_closed = True
        reasons.append(
            f"major_version_drift:pinned={pinned_version}:observed={observed_version}"
        )
    if missing_fields:
        fail_closed = True
        reasons.append("missing_required_fields:" + ",".join(sorted(missing_fields)))
    required_ids = {f["field_id"] for f in doc["fields"] if f.get("required")}
    if any(m["field_id"] in required_ids for m in unit_mismatches):
        fail_closed = True
        reasons.append("required_unit_mismatch")
    if any(m["field_id"] in required_ids for m in type_mismatches):
        fail_closed = True
        reasons.append("required_type_mismatch")

    return {
        "compatible": not fail_closed,
        "fail_closed": fail_closed,
        "pinned_catalog_version": pinned_version,
        "observed_catalog_version": observed_version or None,
        "pinned_major": pinned_major,
        "observed_major": observed_major,
        "missing_fields": missing_fields,
        "unit_mismatches": unit_mismatches,
        "type_mismatches": type_mismatches,
        "reasons": reasons,
        "manifest_hash": doc.get("manifest_hash"),
    }


def _major(version: str) -> int | None:
    if not version:
        return None
    head = version.split(".", 1)[0]
    return int(head) if head.isdigit() else None


def project_mireye_environmental_profile(
    *,
    run_id: str,
    parcel_ref: Mapping[str, Any],
    field_values: Mapping[str, Any],
    fetched_at: str | None = None,
    returned_spatial_semantics: Mapping[str, str] | None = None,
    unavailable_fields: Sequence[str] | None = None,
    built_at: str | None = None,
    manifest: Mapping[str, Any] | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Project Mireye field payloads into a cattle-environment Profile.

    ``field_values`` maps field_id -> scalar or Mireye field object
    ``{value, unit, source, source_url, dataset_vintage, fetched_at, confidence, status}``.
    """
    doc = dict(manifest) if manifest is not None else load_field_manifest()
    if not run_id or not str(run_id).strip():
        raise MireyeEnvironmentalProfileError("missing_run_id", "run_id is required")

    parcel_resolution_id = str(parcel_ref.get("parcel_resolution_id") or "").strip()
    geometry_hash = str(parcel_ref.get("geometry_hash") or "").strip()
    confirmed = parcel_ref.get("confirmed")
    if not parcel_resolution_id or not geometry_hash:
        raise MireyeEnvironmentalProfileError(
            "invalid_parcel_ref",
            "parcel_resolution_id and geometry_hash are required",
        )
    if confirmed is not True:
        raise MireyeEnvironmentalProfileError(
            "parcel_not_confirmed",
            "Profile requires confirmed=true parcel_ref",
        )

    unavailable = {str(x) for x in (unavailable_fields or [])}
    returned_sem = {
        str(k): str(v) for k, v in dict(returned_spatial_semantics or {}).items()
    }
    default_fetched_at = fetched_at

    observations: list[dict[str, Any]] = []
    for field_spec in doc["fields"]:
        field_id = str(field_spec["field_id"])
        expected_sem = str(field_spec["expected_spatial_semantics"])
        domain = str(field_spec["domain"])
        payload = _field_payload(field_values.get(field_id))
        value = payload.get("value", payload.get("val"))
        obs_geom = (
            payload.get("geometry_hash")
            or payload.get("parcel_geometry_hash")
            or payload.get("geometry_hash_ref")
        )
        if obs_geom is not None:
            obs_geom = str(obs_geom)

        returned = returned_sem.get(field_id) or payload.get("spatial_semantics")
        if returned is not None:
            returned = str(returned)
        effective_sem, rejection = resolve_spatial_semantics(
            expected=expected_sem, returned=returned
        )

        status: str
        rejection_reason = rejection
        hard_reject = bool(
            rejection_reason
            and (
                rejection_reason.startswith("refused_promotion:")
                or rejection_reason.startswith("rejected_unexpected_parcel_claim:")
                or rejection_reason.startswith("invalid_returned_semantics:")
                or rejection_reason.startswith("invalid_expected_semantics:")
            )
        )

        if field_id in unavailable:
            status = STATUS_SOURCE_UNAVAILABLE
            value = None
        elif hard_reject:
            status = STATUS_REJECTED
            value = None
        elif _is_empty_value(value):
            status = STATUS_MISSING
            value = None
        elif str(payload.get("status") or "").upper() == STATUS_PARTIAL:
            status = STATUS_PARTIAL
        else:
            status = STATUS_RETRIEVED

        if (
            expected_sem == SPATIAL_PARCEL
            and status in BUYER_VISIBLE_STATUSES
            and effective_sem == SPATIAL_PARCEL
            and obs_geom is None
        ):
            status = STATUS_REJECTED
            rejection_reason = "parcel_field_missing_geometry_hash"
            value = None

        canonical = assign_canonical_for_parcel_facts(
            expected_semantics=expected_sem,
            effective_semantics=effective_sem,
            rejection_reason=rejection_reason if status == STATUS_REJECTED else None,
            confirmed_geometry_hash=geometry_hash,
            observation_geometry_hash=obs_geom,
        )
        # Soft POINT/CONTEXT mismatches stay non-canonical even when retrieved.
        if rejection_reason and rejection_reason.startswith("semantics_mismatch:"):
            canonical = False

        observation = {
            "observation_id": f"MIREYE_{field_id}",
            "field_id": field_id,
            "domain": domain,
            "value": value,
            "unit": payload.get("unit", field_spec.get("expected_unit")),
            "provider": PROVIDER,
            "source_name": payload.get("source")
            or payload.get("source_name")
            or field_spec.get("catalog_source"),
            "source_url": payload.get("source_url")
            or field_spec.get("catalog_source_url"),
            "dataset_vintage": payload.get("dataset_vintage"),
            "fetched_at": payload.get("fetched_at") or default_fetched_at,
            "confidence": payload.get("confidence"),
            "status": status,
            "spatial_semantics": (
                (returned or expected_sem)
                if status == STATUS_REJECTED
                else effective_sem
            ),
            "temporal_semantics": payload.get("temporal_semantics")
            or field_spec.get("expected_temporal_semantics"),
            "canonical_for_parcel_facts": bool(canonical),
            "geometry_hash_ref": (
                obs_geom if expected_sem == SPATIAL_PARCEL else geometry_hash
            ),
            "rejection_reason": rejection_reason,
            "notes": payload.get("notes") or field_spec.get("notes"),
        }
        observations.append(observation)

    coverage = _build_coverage_summary(observations, requested_count=len(doc["fields"]))
    catalog_ref = {
        "version": str((doc.get("catalog_ref") or {}).get("version") or ""),
        "manifest_hash": str(doc.get("manifest_hash") or ""),
        "catalog_file_sha256": (doc.get("catalog_ref") or {}).get("catalog_file_sha256"),
        "etag": (doc.get("catalog_ref") or {}).get("etag"),
    }
    profile: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(run_id),
        "parcel_ref": {
            "parcel_resolution_id": parcel_resolution_id,
            "geometry_hash": geometry_hash,
            "confirmed": True,
        },
        "catalog_ref": catalog_ref,
        "observations": observations,
        "coverage_summary": coverage,
        "provenance": {
            "projector_id": PROJECTOR_ID,
            "provider": PROVIDER,
            "built_at": built_at or _utc_now(),
            "limitations": [
                "point_and_context_fields_are_not_parcel_wide_proof",
                "null_is_not_evidence",
                "canonical_authority_is_per_field",
            ],
        },
    }
    profile["profile_hash"] = compute_profile_hash(profile)
    if validate:
        validate_mireye_environmental_profile(profile)
    return profile


def _build_coverage_summary(
    observations: Sequence[Mapping[str, Any]],
    *,
    requested_count: int,
) -> dict[str, Any]:
    retrieved_by_domain: dict[str, int] = {}
    retrieved = 0
    missing = 0
    point_count = 0
    parcel_count = 0
    context_count = 0
    rejected = 0
    for obs in observations:
        status = obs.get("status")
        sem = obs.get("spatial_semantics")
        if status in BUYER_VISIBLE_STATUSES:
            retrieved += 1
            domain = str(obs.get("domain") or "UNKNOWN")
            retrieved_by_domain[domain] = retrieved_by_domain.get(domain, 0) + 1
            if sem == SPATIAL_POINT:
                point_count += 1
            elif sem == SPATIAL_PARCEL:
                parcel_count += 1
            elif sem == SPATIAL_CONTEXT:
                context_count += 1
        elif status == STATUS_MISSING:
            missing += 1
        elif status == STATUS_REJECTED:
            rejected += 1
    return {
        "requested_field_count": requested_count,
        "retrieved_field_count": retrieved,
        "missing_field_count": missing,
        "point_count": point_count,
        "parcel_count": parcel_count,
        "context_count": context_count,
        "rejected_by_semantics_count": rejected,
        "retrieved_by_domain": dict(sorted(retrieved_by_domain.items())),
    }


def compute_profile_hash(profile: Mapping[str, Any]) -> str:
    body = {k: v for k, v in dict(profile).items() if k != "profile_hash"}
    return sha256_canonical(body)


def validate_mireye_environmental_profile(profile: Mapping[str, Any]) -> None:
    schema = load_profile_schema()
    errors = sorted(
        Draft202012Validator(schema).iter_errors(dict(profile)),
        key=lambda err: list(err.path),
    )
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.path) or "<root>"
        raise MireyeEnvironmentalProfileError(
            "schema_validation_failed",
            f"{path}: {first.message}",
        )
    # Extra semantic gate: POINT/CONTEXT must never be canonical parcel facts.
    for obs in profile.get("observations") or []:
        if not isinstance(obs, Mapping):
            continue
        if obs.get("canonical_for_parcel_facts") is True:
            if obs.get("spatial_semantics") != SPATIAL_PARCEL:
                raise MireyeEnvironmentalProfileError(
                    "canonical_semantics_violation",
                    f"{obs.get('field_id')} is canonical but not PARCEL",
                )


def buyer_evidence_rows(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Appendix-safe rows: only retrieved/partial non-empty observations."""
    rows: list[dict[str, Any]] = []
    for obs in profile.get("observations") or []:
        if not isinstance(obs, Mapping):
            continue
        if obs.get("status") not in BUYER_VISIBLE_STATUSES:
            continue
        if _is_empty_value(obs.get("value")):
            continue
        rows.append(dict(obs))
    return rows


def load_pinned_catalog() -> dict[str, Any]:
    return json.loads(PINNED_CATALOG_PATH.read_text(encoding="utf-8"))
