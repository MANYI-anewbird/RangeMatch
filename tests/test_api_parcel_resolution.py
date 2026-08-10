"""API tests for parcel resolution endpoints + investigation integration."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from rangematch.api import app, reset_store_for_tests


ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "test-data" / "parcel-resolution"
CPER_REF = "test-data/land-profiles/land_profile_cper_001.json"


def _scenario(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


class ParcelResolutionAPITests(unittest.TestCase):
    def setUp(self) -> None:
        reset_store_for_tests()
        self.client = TestClient(app)

    def _create(self, scenario_id: str, *, resolver_mode: str = "FIXTURE") -> dict:
        sc = _scenario(scenario_id)
        if str(sc.get("input_kind") or "ADDRESS").upper() == "COORDINATE":
            payload = {
                "input_kind": "COORDINATE",
                "latitude": sc["latitude"],
                "longitude": sc["longitude"],
                "resolver_mode": resolver_mode,
                "fixture_scenario_id": scenario_id if resolver_mode == "FIXTURE" else None,
            }
        else:
            payload = {
                "input_kind": "ADDRESS",
                "address": sc["raw_address"],
                "resolver_mode": resolver_mode,
                "fixture_scenario_id": scenario_id if resolver_mode == "FIXTURE" else None,
            }
        r = self.client.post("/v1/parcel-resolutions", json=payload)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_01_single_candidate_creation(self):
        body = self._create("one_valid_candidate")
        self.assertEqual(body["status"], "NEEDS_BOUNDARY_CONFIRMATION")
        self.assertEqual(len(body["candidates"]), 1)
        self.assertEqual(
            body["normalized_address"],
            _scenario("one_valid_candidate")["normalized_address"],
        )
        self.assertIn("provenance", body)
        self.assertIn("limitations", body)
        self.assertFalse(body["confirmation_status"]["confirmed"])
        self.assertFalse(body["evidence_invalidation_required"])

    def test_02_multiple_candidates(self):
        body = self._create("multiple_candidates")
        self.assertEqual(body["status"], "NEEDS_USER_SELECTION")
        self.assertGreaterEqual(len(body["candidates"]), 2)

    def test_03_no_match(self):
        body = self._create("no_match")
        self.assertEqual(body["status"], "NO_MATCH")

    def test_04_blocked_external_live(self):
        r = self.client.post(
            "/v1/parcel-resolutions",
            json={
                "address": "123 Main St, Denver, CO 80202",
                "resolver_mode": "LIVE",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "BLOCKED_EXTERNAL")
        blob = json.dumps(body)
        self.assertNotIn("engineering_test_geometry_cper", blob)

    def test_05_get_unknown_id(self):
        r = self.client.get("/v1/parcel-resolutions/pres_does_not_exist")
        self.assertEqual(r.status_code, 404)

    def test_06_confirmation_success(self):
        created = self._create("one_valid_candidate")
        cand = created["candidates"][0]
        r = self.client.post(
            f"/v1/parcel-resolutions/{created['resolution_id']}/confirm",
            json={
                "selected_candidate_id": cand["candidate_id"],
                "expected_geometry_hash": cand["geometry_hash"],
                "explicit_confirmation": True,
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "PARCEL_CONFIRMED")
        self.assertTrue(body["confirmation_status"]["confirmed"])
        binding = body["planner_binding"]
        self.assertEqual(binding["source_crs"], "EPSG:4326")
        self.assertEqual(binding["geometry_hash"], cand["geometry_hash"])
        self.assertEqual(binding["parcel_geometry"]["type"], "FeatureCollection")
        self.assertEqual(len(binding["parcel_geometry"]["features"]), 1)

    def test_07_missing_explicit_confirmation(self):
        created = self._create("one_valid_candidate")
        cand = created["candidates"][0]
        r = self.client.post(
            f"/v1/parcel-resolutions/{created['resolution_id']}/confirm",
            json={
                "selected_candidate_id": cand["candidate_id"],
                "expected_geometry_hash": cand["geometry_hash"],
                "explicit_confirmation": False,
            },
        )
        self.assertEqual(r.status_code, 422)

        r2 = self.client.post(
            f"/v1/parcel-resolutions/{created['resolution_id']}/confirm",
            json={
                "selected_candidate_id": cand["candidate_id"],
                "expected_geometry_hash": cand["geometry_hash"],
            },
        )
        self.assertEqual(r2.status_code, 422)

    def test_08_wrong_candidate(self):
        created = self._create("one_valid_candidate")
        cand = created["candidates"][0]
        r = self.client.post(
            f"/v1/parcel-resolutions/{created['resolution_id']}/confirm",
            json={
                "selected_candidate_id": "cand_does_not_exist",
                "expected_geometry_hash": cand["geometry_hash"],
                "explicit_confirmation": True,
            },
        )
        self.assertIn(r.status_code, {400, 404})

    def test_09_stale_geometry_hash(self):
        created = self._create("one_valid_candidate")
        cand = created["candidates"][0]
        stale = "0" * 64
        r = self.client.post(
            f"/v1/parcel-resolutions/{created['resolution_id']}/confirm",
            json={
                "selected_candidate_id": cand["candidate_id"],
                "expected_geometry_hash": stale,
                "explicit_confirmation": True,
            },
        )
        self.assertEqual(r.status_code, 409, r.text)
        self.assertIn("STALE_GEOMETRY_HASH", r.text)

    def test_10_repeated_confirmation_idempotent(self):
        created = self._create("one_valid_candidate")
        cand = created["candidates"][0]
        payload = {
            "selected_candidate_id": cand["candidate_id"],
            "expected_geometry_hash": cand["geometry_hash"],
            "explicit_confirmation": True,
        }
        a = self.client.post(
            f"/v1/parcel-resolutions/{created['resolution_id']}/confirm",
            json=payload,
        ).json()
        b = self.client.post(
            f"/v1/parcel-resolutions/{created['resolution_id']}/confirm",
            json=payload,
        ).json()
        self.assertEqual(a["status"], "PARCEL_CONFIRMED")
        self.assertEqual(b["status"], "PARCEL_CONFIRMED")
        self.assertEqual(
            a["planner_binding"]["geometry_hash"],
            b["planner_binding"]["geometry_hash"],
        )
        self.assertEqual(
            a["confirmed_parcel"]["geometry_hash"],
            b["confirmed_parcel"]["geometry_hash"],
        )

    def test_11_investigation_from_confirmed_resolution(self):
        created = self._create("one_valid_candidate")
        cand = created["candidates"][0]
        confirmed = self.client.post(
            f"/v1/parcel-resolutions/{created['resolution_id']}/confirm",
            json={
                "selected_candidate_id": cand["candidate_id"],
                "expected_geometry_hash": cand["geometry_hash"],
                "explicit_confirmation": True,
            },
        ).json()
        r = self.client.post(
            "/v1/investigations",
            json={
                "parcel_resolution_id": confirmed["resolution_id"],
                "mode": "DISCOVERY",
                "intended_operation": None,
                "execution_source": "PARCEL_RESOLUTION",
                "mireye_mode": "BLOCKED_EXTERNAL",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "QUEUED")
        self.assertEqual(body["execution_source"], "PARCEL_RESOLUTION")
        self.assertEqual(body["geometry_hash"], cand["geometry_hash"])
        self.assertEqual(body["parcel_resolution_id"], confirmed["resolution_id"])
        done = self.client.get(f"/v1/investigations/{body['investigation_id']}").json()
        self.assertIn(done["status"], {"PARTIAL", "COMPLETED", "FAILED"})
        lim = " ".join(done.get("limitations") or [])
        self.assertIn("no_automatic_cper_fixture_substitution", lim)
        self.assertNotIn("engineering_test_geometry_cper", json.dumps(done))

    def test_12_investigation_blocked_before_confirmation(self):
        created = self._create("one_valid_candidate")
        r = self.client.post(
            "/v1/investigations",
            json={
                "parcel_resolution_id": created["resolution_id"],
                "mode": "DISCOVERY",
                "execution_source": "PARCEL_RESOLUTION",
            },
        )
        self.assertEqual(r.status_code, 409)
        self.assertIn("parcel_resolution_not_confirmed", r.text)

    def test_13_conflicting_parcel_inputs_rejected(self):
        created = self._create("one_valid_candidate")
        r = self.client.post(
            "/v1/investigations",
            json={
                "parcel_resolution_id": created["resolution_id"],
                "existing_land_profile_reference": CPER_REF,
                "mode": "DISCOVERY",
                "execution_source": "PARCEL_RESOLUTION",
            },
        )
        self.assertEqual(r.status_code, 422)

        r2 = self.client.post(
            "/v1/investigations",
            json={
                "parcel_resolution_id": created["resolution_id"],
                "mode": "DISCOVERY",
                "execution_source": "DEMO_FIXTURE",
            },
        )
        self.assertEqual(r2.status_code, 422)

    def test_14_no_cper_substitution_on_unrelated_address(self):
        r = self.client.post(
            "/v1/parcel-resolutions",
            json={
                "address": "123 Unrelated Main St, Denver, CO 80202",
                "resolver_mode": "FIXTURE",
                "fixture_scenario_id": "silent_cper_substitution",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "INVALID_GEOMETRY")
        self.assertTrue(
            any(
                "SILENT_CPER_SUBSTITUTION_REJECTED" in (c.get("validation_errors") or [])
                for c in body["candidates"]
            )
        )

    def test_15_no_credentials_in_resolution_responses(self):
        body = self._create("one_valid_candidate")
        blob = json.dumps(body).lower()
        self.assertNotIn("authorization", blob)
        self.assertNotIn("api_key", blob)
        self.assertNotIn("bearer ", blob)
        self.assertNotIn("password", blob)

    def test_16_existing_demo_fixture_path_compatible(self):
        r = self.client.post(
            "/v1/investigations",
            json={
                "existing_land_profile_reference": CPER_REF,
                "mode": "GOAL_DIRECTED",
                "intended_operation": "COW_CALF_OPERATION",
                "execution_source": "DEMO_FIXTURE",
                "mireye_mode": "BLOCKED_EXTERNAL",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = self.client.get(
            f"/v1/investigations/{r.json()['investigation_id']}"
        ).json()
        self.assertIn(body["status"], {"COMPLETED", "PARTIAL"})
        self.assertIsNotNone(body.get("unified_output"))

    def test_17_get_resolution_after_create(self):
        created = self._create("multiple_candidates")
        g = self.client.get(f"/v1/parcel-resolutions/{created['resolution_id']}")
        self.assertEqual(g.status_code, 200)
        body = g.json()
        self.assertEqual(body["resolution_id"], created["resolution_id"])
        self.assertEqual(body["status"], "NEEDS_USER_SELECTION")
        self.assertIn("candidates", body)
        self.assertIn("provenance", body)
        self.assertIn("confirmation_status", body)

    def test_18_health_reports_parcel_resolver_live(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["parcel_resolver_live"], "NOT_CONFIGURED")
        self.assertEqual(body["storage"], "in_memory_ephemeral")

    def test_19_coordinate_one_candidate_and_confirm(self):
        body = self._create("coord_one_valid_candidate")
        self.assertEqual(body["status"], "NEEDS_BOUNDARY_CONFIRMATION")
        self.assertEqual(body["input_kind"], "COORDINATE")
        self.assertEqual(body["latitude"], 40.495)
        self.assertEqual(body["longitude"], -104.895)
        self.assertEqual(len(body["candidates"]), 1)
        cand = body["candidates"][0]
        conf = self.client.post(
            f"/v1/parcel-resolutions/{body['resolution_id']}/confirm",
            json={
                "selected_candidate_id": cand["candidate_id"],
                "expected_geometry_hash": cand["geometry_hash"],
                "explicit_confirmation": True,
            },
        )
        self.assertEqual(conf.status_code, 200, conf.text)
        self.assertEqual(conf.json()["status"], "PARCEL_CONFIRMED")

    def test_20_coordinate_swap_and_outside_us_rejected(self):
        # Classic swap: lng,lat entered as lat,lng for a US point
        r = self.client.post(
            "/v1/parcel-resolutions",
            json={
                "input_kind": "COORDINATE",
                "latitude": -104.895,
                "longitude": 40.495,
                "resolver_mode": "FIXTURE",
                "fixture_scenario_id": "coord_one_valid_candidate",
            },
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("COORDINATES_APPEAR_SWAPPED", r.json()["detail"])

        r2 = self.client.post(
            "/v1/parcel-resolutions",
            json={
                "input_kind": "COORDINATE",
                "latitude": 0.0,
                "longitude": 0.0,
                "resolver_mode": "FIXTURE",
            },
        )
        self.assertEqual(r2.status_code, 400)
        self.assertIn("COORDINATES_OUTSIDE_US", r2.json()["detail"])

    def test_21_live_mireye_requires_explicit_network_authorization(self):
        created = self._create("one_valid_candidate")
        cand = created["candidates"][0]
        confirmed = self.client.post(
            f"/v1/parcel-resolutions/{created['resolution_id']}/confirm",
            json={
                "selected_candidate_id": cand["candidate_id"],
                "expected_geometry_hash": cand["geometry_hash"],
                "explicit_confirmation": True,
            },
        ).json()
        denied = self.client.post(
            "/v1/investigations",
            json={
                "parcel_resolution_id": confirmed["resolution_id"],
                "mode": "DISCOVERY",
                "execution_source": "PARCEL_RESOLUTION",
                "mireye_mode": "LIVE",
            },
        )
        self.assertEqual(denied.status_code, 422)

    def test_22_live_mireye_contexts_enter_executor_without_factor_authority(self):
        import sys
        from types import ModuleType
        from unittest.mock import MagicMock

        created = self._create("one_valid_candidate")
        cand = created["candidates"][0]
        confirmed = self.client.post(
            f"/v1/parcel-resolutions/{created['resolution_id']}/confirm",
            json={
                "selected_candidate_id": cand["candidate_id"],
                "expected_geometry_hash": cand["geometry_hash"],
                "explicit_confirmation": True,
            },
        ).json()
        norm = ROOT / "test-data/mireye-normalized/normalized"
        contexts = {
            "PROPERTY_DILIGENCE_CONTEXT": json.loads((norm / "lookup_resolved.normalized.json").read_text()),
            "POINT_LAND_CONTEXT": json.loads((norm / "point_land_complete.normalized.json").read_text()),
            "POINT_HAZARD_CONTEXT": json.loads((norm / "point_hazard_complete.normalized.json").read_text()),
        }
        collected = {
            "contexts": contexts,
            "errors": {},
            "transport_meta": {},
            "requested_point": {"lat": 40.0, "lng": -104.0},
            "canonical_for_parcel_facts": False,
        }
        f01 = json.loads((ROOT / CPER_REF).read_text())["factors"]["F01_TOPOGRAPHY"]
        profile_factors = json.loads((ROOT / CPER_REF).read_text())["factors"]
        rap_result = {
            "factors": {
                "F02_HERBACEOUS_RESOURCE": profile_factors["F02_HERBACEOUS_RESOURCE"],
                "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE": profile_factors["F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"],
            },
            "cover_request_count": 1,
            "production_request_count": 1,
            "cover_response_hash": "a" * 64,
            "duplicate_coverV3_fetch": False,
        }
        f05 = profile_factors["F05_CLIMATE_DROUGHT_EXPOSURE"]
        f07 = profile_factors["F07_ROAD_AND_PHYSICAL_ACCESS"]
        f03 = profile_factors["F03_LIVESTOCK_WATER"]
        f04 = profile_factors["F04_SOIL_WETNESS_ECOLOGICAL_SITE"]

        prior: dict[str, object] = {}

        def _stub(name: str, **attrs: object) -> ModuleType:
            mod = ModuleType(name)
            for key, value in attrs.items():
                setattr(mod, key, value)
            prior[name] = sys.modules.get(name)
            sys.modules[name] = mod
            return mod

        err = type("AdapterError", (Exception,), {})
        collect_f01 = MagicMock(return_value=f01)
        collect_rap = MagicMock(return_value=rap_result)
        collect_f03 = MagicMock(return_value=f03)
        collect_f04 = MagicMock(return_value=f04)
        collect_f05 = MagicMock(return_value=f05)
        collect_f07 = MagicMock(
            return_value={**f07, "_collection": {"features": ["not-for-land-profile"]}}
        )
        try:
            _stub(
                "rangematch.f01_3dep_adapter",
                collect_f01_from_usgs_3dep=collect_f01,
                F01AdapterError=err,
            )
            _stub(
                "rangematch.f02_rap_adapter",
                collect_f02_f08_from_rap=collect_rap,
                F02RAPAdapterError=err,
            )
            _stub(
                "rangematch.f03_nhd_adapter",
                collect_f03_from_usgs_nhd=collect_f03,
                F03NHDAdapterError=err,
            )
            _stub(
                "rangematch.f04_sda_adapter",
                collect_f04_from_usda_sda=collect_f04,
                F04SDAAdapterError=err,
            )
            _stub(
                "rangematch.f05_noaa_adapter",
                collect_f05_from_noaa_normals=collect_f05,
                F05NOAAAdapterError=err,
            )
            _stub(
                "rangematch.f07_tiger_adapter",
                derive_f07_via_tiger_adapter=collect_f07,
            )

            with patch(
                "rangematch.mireye_adapter.collect_live_mireye_contexts",
                return_value=collected,
            ) as collect:
                response = self.client.post(
                    "/v1/investigations",
                    json={
                        "parcel_resolution_id": confirmed["resolution_id"],
                        "mode": "DISCOVERY",
                        "execution_source": "PARCEL_RESOLUTION",
                        "mireye_mode": "LIVE",
                        "allow_network": True,
                    },
                )
            self.assertEqual(response.status_code, 200, response.text)
            collect.assert_called_once()
            collect_f01.assert_called_once()
            collect_rap.assert_called_once()
            collect_f03.assert_called_once()
            collect_f04.assert_called_once()
            collect_f05.assert_called_once()
            collect_f07.assert_called_once()
            queued = response.json()
            self.assertEqual(queued["status"], "QUEUED")
            body = self.client.get(
                f"/v1/investigations/{queued['investigation_id']}"
            ).json()
            self.assertIn("live_mireye_contexts_noncanonical_for_parcel_facts", body["limitations"])
            self.assertIn(
                "f01_f08_confirmed_parcel_collection_attempted",
                body["limitations"],
            )
            self.assertEqual(
                body["live_factor_summary"]["computed_factors"],
                ["F01_TOPOGRAPHY", "F02_HERBACEOUS_RESOURCE", "F03_LIVESTOCK_WATER", "F04_SOIL_WETNESS_ECOLOGICAL_SITE", "F05_CLIMATE_DROUGHT_EXPOSURE", "F07_ROAD_AND_PHYSICAL_ACCESS", "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"],
            )
            self.assertEqual(body["live_factor_summary"]["failed_factors"], {})
            self.assertEqual(body["live_factor_summary"]["rap_acquisition"]["cover_request_count"], 1)
            self.assertTrue(body["live_factor_summary"]["rap_acquisition"]["f08_reuses_f02_cover_artifact"])
            self.assertFalse(body["mireye_live_summary"]["canonical_for_parcel_facts"])
            self.assertEqual(body["mireye_live_summary"]["failed_contexts"], [])
            self.assertEqual(len(body["mireye_live_summary"]["context_status"]), 3)
            f05_output = body["unified_output"]["factors"]["F05_CLIMATE_DROUGHT_EXPOSURE"]
            self.assertTrue(
                any(
                    fact["variable_id"] == "VAR_F05_MEAN_ANNUAL_PRECIPITATION"
                    for fact in f05_output["land_facts"]
                )
            )
            f07_output = body["unified_output"]["factors"]["F07_ROAD_AND_PHYSICAL_ACCESS"]
            self.assertEqual(f07_output["ranking_effect"], "NONE")
            self.assertTrue(
                any(
                    fact["variable_id"] == "VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M"
                    for fact in f07_output["land_facts"]
                )
            )
            self.assertNotIn("_collection", f07_output)
            f03_output = body["unified_output"]["factors"]["F03_LIVESTOCK_WATER"]
            self.assertTrue(
                any(
                    fact["variable_id"] == "VAR_F03_FIELD_VERIFIED_LIVESTOCK_WATER_COUNT"
                    and fact["value"] == 0
                    for fact in f03_output["land_facts"]
                )
            )
            f04_output = body["unified_output"]["factors"]["F04_SOIL_WETNESS_ECOLOGICAL_SITE"]
            self.assertTrue(
                any(
                    fact["variable_id"] == "VAR_F04_SDA_VALID_COVERAGE_FRACTION"
                    for fact in f04_output["land_facts"]
                )
            )
            trace = self.client.get(f"/v1/investigations/{body['investigation_id']}/trace").json()
            mireye_steps = [s for s in trace["steps"] if str(s.get("tool_id", "")).startswith("mireye.")]
            self.assertEqual(len(mireye_steps), 3)
            self.assertTrue(all(s["status"] == "SUCCEEDED" for s in mireye_steps))
        finally:
            for name, old in prior.items():
                if old is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = old  # type: ignore[assignment]

    def test_21_address_rejects_lat_lng_fields(self):
        r = self.client.post(
            "/v1/parcel-resolutions",
            json={
                "input_kind": "ADDRESS",
                "address": "100 Demo Ranch Rd, Weld County, CO 80701",
                "latitude": 40.495,
                "longitude": -104.895,
                "resolver_mode": "FIXTURE",
                "fixture_scenario_id": "one_valid_candidate",
            },
        )
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
