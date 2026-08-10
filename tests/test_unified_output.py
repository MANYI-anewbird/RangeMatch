"""Executable tests for RANGEMATCH_UNIFIED_OUTPUT@0.1.0 projection."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from rangematch.engine import evaluate_land_profile
from rangematch.explanation import explain_match_result
from rangematch.unified_output import (
    CONTRACT_VERSION,
    COVERAGE_NORMALIZATION,
    UnifiedOutputError,
    assert_explanation_binding,
    build_coverage_record,
    hash_match_result,
    normalize_coverage_status,
    project_unified_output,
    validate_one_parcel_geometry,
    validate_unified_output,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "test-data/land-profiles/land_profile_cper_001.json"
MATCH_PATH = ROOT / "test-data/land-profiles/match_result_cper_001.json"
GOLDEN_PATH = ROOT / "test-data/land-profiles/unified_output_cper_001.json"
GEOMETRY_PATH = ROOT / "test-data/engineering_test_geometry_cper_001.geojson"

PROFILE = json.loads(PROFILE_PATH.read_text())
MATCH = json.loads(MATCH_PATH.read_text())


def _stable_project(**kwargs):
    defaults = dict(
        mode="DISCOVERY",
        intended_operation=None,
        planned_actions=[],
        run_id="cper_unified_output_golden",
        created_at="2026-08-08T12:00:00Z",
        mireye_context=[],
        dynamic_diligence_findings=[],
    )
    defaults.update(kwargs)
    return project_unified_output(PROFILE, MATCH, **defaults)


class CoverageNormalizationTests(unittest.TestCase):
    def test_aliases_normalize_without_rewriting_source(self):
        cases = {
            "COVERAGE_UNQUANTIFIED": "UNQUANTIFIED",
            "COMPLETE_RANGELAND_COVERAGE": "COMPLETE",
            "COMPLETE_WITH_NUMERIC_TOLERANCE": "COMPLETE",
            "PARTIAL_RANGELAND_COVERAGE": "PARTIAL",
            "OUTSIDE_SUPPORTED_GEOGRAPHY": "OUTSIDE_SCOPE",
            "MISSING": "UNKNOWN",
            "NOT_APPLICABLE": "NOT_APPLICABLE",
        }
        for source, expected in cases.items():
            record = build_coverage_record(source, {"adapter_status": "x"})
            self.assertEqual(record["normalized_status"], expected)
            self.assertEqual(record["source_status"], source)
            self.assertEqual(normalize_coverage_status(source), expected)
            self.assertIn(source, COVERAGE_NORMALIZATION)

    def test_unknown_alias_becomes_unknown_normalized(self):
        record = build_coverage_record("SOMETHING_NEW", {})
        self.assertEqual(record["normalized_status"], "UNKNOWN")
        self.assertEqual(record["source_status"], "SOMETHING_NEW")


class OneParcelValidationTests(unittest.TestCase):
    def test_single_feature_ok(self):
        geo = json.loads(GEOMETRY_PATH.read_text())
        validate_one_parcel_geometry(geo)

    def test_multi_feature_rejected(self):
        geo = json.loads(GEOMETRY_PATH.read_text())
        geo["features"] = geo["features"] + deepcopy(geo["features"])
        with self.assertRaises(UnifiedOutputError):
            validate_one_parcel_geometry(geo)

    def test_project_rejects_multi_parcel_geometry(self):
        geo = json.loads(GEOMETRY_PATH.read_text())
        geo["features"] = geo["features"] + deepcopy(geo["features"])
        with self.assertRaises(UnifiedOutputError):
            project_unified_output(
                PROFILE,
                MATCH,
                mode="DISCOVERY",
                intended_operation=None,
                geometry=geo,
                created_at="2026-08-08T12:00:00Z",
                run_id="multi",
            )


class HashBehaviorTests(unittest.TestCase):
    def test_match_result_hash_stable_and_ignores_timestamps(self):
        a = hash_match_result(MATCH)
        b = hash_match_result(MATCH)
        self.assertEqual(a, b)
        mutated = deepcopy(MATCH)
        # Inject volatile fields that must not affect hash.
        mutated["created_at"] = "2099-01-01T00:00:00Z"
        mutated["fetched_at"] = "2099-01-01T00:00:00Z"
        mutated["operation_results"]["COW_CALF_OPERATION"]["llm_prose"] = "ignore me"
        mutated["operation_results"]["COW_CALF_OPERATION"]["ui_order"] = [3, 2, 1]
        mutated["cache_path"] = "test-data/live-results/cper/tiger2025_cache/x.zip"
        self.assertEqual(hash_match_result(mutated), a)

    def test_decision_change_changes_hash(self):
        mutated = deepcopy(MATCH)
        mutated["operation_results"]["COW_CALF_OPERATION"]["decision_label"] = "REVIEW"
        self.assertNotEqual(hash_match_result(mutated), hash_match_result(MATCH))


class ProjectionContractTests(unittest.TestCase):
    def test_discovery_cper_core_contract(self):
        envelope = _stable_project()
        self.assertEqual(envelope["contract_version"], CONTRACT_VERSION)
        self.assertEqual(envelope["mode"], "DISCOVERY")
        self.assertIsNone(envelope["intended_operation"])
        self.assertEqual(envelope["engine_input_hash"], MATCH["input_sha256"])
        self.assertEqual(
            envelope["explanation_binding_hash"], envelope["match_result_hash"]
        )
        self.assertEqual(
            envelope["match_result_hash"], hash_match_result(MATCH)
        )
        self.assertFalse(envelope["cross_profile_comparison"]["ranking_permitted"])
        self.assertIsNone(envelope["cross_profile_comparison"]["numeric_score"])
        self.assertEqual(
            envelope["operations"]["COW_CALF_OPERATION"]["decision_label"], "HOLD"
        )
        self.assertEqual(
            envelope["operations"]["SHEEP_GRAZING"]["decision_label"], "HOLD"
        )
        self.assertIn(
            "resolution_status", envelope["parcel"]["jurisdiction"]
        )
        self.assertEqual(
            envelope["factors"]["F02_HERBACEOUS_RESOURCE"]["signal"],
            "NEEDS_VERIFICATION",
        )
        self.assertEqual(
            envelope["factors"]["F03_LIVESTOCK_WATER"]["signal"],
            "NEEDS_VERIFICATION",
        )
        self.assertEqual(
            envelope["factors"]["F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"]["signal"],
            "NEEDS_VERIFICATION",
        )
        f02_cov = envelope["factors"]["F02_HERBACEOUS_RESOURCE"]["coverage"]
        self.assertEqual(f02_cov["normalized_status"], "UNQUANTIFIED")
        self.assertEqual(f02_cov["source_status"], "COVERAGE_UNQUANTIFIED")
        f08_cov = envelope["factors"]["F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"][
            "coverage"
        ]
        self.assertEqual(f08_cov["normalized_status"], "UNQUANTIFIED")
        self.assertEqual(f08_cov["source_status"], "COVERAGE_UNQUANTIFIED")
        # Jurisdiction required; CPER inferred PARTIAL/RESOLVED from F07 FIPS.
        self.assertIn(
            envelope["parcel"]["jurisdiction"]["resolution_status"],
            {"PARTIAL", "RESOLVED"},
        )
        self.assertEqual(envelope["constraints"]["parcels_per_run"], 1)
        self.assertFalse(envelope["constraints"]["f09_authorized"])
        validate_unified_output(envelope)

    def test_goal_directed_presentation_not_science(self):
        envelope = _stable_project(
            mode="GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            run_id="cper_goal",
        )
        cow = envelope["operations"]["COW_CALF_OPERATION"]
        sheep = envelope["operations"]["SHEEP_GRAZING"]
        self.assertEqual(cow["presentation_priority"], 0)
        self.assertEqual(sheep["presentation_priority"], 1)
        self.assertEqual(cow["decision_label"], sheep["decision_label"])
        self.assertFalse(cow["ranking_permission"])
        highlights = envelope["buyer_report"]["Operation Comparison"]["highlights"]
        self.assertTrue(
            any(
                isinstance(h, dict) and "no scientific priority" in str(h).lower()
                for h in highlights
            )
        )

    def test_discovery_rejects_intended_operation(self):
        with self.assertRaises(UnifiedOutputError):
            _stable_project(
                mode="DISCOVERY",
                intended_operation="COW_CALF_OPERATION",
            )

    def test_planned_actions_do_not_mutate_match_result(self):
        before = deepcopy(MATCH)
        envelope = _stable_project(
            planned_actions=["drill_well", "construct_fence"],
            dynamic_diligence_findings=[
                {
                    "finding_id": "dil_1",
                    "finding_type": "PERMIT",
                    "trigger": "drill_well",
                    "jurisdiction": "county",
                    "official_sources": [],
                    "accessed_at": "2026-08-08T12:00:00Z",
                    "currency_status": "UNKNOWN",
                    "applicability_status": "UNKNOWN",
                    "limitations": ["not legal advice"],
                    "professional_verification_required": True,
                    "disposition": "PROFESSIONAL_CONFIRMATION_REQUIRED",
                }
            ],
        )
        self.assertEqual(MATCH, before)
        self.assertEqual(envelope["planned_actions"], ["drill_well", "construct_fence"])
        self.assertFalse(envelope["constraints"]["planned_actions_mutate_factors"])
        self.assertEqual(
            envelope["dynamic_diligence_findings"][0]["related_planned_actions"],
            ["drill_well", "construct_fence"],
        )
        # Factor signals unchanged vs MatchResult.
        self.assertEqual(
            envelope["factors"]["F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"]["signal"],
            MATCH["operation_results"]["COW_CALF_OPERATION"]["factor_evaluations"][
                "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"
            ]["signal"],
        )

    def test_f07_split_property_vs_diligence(self):
        envelope = _stable_project()
        prop = envelope["buyer_report"]["Property"]
        dil = envelope["buyer_report"]["Diligence Plan"]
        self.assertIn("F07_ROAD_AND_PHYSICAL_ACCESS", prop["factor_ids"])
        self.assertTrue(
            any(
                h.get("f07_projection") == "physical_road_context"
                for h in prop["highlights"]
                if isinstance(h, dict)
            )
        )
        self.assertTrue(
            any(
                h.get("f07_projection") == "legal_access_diligence"
                for h in dil["highlights"]
                if isinstance(h, dict)
            )
        )
        # Canonical factor remains single.
        self.assertEqual(
            envelope["factors"]["F07_ROAD_AND_PHYSICAL_ACCESS"]["factor_id"],
            "F07_ROAD_AND_PHYSICAL_ACCESS",
        )
        joined_dil = " ".join(dil["diligence_actions"] + dil["limitations"]).lower()
        self.assertIn("legal access", joined_dil)

    def test_mireye_not_promoted_to_land_facts(self):
        envelope = _stable_project(
            mireye_context=[
                {
                    "context_type": "POINT_LAND_CONTEXT",
                    "endpoint_or_preset": "land_read",
                    "requested_point": {"lon": -104.76, "lat": 40.825},
                    "disposition": "SUCCESS",
                    "fields": {"slope": 2.1, "lcms_class": "Grass/Forb/Herb & Shrubs Mix"},
                    "fetched_at": "2026-08-08T12:00:00Z",
                    "partial_failures": [],
                }
            ]
        )
        f08_vars = {
            lf["variable_id"]
            for lf in envelope["factors"]["F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"][
                "land_facts"
            ]
        }
        self.assertNotIn("lcms_class", f08_vars)
        self.assertEqual(envelope["mireye_context"][0]["context_type"], "POINT_LAND_CONTEXT")

    def test_explanation_binding(self):
        envelope = _stable_project()
        explanation = explain_match_result(MATCH, PROFILE)
        self.assertEqual(
            explanation["bound_to_match_result_hash"], envelope["match_result_hash"]
        )
        assert_explanation_binding(explanation, envelope)

    def test_recompute_match_result_compatible(self):
        recomputed = evaluate_land_profile(PROFILE)
        envelope = project_unified_output(
            PROFILE,
            recomputed,
            mode="DISCOVERY",
            intended_operation=None,
            created_at="2026-08-08T12:00:00Z",
            run_id="recomputed",
        )
        self.assertEqual(envelope["operations"]["COW_CALF_OPERATION"]["decision_label"], "HOLD")
        self.assertEqual(
            envelope["engine_input_hash"], recomputed["input_sha256"]
        )


class GoldenFixtureTests(unittest.TestCase):
    def test_golden_projection_matches_fixture(self):
        envelope = _stable_project()
        # Strip created_at equality already fixed; compare stable core.
        if not GOLDEN_PATH.exists():
            self.fail(f"missing golden fixture: {GOLDEN_PATH}")
        golden = json.loads(GOLDEN_PATH.read_text())
        # created_at fixed in both; full equality.
        self.assertEqual(envelope, golden)


def regenerate_golden() -> None:
    envelope = _stable_project()
    GOLDEN_PATH.write_text(json.dumps(envelope, indent=2) + "\n")


if __name__ == "__main__":
    regenerate_golden()
    unittest.main()
