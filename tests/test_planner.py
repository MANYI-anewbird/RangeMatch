"""Executable tests for RangeMatch Planner dependency-DAG routing stub."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from rangematch.planner import (
    PLANNER_VERSION,
    PlannerError,
    assert_plans_equal,
    build_investigation_plan,
    factor_steps_in_report_order,
    get_step,
    plan_sha256,
)
from rangematch.tool_registry import (
    CANONICAL_FACTOR_REPORT_ORDER,
    PEER_FACTORS_AFTER_F06,
    UNAUTHORIZED_TOOL_IDS,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads(
    (ROOT / "test-data/land-profiles/land_profile_cper_001.json").read_text()
)
GEOMETRY = json.loads(
    (ROOT / "test-data/engineering_test_geometry_cper_001.geojson").read_text()
)


def _deps(plan, step_id: str) -> set[str]:
    return set(get_step(plan, step_id)["dependency_step_ids"])


def _tool_ids(plan) -> set[str]:
    return {s["tool_id"] for s in plan["steps"]}


class PlannerModeTests(unittest.TestCase):
    def test_goal_directed_cow_calf_dag(self):
        plan = build_investigation_plan(
            mode="GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            parcel_geometry=GEOMETRY,
            plan_id="goal_cow",
        )
        self.assertEqual(plan["planner_version"], PLANNER_VERSION)
        self.assertEqual(plan["mode"], "GOAL_DIRECTED")
        self.assertEqual(
            plan["presentation"]["operation_presentation_order"][0],
            "COW_CALF_OPERATION",
        )
        self.assertFalse(plan["presentation"]["scientific_priority_change"])
        self.assertFalse(plan["live_network_authorized"])
        self.assertEqual(plan["execution_model"], "DEPENDENCY_DAG")
        self.assertIn("S06_F06_PARCEL_CONFIGURATION", plan["dag"]["nodes"])
        self.assertEqual(
            plan["terminal_sequence"],
            [
                "S09_ASSEMBLE_LAND_PROFILE",
                "S10_EVALUATE_ENGINE",
                "S11_PROJECT_UNIFIED_OUTPUT",
                "S13_EXPLAIN_AND_PRODUCT",
            ],
        )

    def test_goal_directed_sheep_dag(self):
        plan = build_investigation_plan(
            mode="GOAL_DIRECTED",
            intended_operation="SHEEP_GRAZING",
            parcel_geometry=GEOMETRY,
        )
        self.assertEqual(
            plan["presentation"]["operation_presentation_order"][0],
            "SHEEP_GRAZING",
        )
        self.assertIn("COW_CALF_OPERATION", plan["presentation"]["operation_presentation_order"])
        self.assertFalse(plan["presentation"]["rule_or_threshold_change"])

    def test_discovery_dag(self):
        plan = build_investigation_plan(
            mode="DISCOVERY",
            intended_operation=None,
            parcel_geometry=GEOMETRY,
        )
        self.assertIsNone(plan["intended_operation"])
        self.assertTrue(plan["presentation"]["discovery_limited_to_supported_profiles"])
        self.assertEqual(
            plan["presentation"]["operation_presentation_order"],
            ["COW_CALF_OPERATION", "SHEEP_GRAZING"],
        )

    def test_invalid_mode_combinations(self):
        with self.assertRaises(PlannerError):
            build_investigation_plan(
                mode="DISCOVERY",
                intended_operation="COW_CALF_OPERATION",
                parcel_geometry=GEOMETRY,
            )
        with self.assertRaises(PlannerError):
            build_investigation_plan(
                mode="GOAL_DIRECTED",
                intended_operation=None,
                parcel_geometry=GEOMETRY,
            )
        with self.assertRaises(PlannerError):
            build_investigation_plan(
                mode="GOAL_DIRECTED",
                intended_operation="GOAT",
                parcel_geometry=GEOMETRY,
            )


class PlannerGeometryTests(unittest.TestCase):
    def test_multiple_parcels_rejected(self):
        multi = deepcopy(GEOMETRY)
        multi["features"] = multi["features"] + deepcopy(multi["features"])
        with self.assertRaises(PlannerError):
            build_investigation_plan(
                mode="DISCOVERY",
                intended_operation=None,
                parcel_geometry=multi,
            )

    def test_exactly_one_entry_required(self):
        with self.assertRaises(PlannerError):
            build_investigation_plan(
                mode="DISCOVERY",
                intended_operation=None,
            )
        with self.assertRaises(PlannerError):
            build_investigation_plan(
                mode="DISCOVERY",
                intended_operation=None,
                address="somewhere",
                parcel_geometry=GEOMETRY,
            )


class PlannerDagStructureTests(unittest.TestCase):
    def test_peers_after_geometry_f06_gate(self):
        plan = build_investigation_plan(
            mode="DISCOVERY",
            intended_operation=None,
            parcel_geometry=GEOMETRY,
        )
        f06 = "S06_F06_PARCEL_CONFIGURATION"
        self.assertEqual(_deps(plan, f06), {"S02_RESOLVE_GEOMETRY"})
        peer_steps = plan["dag"]["parallel_groups"]["peer_factors_after_f06"]
        self.assertEqual(len(peer_steps), len(PEER_FACTORS_AFTER_F06))
        for sid in peer_steps:
            self.assertEqual(_deps(plan, sid), {f06})
            self.assertEqual(get_step(plan, sid)["parallel_group"], "peer_factors_after_f06")
        # Not a fixed serial chain among peers.
        f01 = get_step(plan, "S07_PEER_F01_TOPOGRAPHY")
        f02 = get_step(plan, "S07_PEER_F02_HERBACEOUS_RESOURCE")
        self.assertNotIn(f01["step_id"], f02["dependency_step_ids"])
        self.assertNotIn(f02["step_id"], f01["dependency_step_ids"])

    def test_f08_depends_on_f02_compatible_artifact_and_reuses(self):
        plan = build_investigation_plan(
            mode="DISCOVERY",
            intended_operation=None,
            parcel_geometry=GEOMETRY,
        )
        f08 = get_step(plan, "S08_F08_WOODY_REUSE")
        self.assertEqual(f08["dependency_step_ids"], ["S07_PEER_F02_HERBACEOUS_RESOURCE"])
        self.assertEqual(f08["action"], "REUSE")
        self.assertFalse(f08["notes"]["duplicate_rap_fetch"])
        self.assertEqual(f08["notes"]["action_forced"], "REUSE")
        self.assertIn("duplicate RAP coverV3 FETCH", f08["prohibited_promotions"])
        # Must not plan a second RAP fetch tool for F08.
        self.assertEqual(f08["tool_id"], "factor.f08_woody_reuse_rap")
        rap_fetch_steps = [
            s
            for s in plan["steps"]
            if s["tool_id"] == "adapter.rap_cover_production"
        ]
        self.assertEqual(len(rap_fetch_steps), 1)

    def test_report_order_remains_f01_to_f08(self):
        plan = build_investigation_plan(
            mode="DISCOVERY",
            intended_operation=None,
            parcel_geometry=GEOMETRY,
        )
        self.assertEqual(
            plan["canonical_factor_report_order"], list(CANONICAL_FACTOR_REPORT_ORDER)
        )
        ordered = factor_steps_in_report_order(plan)
        self.assertEqual(
            [s["factor_id"] for s in ordered], list(CANONICAL_FACTOR_REPORT_ORDER)
        )
        assemble = get_step(plan, "S09_ASSEMBLE_LAND_PROFILE")
        self.assertEqual(
            assemble["notes"]["report_order"], list(CANONICAL_FACTOR_REPORT_ORDER)
        )


class PlannerReuseAndMireyeTests(unittest.TestCase):
    def test_existing_land_profile_prefers_reuse_evaluate(self):
        plan = build_investigation_plan(
            mode="DISCOVERY",
            intended_operation=None,
            land_profile=PROFILE,
        )
        self.assertEqual(plan["entry"], "land_profile")
        self.assertEqual(get_step(plan, "S02_RESOLVE_GEOMETRY")["action"], "REUSE")
        self.assertEqual(
            get_step(plan, "S06_F06_PARCEL_CONFIGURATION")["action"], "REUSE"
        )
        self.assertEqual(
            get_step(plan, "S07_PEER_F02_HERBACEOUS_RESOURCE")["action"], "REUSE"
        )
        self.assertEqual(get_step(plan, "S08_F08_WOODY_REUSE")["action"], "REUSE")
        self.assertEqual(get_step(plan, "S10_EVALUATE_ENGINE")["action"], "EVALUATE")
        self.assertEqual(get_step(plan, "S11_PROJECT_UNIFIED_OUTPUT")["action"], "PROJECT")

    def test_mireye_contexts_non_canonical(self):
        plan = build_investigation_plan(
            mode="DISCOVERY",
            intended_operation=None,
            parcel_geometry=GEOMETRY,
        )
        for sid in plan["dag"]["parallel_groups"]["mireye_context"]:
            step = get_step(plan, sid)
            self.assertTrue(step["notes"]["non_canonical"])
            self.assertIn("NON_CANONICAL", step["canonical_authority"])
            self.assertEqual(_deps(plan, sid), {"S02_RESOLVE_GEOMETRY"})

    def test_hazard_partial_failure_visible(self):
        failures = [{"dataset": "FEMA", "reason": "coverage_gap"}]
        plan = build_investigation_plan(
            mode="DISCOVERY",
            intended_operation=None,
            parcel_geometry=GEOMETRY,
            hazard_partial_failures=failures,
        )
        hazard = get_step(plan, "S05_MIREYE_POINT_HAZARD")
        self.assertTrue(hazard["notes"]["preserve_partial_failures"])
        self.assertEqual(hazard["notes"]["partial_failures"], failures)


class PlannerConstraintTests(unittest.TestCase):
    def test_planned_actions_do_not_change_factor_dag(self):
        base = build_investigation_plan(
            mode="DISCOVERY",
            intended_operation=None,
            parcel_geometry=GEOMETRY,
            planned_actions=[],
            plan_id="same",
        )
        with_actions = build_investigation_plan(
            mode="DISCOVERY",
            intended_operation=None,
            parcel_geometry=GEOMETRY,
            planned_actions=["drill_well", "construct_fence"],
            plan_id="same",
        )
        self.assertEqual(base["dag"]["parallel_groups"], with_actions["dag"]["parallel_groups"])
        self.assertEqual(base["terminal_sequence"], with_actions["terminal_sequence"])
        self.assertEqual(
            [
                (s["step_id"], s["dependency_step_ids"], s["action"], s["tool_id"])
                for s in base["steps"]
            ],
            [
                (s["step_id"], s["dependency_step_ids"], s["action"], s["tool_id"])
                for s in with_actions["steps"]
                if s["tool_id"] != "diligence.dynamic_from_planned_actions"
            ],
        )
        self.assertTrue(
            any(
                s["tool_id"] == "diligence.dynamic_from_planned_actions"
                for s in with_actions["steps"]
            )
        )
        self.assertFalse(with_actions["constraints"]["planned_actions_mutate_factor_dag"])

    def test_deterministic_identical_plan(self):
        a = build_investigation_plan(
            mode="GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            parcel_geometry=GEOMETRY,
            plan_id="det",
            planned_actions=["improve_road"],
        )
        b = build_investigation_plan(
            mode="GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            parcel_geometry=GEOMETRY,
            plan_id="det",
            planned_actions=["improve_road"],
        )
        assert_plans_equal(a, b)
        self.assertEqual(plan_sha256(a), plan_sha256(b))

    def test_no_f09_batch_icp_tools(self):
        plan = build_investigation_plan(
            mode="DISCOVERY",
            intended_operation=None,
            parcel_geometry=GEOMETRY,
        )
        tools = _tool_ids(plan)
        self.assertTrue(tools.isdisjoint(UNAUTHORIZED_TOOL_IDS))
        self.assertFalse(any(t.startswith("F09") for t in tools))
        self.assertFalse(plan["constraints"]["f09_authorized"])
        self.assertFalse(plan["constraints"]["batch_workflow_authorized"])
        self.assertFalse(plan["constraints"]["icp_authorized"])

    def test_final_stages_assemble_evaluate_project_explain(self):
        plan = build_investigation_plan(
            mode="DISCOVERY",
            intended_operation=None,
            parcel_geometry=GEOMETRY,
        )
        seq = plan["terminal_sequence"]
        self.assertEqual(
            [get_step(plan, sid)["action"] for sid in seq],
            ["COMPUTE", "EVALUATE", "PROJECT", "EXPLAIN"],
        )
        self.assertEqual(_deps(plan, "S10_EVALUATE_ENGINE"), {"S09_ASSEMBLE_LAND_PROFILE"})
        self.assertEqual(_deps(plan, "S11_PROJECT_UNIFIED_OUTPUT"), {"S10_EVALUATE_ENGINE"})
        self.assertIn("S11_PROJECT_UNIFIED_OUTPUT", _deps(plan, "S13_EXPLAIN_AND_PRODUCT"))
        explain = get_step(plan, "S13_EXPLAIN_AND_PRODUCT")
        self.assertEqual(explain["notes"]["bind_to"], "match_result_hash")


if __name__ == "__main__":
    unittest.main()
