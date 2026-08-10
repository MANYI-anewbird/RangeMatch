"""Tests for fixture-backed Planner Executor."""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock

from rangematch.planner import build_investigation_plan, plan_sha256
from rangematch.planner_executor import (
    EXECUTOR_VERSION,
    STEP_BLOCKED_DEPENDENCY,
    STEP_BLOCKED_EXTERNAL,
    STEP_FAILED,
    STEP_SUCCEEDED,
    deterministic_execution_hash,
    execute_plan,
    topological_step_order,
    write_execution_record,
)
from rangematch.tool_registry import CANONICAL_FACTOR_REPORT_ORDER
from rangematch.tool_runners import ExecutionFixtures


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "test-data/land-profiles/land_profile_cper_001.json"
GEOM_PATH = ROOT / "test-data/engineering_test_geometry_cper_001.geojson"
MIREYE_DIR = ROOT / "test-data/mireye-normalized/normalized"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _mireye_fixtures(*, blocked: bool = False) -> ExecutionFixtures:
    profile = _load(PROFILE_PATH)
    geometry = _load(GEOM_PATH)
    contexts = {
        "PROPERTY_DILIGENCE_CONTEXT": _load(MIREYE_DIR / "lookup_resolved.normalized.json"),
        "POINT_LAND_CONTEXT": _load(MIREYE_DIR / "point_land_complete.normalized.json"),
        "POINT_HAZARD_CONTEXT": _load(MIREYE_DIR / "point_hazard_complete.normalized.json"),
    }
    return ExecutionFixtures(
        land_profile=profile,
        geometry=geometry,
        mireye_contexts=contexts,
        mireye_blocked_external=blocked,
    )


def _plan(mode: str, *, intended_operation: str | None, plan_id: str):
    profile = _load(PROFILE_PATH)
    return build_investigation_plan(
        mode=mode,
        intended_operation=intended_operation,
        land_profile=profile,
        plan_id=plan_id,
        include_mireye_context=True,
    )


def _step_map(execution):
    return {s["step_id"]: s for s in execution["steps"]}


class PlannerExecutorTests(unittest.TestCase):
    def test_00_f06_compute_uses_confirmed_geometry_without_profile_fixture(self):
        geometry = _load(GEOM_PATH)
        plan = build_investigation_plan(
            mode="DISCOVERY",
            intended_operation=None,
            parcel_geometry=geometry,
            plan_id="live_geometry_f06_compute",
            include_mireye_context=False,
        )
        first = execute_plan(plan, fixtures=ExecutionFixtures(geometry=geometry))
        second = execute_plan(plan, fixtures=ExecutionFixtures(geometry=geometry))
        first_step = _step_map(first)["S06_F06_PARCEL_CONFIGURATION"]
        second_step = _step_map(second)["S06_F06_PARCEL_CONFIGURATION"]
        self.assertEqual(first_step["status"], STEP_SUCCEEDED)
        self.assertTrue(first_step["notes"]["deterministic_geometry_compute"])
        factor = first["_artifact_store"]["factor:F06_PARCEL_CONFIGURATION"]
        factor_2 = second["_artifact_store"]["factor:F06_PARCEL_CONFIGURATION"]
        self.assertEqual(factor["input_quality_state"], "PARCEL_GEOMETRY_COMPLETE")
        self.assertEqual(factor["ranking_effect"], "NONE")
        for field in ("geometry_hash", "working_crs", "area_m2", "perimeter_m", "compactness"):
            self.assertEqual(factor[field], factor_2[field])
        self.assertNotIn("suitability_class", factor)

    def test_00b_precollected_live_f01_enters_executor_without_profile_fixture(self):
        geometry = _load(GEOM_PATH)
        f01 = _load(PROFILE_PATH)["factors"]["F01_TOPOGRAPHY"]
        plan = build_investigation_plan(
            mode="DISCOVERY",
            intended_operation=None,
            parcel_geometry=geometry,
            plan_id="live_geometry_f01_precollected",
            include_mireye_context=False,
        )
        execution = execute_plan(
            plan,
            fixtures=ExecutionFixtures(
                geometry=geometry,
                computed_factors={"F01_TOPOGRAPHY": f01},
            ),
        )
        step = _step_map(execution)["S07_PEER_F01_TOPOGRAPHY"]
        self.assertEqual(step["status"], STEP_SUCCEEDED)
        self.assertTrue(step["notes"]["computed_factor"])
        assembled = execution["_artifact_store"]["land_profile"]["factors"]
        self.assertEqual(assembled["F01_TOPOGRAPHY"]["input_quality_state"], "PARCEL_COMPLETE")

    def test_01_goal_directed_end_to_end(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_goal_directed_exec",
        )
        fixtures = _mireye_fixtures(blocked=False)
        execution = execute_plan(plan, fixtures=fixtures, execution_id="exec_cper_goal")
        self.assertEqual(execution["executor_version"], EXECUTOR_VERSION)
        self.assertIn(execution["execution_status"], {"SUCCEEDED", "PARTIAL"})
        self.assertIsNotNone(execution["match_result_ref"])
        self.assertIsNotNone(execution["unified_output_ref"])
        store = execution["_artifact_store"]
        uo = store["unified_output"]
        self.assertEqual(uo["explanation_binding_hash"], uo["match_result_hash"])
        self.assertEqual(
            execution["presentation"]["operation_presentation_order"][0],
            "COW_CALF_OPERATION",
        )
        self.assertFalse(execution["presentation"]["scientific_priority_change"])
        # Sheep still evaluated
        mr = store["match_result"]
        self.assertIn("COW_CALF_OPERATION", mr["operation_results"])
        self.assertIn("SHEEP_GRAZING", mr["operation_results"])
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "cper_goal_directed_execution.json"
            write_execution_record(output, execution)
            self.assertEqual(_load(output)["execution_id"], "exec_cper_goal")

    def test_02_discovery_end_to_end(self):
        plan = _plan("DISCOVERY", intended_operation=None, plan_id="cper_discovery_exec")
        fixtures = _mireye_fixtures(blocked=False)
        execution = execute_plan(plan, fixtures=fixtures, execution_id="exec_cper_discovery")
        self.assertIn(execution["execution_status"], {"SUCCEEDED", "PARTIAL"})
        self.assertEqual(execution["mode"], "DISCOVERY")
        self.assertIsNone(execution["intended_operation"])
        # No ranking / best-use claim in presentation
        self.assertFalse(execution["presentation"]["scientific_priority_change"])
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "cper_discovery_execution.json"
            write_execution_record(output, execution)
            self.assertEqual(_load(output)["execution_id"], "exec_cper_discovery")

    def test_03_deterministic_execution_hash(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_goal_hash",
        )
        a = execute_plan(plan, fixtures=_mireye_fixtures(), execution_id="a")
        b = execute_plan(plan, fixtures=_mireye_fixtures(), execution_id="b")
        self.assertEqual(
            a["deterministic_execution_hash"], b["deterministic_execution_hash"]
        )
        # Timestamps differ but hash ignores them
        self.assertNotEqual(a["started_at"], "SENTINEL")
        payload_a = {k: v for k, v in a.items() if k != "_artifact_store"}
        payload_b = {k: v for k, v in b.items() if k != "_artifact_store"}
        self.assertEqual(
            deterministic_execution_hash(payload_a),
            deterministic_execution_hash(payload_b),
        )

    def test_04_canonical_report_order(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_order",
        )
        execution = execute_plan(plan, fixtures=_mireye_fixtures())
        self.assertEqual(
            execution["canonical_factor_report_order"], list(CANONICAL_FACTOR_REPORT_ORDER)
        )
        self.assertEqual(
            execution["factor_steps_by_report_order"], list(CANONICAL_FACTOR_REPORT_ORDER)
        )
        # Execution order is topo — F06 before peers; F08 after F02 — not report order
        order = execution["step_order_executed"]
        self.assertLess(
            order.index("S06_F06_PARCEL_CONFIGURATION"),
            order.index("S07_PEER_F01_TOPOGRAPHY"),
        )
        self.assertLess(
            order.index("S07_PEER_F02_HERBACEOUS_RESOURCE"),
            order.index("S08_F08_WOODY_REUSE"),
        )

    def test_05_peer_dependency_behavior(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_peers",
        )
        execution = execute_plan(plan, fixtures=_mireye_fixtures())
        steps = _step_map(execution)
        for fid in (
            "F01_TOPOGRAPHY",
            "F02_HERBACEOUS_RESOURCE",
            "F03_LIVESTOCK_WATER",
            "F04_SOIL_WETNESS_ECOLOGICAL_SITE",
            "F05_CLIMATE_DROUGHT_EXPOSURE",
            "F07_ROAD_AND_PHYSICAL_ACCESS",
        ):
            sid = f"S07_PEER_{fid}"
            self.assertEqual(steps[sid]["dependency_step_ids"], ["S06_F06_PARCEL_CONFIGURATION"])
            self.assertEqual(steps[sid]["status"], STEP_SUCCEEDED)

    def test_06_f08_reuses_f02_artifact(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_f08",
        )
        fixtures = _mireye_fixtures()
        execution = execute_plan(plan, fixtures=fixtures)
        f08 = _step_map(execution)["S08_F08_WOODY_REUSE"]
        self.assertEqual(f08["action"], "REUSE")
        self.assertEqual(f08["status"], STEP_SUCCEEDED)
        self.assertTrue(
            any(r.startswith("rap_coverV3:") for r in f08["reused_artifact_refs"])
        )

    def test_07_no_duplicate_rap_fetch(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_rap",
        )
        fixtures = _mireye_fixtures()
        execution = execute_plan(plan, fixtures=fixtures)
        self.assertEqual(fixtures.rap_fetch_count, 1)
        self.assertEqual(execution["artifacts"]["_meta"]["rap_fetch_count"], 1)

    def test_08_geometry_failure_blocks_parcel_workflow(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_geo_fail",
        )
        fixtures = _mireye_fixtures()
        fixtures.force_step_status = {"S01_VALIDATE_ONE_PARCEL": STEP_FAILED}
        execution = execute_plan(plan, fixtures=fixtures)
        steps = _step_map(execution)
        self.assertEqual(steps["S01_VALIDATE_ONE_PARCEL"]["status"], STEP_FAILED)
        self.assertEqual(steps["S06_F06_PARCEL_CONFIGURATION"]["status"], STEP_BLOCKED_DEPENDENCY)
        self.assertEqual(steps["S10_EVALUATE_ENGINE"]["status"], STEP_BLOCKED_DEPENDENCY)
        self.assertIsNone(execution["match_result_ref"])
        self.assertEqual(execution["execution_status"], "FAILED")

    def test_09_f02_failure_blocks_f08_only(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_f02_fail",
        )
        fixtures = _mireye_fixtures()
        fixtures.force_step_status = {"S07_PEER_F02_HERBACEOUS_RESOURCE": STEP_FAILED}
        execution = execute_plan(plan, fixtures=fixtures)
        steps = _step_map(execution)
        self.assertEqual(steps["S08_F08_WOODY_REUSE"]["status"], STEP_BLOCKED_DEPENDENCY)
        self.assertEqual(steps["S07_PEER_F01_TOPOGRAPHY"]["status"], STEP_SUCCEEDED)
        self.assertEqual(steps["S07_PEER_F03_LIVESTOCK_WATER"]["status"], STEP_SUCCEEDED)
        # Assemble still runs without inventing F02/F08
        self.assertIn(steps["S09_ASSEMBLE_LAND_PROFILE"]["status"], {STEP_SUCCEEDED, "PARTIAL"})
        missing = (steps["S09_ASSEMBLE_LAND_PROFILE"].get("notes") or {}).get(
            "missing_factors"
        ) or execution["_artifact_store"]["land_profile"].get("factors")
        assembled = execution["_artifact_store"]["land_profile"]["factors"]
        self.assertNotIn("F02_HERBACEOUS_RESOURCE", assembled)
        self.assertNotIn("F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE", assembled)

    def test_10_mireye_blocked_external_factors_continue(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_mireye_blocked",
        )
        fixtures = _mireye_fixtures(blocked=True)
        execution = execute_plan(plan, fixtures=fixtures)
        steps = _step_map(execution)
        for sid in ("S03_MIREYE_PROPERTY", "S04_MIREYE_POINT_LAND", "S05_MIREYE_POINT_HAZARD"):
            self.assertEqual(steps[sid]["status"], STEP_BLOCKED_EXTERNAL)
        self.assertEqual(steps["S07_PEER_F01_TOPOGRAPHY"]["status"], STEP_SUCCEEDED)
        self.assertEqual(steps["S10_EVALUATE_ENGINE"]["status"], STEP_SUCCEEDED)
        uo = execution["_artifact_store"]["unified_output"]
        mireye = uo.get("mireye_context") or []
        self.assertTrue(mireye)
        self.assertTrue(any(m.get("disposition") == "BLOCKED_EXTERNAL" for m in mireye))
        limitations = uo.get("limitations") or []
        self.assertTrue(any("BLOCKED_EXTERNAL" in str(x) for x in limitations))
        # Not an empty successful context
        for m in mireye:
            if m.get("disposition") == "BLOCKED_EXTERNAL":
                self.assertTrue(m.get("partial_failures"))

    def test_11_partial_mireye_field_failures_visible(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_mireye_partial",
        )
        fixtures = _mireye_fixtures(blocked=False)
        fixtures.mireye_contexts["POINT_HAZARD_CONTEXT"] = _load(
            MIREYE_DIR / "point_hazard_fema_partial.normalized.json"
        )
        execution = execute_plan(plan, fixtures=fixtures)
        steps = _step_map(execution)
        self.assertEqual(steps["S05_MIREYE_POINT_HAZARD"]["status"], "PARTIAL")
        hazard = execution["_artifact_store"]["mireye:POINT_HAZARD_CONTEXT"]
        self.assertTrue(hazard.get("partial_failures"))
        uo = execution["_artifact_store"]["unified_output"]
        items = [m for m in (uo.get("mireye_context") or []) if m.get("context_type") == "POINT_HAZARD_CONTEXT"]
        self.assertTrue(items and items[0].get("partial_failures"))

    def test_12_individual_factor_failure_unknown_not_fabricated(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_f04_fail",
        )
        fixtures = _mireye_fixtures()
        fixtures.force_step_status = {
            "S07_PEER_F04_SOIL_WETNESS_ECOLOGICAL_SITE": STEP_FAILED
        }
        execution = execute_plan(plan, fixtures=fixtures)
        assembled = execution["_artifact_store"]["land_profile"]["factors"]
        self.assertNotIn("F04_SOIL_WETNESS_ECOLOGICAL_SITE", assembled)
        self.assertIn("F01_TOPOGRAPHY", assembled)
        self.assertEqual(
            _step_map(execution)["S07_PEER_F01_TOPOGRAPHY"]["status"], STEP_SUCCEEDED
        )

    def test_13_existing_land_profile_reuse_path(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_reuse",
        )
        self.assertEqual(plan["entry"], "land_profile")
        execution = execute_plan(plan, fixtures=_mireye_fixtures())
        steps = _step_map(execution)
        self.assertEqual(steps["S02_RESOLVE_GEOMETRY"]["action"], "REUSE")
        self.assertTrue(steps["S02_RESOLVE_GEOMETRY"]["reused_artifact_refs"])

    def test_14_engine_authoritative(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_engine",
        )
        execution = execute_plan(plan, fixtures=_mireye_fixtures())
        mr = execution["_artifact_store"]["match_result"]
        uo = execution["_artifact_store"]["unified_output"]
        # Projection consumes engine match result hashes
        self.assertEqual(uo["match_result_hash"], __import__(
            "rangematch.unified_output", fromlist=["hash_match_result"]
        ).hash_match_result(mr))
        ex = execution["_artifact_store"]["explanation"]
        self.assertFalse(ex.get("may_alter_decision_labels"))
        self.assertFalse(ex.get("llm_override_permitted"))

    def test_15_explanation_binding_hash(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_bind",
        )
        execution = execute_plan(plan, fixtures=_mireye_fixtures())
        uo = execution["_artifact_store"]["unified_output"]
        ex = uo["explanation"]
        self.assertEqual(ex["bound_to_match_result_hash"], uo["match_result_hash"])
        self.assertEqual(uo["explanation_binding_hash"], uo["match_result_hash"])

    def test_16_one_parcel_only_enforcement(self):
        from rangematch.planner import PlannerError

        multi = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {},
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [1, 1]},
                    "properties": {},
                },
            ],
        }
        with self.assertRaises(PlannerError):
            build_investigation_plan(
                mode="DISCOVERY",
                parcel_geometry=multi,
                plan_id="multi_should_fail",
            )
        # Happy-path plan remains one-parcel.
        plan = _plan("DISCOVERY", intended_operation=None, plan_id="cper_one")
        self.assertEqual(plan["constraints"]["parcels_per_run"], 1)
        execution = execute_plan(plan, fixtures=_mireye_fixtures())
        self.assertEqual(execution["constraints"]["batch_authorized"], False)

    def test_17_no_f09_batch_icp_tools(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_authz",
        )
        tool_ids = {s["tool_id"] for s in plan["steps"]}
        self.assertTrue(all(not t.startswith("F09") for t in tool_ids))
        self.assertNotIn("BATCH_PARCEL_SEARCH", tool_ids)
        self.assertNotIn("ICP_FINDER", tool_ids)
        execution = execute_plan(plan, fixtures=_mireye_fixtures())
        self.assertFalse(execution["constraints"]["f09_authorized"])
        self.assertFalse(execution["constraints"]["batch_authorized"])
        self.assertFalse(execution["constraints"]["icp_authorized"])

    def test_18_no_network_calls(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_net",
        )

        def boom(*args, **kwargs):
            raise AssertionError("network_call_attempted")

        with mock.patch("urllib.request.urlopen", side_effect=boom):
            with mock.patch("urllib.request.Request", side_effect=boom):
                execution = execute_plan(plan, fixtures=_mireye_fixtures(blocked=True))
        self.assertFalse(execution["constraints"]["live_network"])
        self.assertFalse(execution["constraints"]["live_mireye_attempted"])

    def test_19_credentials_absent(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_creds",
        )
        execution = execute_plan(plan, fixtures=_mireye_fixtures(blocked=True))
        blob = json.dumps({k: v for k, v in execution.items() if k != "_artifact_store"})
        self.assertNotRegex(blob, r"(?i)authorization")
        self.assertNotRegex(blob, r"(?i)api[_-]?key")
        self.assertNotRegex(blob, r"(?i)bearer\s+\w+")

    def test_20_timestamps_excluded_from_hash(self):
        plan = _plan(
            "GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            plan_id="cper_ts",
        )
        execution = execute_plan(plan, fixtures=_mireye_fixtures())
        mutated = deepcopy({k: v for k, v in execution.items() if k != "_artifact_store"})
        mutated["started_at"] = "1999-01-01T00:00:00+00:00"
        mutated["completed_at"] = "1999-01-01T00:00:01+00:00"
        for step in mutated["steps"]:
            step["started_at"] = "1999-01-01T00:00:00+00:00"
            step["completed_at"] = "1999-01-01T00:00:01+00:00"
        self.assertEqual(
            deterministic_execution_hash(mutated),
            execution["deterministic_execution_hash"],
        )


if __name__ == "__main__":
    unittest.main()
