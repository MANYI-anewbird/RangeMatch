#!/usr/bin/env python3
"""Build synthetic F03 field-evidence fixtures (TEST_ONLY). Does not touch live parcels."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "test-data/f03_field_evidence_fixtures"

DIGEST_A = "a" * 64
PARCEL_HASH = "f" * 64
PARCEL_HASH_CHANGED = "1" * 64
CANDIDATE_HASH = "2" * 64


def markers() -> dict:
    return {
        "fixture_type": "SYNTHETIC_ENGINEERING_TEST",
        "evidence_use_limit": "TEST_ONLY",
    }


def base_package(**overrides):
    pkg = {
        **markers(),
        "package_id": "SYNTH_PKG_BASE",
        "evidence_class": "FIELD_OBSERVATION",
        "candidate_id": "SYNTHETIC:pond:001",
        "source_feature_id": "SYNTH_FEAT_001",
        "prior_level": "REMOTELY_SUPPORTED_CANDIDATE",
        "attempted_level": "FIELD_VERIFIED_LIVESTOCK_WATER",
        "parcel_context": {
            "parcel_id": "SYNTHETIC_PARCEL_F03_001",
            "parcel_geometry_hash": PARCEL_HASH,
        },
        "candidate_linkage": {
            "geometry_or_point_hash": CANDIDATE_HASH,
            "source_reference": "SYNTHETIC_FIELD_LOG:visit_001",
            "linked_parcel_geometry_hash": PARCEL_HASH,
        },
        "evidence_hashes": {
            "response_or_artifact_hash_or_record_hash": DIGEST_A,
        },
        "observed_or_fetched_at": "2026-07-01T15:00:00Z",
        "as_of": "2026-07-01T15:00:00Z",
        "review_date": "2026-08-08",
        "reviewer_or_adapter_id": "rangematch.f03_field_evidence_test/v1",
        "limitations": [],
        "dimensions": {
            "feature_identity": {
                "type": "pond",
                "geometry_or_point_reference": CANDIDATE_HASH,
                "source_feature_id": "SYNTH_FEAT_001",
            },
            "physical_presence": {
                "status": "confirmed",
                "source": "field",
                "observation_date": "2026-07-01",
            },
            "seasonal_reliability": {
                "status": "intermittent",
                "observation_period": "2024-2026",
            },
            "livestock_accessibility": {"status": "supported"},
            "capacity_and_quality": {
                "capacity": {
                    "status": "documented",
                    "value": 25000,
                    "unit": "gallon_storage",
                    "scenario_reference": "summer_stock_water_2026",
                    "unknown_rationale": None,
                },
                "water_quality": {
                    "status": "verified",
                    "diligence_required": False,
                    "evidence_source_ids": ["SYNTH_LAB_RESULT_001"],
                },
            },
            "legal_access": {
                "status": "verified",
                "basis": "owned_deed_stock_water",
            },
        },
    }
    for key, value in overrides.items():
        if key == "dimensions" and isinstance(value, dict):
            dims = deepcopy(pkg["dimensions"])
            for dkey, dval in value.items():
                if isinstance(dval, dict) and isinstance(dims.get(dkey), dict):
                    merged = deepcopy(dims[dkey])
                    merged.update(dval)
                    dims[dkey] = merged
                else:
                    dims[dkey] = dval
            pkg["dimensions"] = dims
        else:
            pkg[key] = value
    return pkg


def write(name: str, package: dict) -> None:
    path = OUT / name
    path.write_text(json.dumps(package, indent=2) + "\n")
    print("wrote", path.relative_to(PROJECT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    write(
        "valid_field_verified_livestock_water.json",
        base_package(
            package_id="SYNTH_PKG_VALID_FIELD_VERIFIED",
            scenario_label="valid_FIELD_VERIFIED_LIVESTOCK_WATER",
        ),
    )

    incomplete = base_package(
        package_id="SYNTH_PKG_PHYSICAL_SOURCE_UNVERIFIED",
        scenario_label="PHYSICAL_SOURCE_UNVERIFIED_SYSTEM",
        dimensions={
            "capacity_and_quality": {
                "capacity": {
                    "status": "unknown",
                    "value": None,
                    "unit": None,
                    "scenario_reference": None,
                    "unknown_rationale": (
                        "Pond storage not gauged during field visit; "
                        "operator estimates only."
                    ),
                },
                "water_quality": {
                    "status": "unknown",
                    "diligence_required": True,
                    "evidence_source_ids": [],
                },
            }
        },
    )
    write("physical_source_unverified_system.json", incomplete)

    write(
        "verified_water_system_context.json",
        base_package(
            package_id="SYNTH_PKG_VERIFIED_SYSTEM_CONTEXT",
            scenario_label="VERIFIED_WATER_SYSTEM_CONTEXT",
            evidence_class="OPERATOR_OWNER_OPERATIONAL_RECORD",
            dimensions={
                "physical_presence": {
                    "status": "confirmed",
                    "source": "operator_record_equivalent",
                    "observation_date": "2026-06-15",
                }
            },
        ),
    )

    write(
        "conflicting_sources.json",
        base_package(
            package_id="SYNTH_PKG_CONFLICTING_SOURCES",
            scenario_label="CONFLICTING_SOURCES",
            unresolved_material_conflict=True,
            material_conflicts=[
                {
                    "conflict_id": "OPERATOR_ACTIVE_TROUGH_VS_FIELD_ABSENT",
                    "dimensions": ["physical_presence"],
                }
            ],
            physical_use_claimed=True,
            legal_access_denied=True,
        ),
    )

    missing_legal = base_package(
        package_id="SYNTH_PKG_MISSING_LEGAL_ACCESS",
        scenario_label="missing_legal_access",
    )
    missing_legal["dimensions"]["legal_access"] = {"status": "unresolved"}
    write("missing_legal_access.json", missing_legal)

    missing_rationale = base_package(
        package_id="SYNTH_PKG_MISSING_CAPACITY_RATIONALE",
        scenario_label="missing_capacity_rationale",
        dimensions={
            "capacity_and_quality": {
                "capacity": {
                    "status": "unknown",
                    "value": None,
                    "unit": None,
                    "scenario_reference": None,
                    "unknown_rationale": None,
                },
                "water_quality": {
                    "status": "unknown",
                    "diligence_required": True,
                    "evidence_source_ids": [],
                },
            }
        },
    )
    write("missing_capacity_rationale.json", missing_rationale)

    write(
        "invalid_evidence_hash.json",
        base_package(
            package_id="SYNTH_PKG_INVALID_HASH",
            scenario_label="invalid_evidence_hash",
            evidence_hashes={"response_or_artifact_hash_or_record_hash": "tooshort"},
        ),
    )

    write(
        "stale_evidence.json",
        base_package(
            package_id="SYNTH_PKG_STALE_EVIDENCE",
            scenario_label="stale_evidence",
            observed_or_fetched_at="2023-01-15T12:00:00Z",
            as_of="2026-08-08T00:00:00Z",
            review_date="2026-08-08",
            staleness_review_note=(
                "Field note older than 365 days retained with explicit staleness "
                "limitation; operator corroborated continued pond use in 2026."
            ),
            limitations=[
                "STALE_FIELD_OR_OPERATOR_EVIDENCE retained with review note"
            ],
            allow_stale_with_limitation=True,
        ),
    )

    write(
        "geometry_mismatch.json",
        base_package(
            package_id="SYNTH_PKG_GEOMETRY_MISMATCH",
            scenario_label="geometry_mismatch",
            expected_parcel_geometry_hash=PARCEL_HASH,
            parcel_context={
                "parcel_id": "SYNTHETIC_PARCEL_F03_001",
                "parcel_geometry_hash": PARCEL_HASH_CHANGED,
            },
            candidate_linkage={
                "geometry_or_point_hash": CANDIDATE_HASH,
                "source_reference": "SYNTHETIC_FIELD_LOG:visit_001",
                "linked_parcel_geometry_hash": PARCEL_HASH,
            },
        ),
    )

    write(
        "reviewed_equivalent_field_verified.json",
        base_package(
            package_id="SYNTH_PKG_REVIEWED_EQUIVALENT",
            scenario_label="REVIEWED_EQUIVALENT_FIELD_VERIFIED",
            evidence_class="REVIEWED_EQUIVALENT",
            dimensions={
                "physical_presence": {
                    "status": "confirmed",
                    "source": "reviewed_equivalent",
                    "observation_date": "2026-07-10",
                    "review_note": (
                        "Synthetic reviewed-equivalent package treated as "
                        "field/operational equivalent for TEST_ONLY demo."
                    ),
                }
            },
        ),
    )

    write(
        "mixed_with_qualified_field_basis.json",
        base_package(
            package_id="SYNTH_PKG_MIXED_QUALIFIED",
            scenario_label="MIXED_with_qualified_field_basis",
            evidence_class="MIXED",
            qualified_field_basis_required=True,
            dimensions={
                "physical_presence": {
                    "status": "confirmed",
                    "source": "reviewed_equivalent",
                    "qualified_field_basis": {
                        "source": "field",
                        "as_of": "2026-07-20T18:00:00Z",
                        "record_or_observation_hash": "9" * 64,
                    },
                }
            },
        ),
    )

    write(
        "mapped_to_field_verified_jump_rejected.json",
        base_package(
            package_id="SYNTH_PKG_SKIP_REMOTE_REJECTED",
            scenario_label="mapped_to_field_verified_jump_rejected",
            prior_level="MAPPED_CANDIDATE",
            attempted_level="FIELD_VERIFIED_LIVESTOCK_WATER",
        ),
    )

    manifest = {
        "fixture_type": "SYNTHETIC_ENGINEERING_TEST",
        "evidence_use_limit": "TEST_ONLY",
        "live_parcels_touched": False,
        "fixtures": sorted(p.name for p in OUT.glob("*.json")),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("wrote", (OUT / "manifest.json").relative_to(PROJECT))


if __name__ == "__main__":
    main()
