#!/usr/bin/env python3
"""Deterministic F03 field-evidence demo using synthetic fixtures only.

Does not write to live XPV parcel profiles. field_verified_count on real
parcels remains 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from rangematch.f03_field_evidence import (  # noqa: E402
    LIVE_PARCEL_IDS,
    run_synthetic_ingestion_suite,
)

FIXTURE_DIR = PROJECT / "test-data/f03_field_evidence_fixtures"
OUT_DIR = PROJECT / "test-data/f03_field_evidence_demo"
LIVE_REMOTE_ROOT = PROJECT / "test-data/cross-parcel-validation"

DEMO_FIXTURES = [
    "valid_field_verified_livestock_water.json",
    "physical_source_unverified_system.json",
    "verified_water_system_context.json",
    "conflicting_sources.json",
    "missing_legal_access.json",
    "missing_capacity_rationale.json",
    "invalid_evidence_hash.json",
    "stale_evidence.json",
    "geometry_mismatch.json",
    "reviewed_equivalent_field_verified.json",
    "mixed_with_qualified_field_basis.json",
    "mapped_to_field_verified_jump_rejected.json",
]


def load_packages() -> list[dict]:
    packages = []
    for name in DEMO_FIXTURES:
        path = FIXTURE_DIR / name
        packages.append(json.loads(path.read_text()))
    return packages


def confirm_live_parcels_untouched() -> dict:
    checks = []
    for parcel_id in sorted(LIVE_PARCEL_IDS):
        path = LIVE_REMOTE_ROOT / parcel_id / "f03_remote_pilot" / "remote_pilot_result.json"
        if not path.exists():
            checks.append(
                {
                    "parcel_id": parcel_id,
                    "remote_pilot_result_present": False,
                    "field_verified_count": None,
                }
            )
            continue
        payload = json.loads(path.read_text())
        checks.append(
            {
                "parcel_id": parcel_id,
                "remote_pilot_result_present": True,
                "field_verified_count": payload.get("field_verified_count"),
                "unchanged_zero": payload.get("field_verified_count") == 0,
            }
        )
    return {
        "all_field_verified_counts_zero": all(
            c.get("unchanged_zero") for c in checks if c.get("remote_pilot_result_present")
        ),
        "parcels": checks,
    }


def main() -> None:
    packages = load_packages()
    suite = run_synthetic_ingestion_suite(packages)
    live = confirm_live_parcels_untouched()

    # Explicit state-transition table for the demo.
    transitions = []
    for package, outcome in zip(packages, suite["outcomes"]):
        transitions.append(
            {
                "fixture": package.get("scenario_label") or package.get("package_id"),
                "evidence_class": package.get("evidence_class"),
                "prior_level": package.get("prior_level"),
                "after_level": outcome.get("verification_level"),
                "factor_input_quality_state": outcome.get("factor_input_quality_state"),
                "accepted": outcome.get("accepted"),
                "reason_codes": outcome.get("reason_codes"),
                "limitations": outcome.get("limitations"),
                "fixture_type": package.get("fixture_type"),
                "evidence_use_limit": package.get("evidence_use_limit"),
            }
        )

    gate_passed = (
        suite["synthetic_live_separation_ok"]
        and live["all_field_verified_counts_zero"]
        and suite["runtime_rules_changed"] is False
        and suite["ranking_effect"] == "NONE"
        and suite["live_parcel_profiles_written"] == 0
    )

    # Spot-check key expected transitions.
    by_label = {t["fixture"]: t for t in transitions}
    expectations = {
        "valid_FIELD_VERIFIED_LIVESTOCK_WATER": "FIELD_VERIFIED_LIVESTOCK_WATER",
        "PHYSICAL_SOURCE_UNVERIFIED_SYSTEM": "FIELD_VERIFIED_LIVESTOCK_WATER",
        "VERIFIED_WATER_SYSTEM_CONTEXT": "FIELD_VERIFIED_LIVESTOCK_WATER",
        "CONFLICTING_SOURCES": "REMOTELY_SUPPORTED_CANDIDATE",
        "missing_legal_access": "REMOTELY_SUPPORTED_CANDIDATE",
        "missing_capacity_rationale": "REMOTELY_SUPPORTED_CANDIDATE",
        "invalid_evidence_hash": "REMOTELY_SUPPORTED_CANDIDATE",
        "stale_evidence": "FIELD_VERIFIED_LIVESTOCK_WATER",
        "geometry_mismatch": "REMOTELY_SUPPORTED_CANDIDATE",
        "REVIEWED_EQUIVALENT_FIELD_VERIFIED": "FIELD_VERIFIED_LIVESTOCK_WATER",
        "MIXED_with_qualified_field_basis": "FIELD_VERIFIED_LIVESTOCK_WATER",
        "mapped_to_field_verified_jump_rejected": "MAPPED_CANDIDATE",
    }
    expectation_ok = True
    expectation_failures = []
    for label, expected_level in expectations.items():
        actual = (by_label.get(label) or {}).get("after_level")
        if actual != expected_level:
            expectation_ok = False
            expectation_failures.append(
                {"fixture": label, "expected": expected_level, "actual": actual}
            )

    # Factor-state spot checks
    factor_expectations = {
        "valid_FIELD_VERIFIED_LIVESTOCK_WATER": "VERIFIED_WATER_SYSTEM_CONTEXT",
        "PHYSICAL_SOURCE_UNVERIFIED_SYSTEM": "PHYSICAL_SOURCE_UNVERIFIED_SYSTEM",
        "VERIFIED_WATER_SYSTEM_CONTEXT": "VERIFIED_WATER_SYSTEM_CONTEXT",
        "CONFLICTING_SOURCES": "CONFLICTING_SOURCES",
    }
    for label, expected_state in factor_expectations.items():
        actual = (by_label.get(label) or {}).get("factor_input_quality_state")
        if actual != expected_state:
            expectation_ok = False
            expectation_failures.append(
                {
                    "fixture": label,
                    "expected_factor_state": expected_state,
                    "actual_factor_state": actual,
                }
            )

    gate_passed = gate_passed and expectation_ok

    summary = {
        "demo_id": "F03_FIELD_EVIDENCE_INGESTION_DEMO",
        "suite": suite,
        "state_transitions": transitions,
        "live_parcel_separation": live,
        "expectation_failures": expectation_failures,
        "field_evidence_workflow_gate": {
            "passed": gate_passed,
            "criteria": [
                "synthetic_fixtures_only",
                "live_parcel_profiles_not_written",
                "live_field_verified_count_remains_0",
                "runtime_rules_unchanged",
                "ranking_effect_none",
                "deterministic_transitions_match_expectations",
            ],
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "field_evidence_demo_result.json"
    out_path.write_text(json.dumps(summary, indent=2) + "\n")

    # Also emit a compact transition table.
    table_path = OUT_DIR / "state_transitions.json"
    table_path.write_text(json.dumps(transitions, indent=2) + "\n")

    print(
        json.dumps(
            {
                "wrote": str(out_path.relative_to(PROJECT)),
                "field_evidence_workflow_gate_passed": gate_passed,
                "expectation_failures": expectation_failures,
                "synthetic_field_verified_count": suite["field_verified_count"],
                "live_field_verified_counts_zero": live["all_field_verified_counts_zero"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    # Ensure fixtures exist.
    build = PROJECT / "scripts/build_f03_field_evidence_fixtures.py"
    if not (FIXTURE_DIR / "manifest.json").exists():
        import runpy

        runpy.run_path(str(build))
    main()
