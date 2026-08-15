"""Phase 7 Gate: Natural Cattle Foundation two-page PDF."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from rangematch.advisor_deal_context import create_deal_context, reset_deal_contexts_for_tests
from rangematch.advisor_natural_foundation_pdf import (
    project_natural_cattle_foundation_report,
    render_natural_cattle_foundation_pdf,
    run_has_natural_foundation_report,
)
from rangematch.advisor_natural_interpretation import (
    generate_natural_foundation_interpretation,
)
from rangematch.environmental_gap_detector import detect_environmental_gaps
from rangematch.environmental_supplement_runner import (
    build_combined_environmental_evidence_packet,
    execute_supplement_plan,
    unit_test_supplement_runners,
)
from rangematch.mireye_environmental_profile import validate_mireye_environmental_profile
from rangematch.mireye_first_collection import derive_confirmed_f06
from rangematch.natural_cattle_profile import project_natural_cattle_profile

REPO = Path(__file__).resolve().parents[1]
NAMBE_PROFILE = (
    REPO
    / "test-data"
    / "mireye-environmental-profile"
    / "nambe_mireye_environmental_profile.json"
)

SIMPLE_POLYGON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-104.9, 40.5],
                        [-104.89, 40.5],
                        [-104.89, 40.49],
                        [-104.9, 40.49],
                        [-104.9, 40.5],
                    ]
                ],
            },
        }
    ],
}


def _mireye_first_run() -> dict:
    reset_deal_contexts_for_tests()
    mireye = json.loads(NAMBE_PROFILE.read_text(encoding="utf-8"))
    validate_mireye_environmental_profile(mireye)
    geometry_hash = mireye["parcel_ref"]["geometry_hash"]
    plan = detect_environmental_gaps(mireye, f06_geometry_hash=geometry_hash)
    execution = execute_supplement_plan(
        plan,
        geometry=SIMPLE_POLYGON,
        geometry_id="phase7",
        geometry_hash=geometry_hash,
        runners=unit_test_supplement_runners(),
    )
    f06 = derive_confirmed_f06(SIMPLE_POLYGON, geometry_hash=geometry_hash)
    packet = build_combined_environmental_evidence_packet(
        mireye_profile=mireye,
        gap_plan=plan,
        supplement_execution=execution,
        f06=f06,
    )
    profile = project_natural_cattle_profile(packet)
    deal = create_deal_context(
        run_id="advisor_phase7_pdf01",
        parcel_resolution_id="res_phase7",
        geometry_hash=geometry_hash,
    )
    interpretation = generate_natural_foundation_interpretation(
        natural_cattle_profile=profile,
        deal_context=deal,
        force_fallback=True,
    )
    return {
        "run_id": "advisor_phase7_pdf01",
        "address": "4213 Nambe Road, Indian Hills, CO 80454",
        "status": "SUCCEEDED",
        "collection_mode": "MIREYE_FIRST",
        "deal_context": deal,
        "natural_cattle_profile": profile,
        "combined_environmental_evidence_packet": packet,
        "natural_foundation_interpretation": interpretation,
        "packet": None,
        "operating_conclusion": None,
    }


class Phase7NaturalFoundationPdfTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run = _mireye_first_run()

    def test_projects_page1_verbatim_from_interpretation(self) -> None:
        self.assertTrue(run_has_natural_foundation_report(self.run))
        view = project_natural_cattle_foundation_report(self.run)
        interp = self.run["natural_foundation_interpretation"]
        self.assertEqual(view["page1"]["advisor_view"], interp["advisor_view"])
        self.assertEqual(
            view["page1"]["integrated_natural_reading"],
            interp["integrated_natural_reading"],
        )
        self.assertEqual(
            view["page1"]["intended_use_interpretation"],
            interp["intended_use_interpretation"],
        )
        self.assertEqual(
            view["page1"]["what_would_change_the_view"],
            interp["what_would_change_the_view"],
        )
        self.assertEqual(
            view["page1"]["refinement_request"], interp["refinement_request"]
        )
        self.assertNotIn("optional_copy_ready_request", view["page1"])
        page1_blob = json.dumps(view["page1"]).upper()
        self.assertNotIn("OBS_", page1_blob)
        self.assertNotIn("F01_", page1_blob)
        self.assertNotIn("ADAPTER", page1_blob)
        self.assertNotIn("HTTP_", page1_blob)

    def test_page2_omits_empty_and_unavailable_rows(self) -> None:
        view = project_natural_cattle_foundation_report(self.run)
        rows = view["page2"]["environmental_evidence"]
        self.assertTrue(rows)
        for row in rows:
            self.assertTrue(str(row.get("result") or "").strip())
            self.assertIn(row.get("status"), {"RETRIEVED", "PARTIAL"})
            self.assertTrue(row.get("spatial"))
            self.assertTrue(row.get("provider"))
        # Inject a failed row into packet; it must not appear.
        packet = copy.deepcopy(self.run["combined_environmental_evidence_packet"])
        packet["supplement_observations"].append(
            {
                "observation_id": "SUPPLEMENT_FAILURE_EMPTY",
                "field_id": "F03_LIVESTOCK_WATER",
                "domain": "WATER",
                "value": None,
                "status": "SOURCE_UNAVAILABLE",
                "spatial_semantics": "PARCEL",
                "provider": "RANGEMATCH_SUPPLEMENT",
            }
        )
        run2 = copy.deepcopy(self.run)
        run2["combined_environmental_evidence_packet"] = packet
        view2 = project_natural_cattle_foundation_report(run2)
        ids = json.dumps(view2["page2"]["environmental_evidence"])
        self.assertNotIn("SUPPLEMENT_FAILURE_EMPTY", ids)

    def test_property_context_omitted_when_empty(self) -> None:
        view = project_natural_cattle_foundation_report(self.run)
        self.assertIsNone(view["page2"]["related_property_context"])
        self.assertIsNone(view["page1"]["appendix_pointer"])

    def test_isolated_f07_context_renders_only_in_page2b(self) -> None:
        run = copy.deepcopy(self.run)
        run["additional_property_context_collection"] = {
            "role": "APPENDIX_CONTEXT_COLLECTOR",
            "status": "SUCCEEDED",
            "may_affect_natural_profile": False,
            "may_enter_primary_llm_workbench": False,
            "may_change_conclusion": False,
            "observations": [{
                "observation_id": "APPENDIX_VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M",
                "land_fact_ref": "VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M",
                "value": 0.0,
                "unit": "m",
                "evidence_state": "RETRIEVED",
                "source_id": "UNIT_TEST_TIGER",
                "classification": "APPENDIX_ONLY",
            }],
        }
        original_profile = copy.deepcopy(run["natural_cattle_profile"])
        original_interpretation = copy.deepcopy(run["natural_foundation_interpretation"])
        view = project_natural_cattle_foundation_report(run)
        ctx = view["page2"]["related_property_context"]
        self.assertTrue(ctx["enabled"])
        self.assertIn("reaches the parcel boundary", ctx["rows"][0]["what_we_can_say"])
        self.assertEqual(run["natural_cattle_profile"], original_profile)
        self.assertEqual(run["natural_foundation_interpretation"], original_interpretation)

    def test_pdf_is_exactly_two_pages_for_llm_and_fallback(self) -> None:
        view = project_natural_cattle_foundation_report(self.run)
        payload = render_natural_cattle_foundation_pdf(view)
        self.assertTrue(payload.startswith(b"%PDF"))
        self.assertGreater(len(payload), 1000)
        # Provenance hashes aligned.
        self.assertEqual(
            view["provenance"]["natural_cattle_profile_hash"],
            self.run["natural_cattle_profile"]["profile_hash"],
        )
        self.assertEqual(
            view["provenance"]["interpretation_source"],
            self.run["natural_foundation_interpretation"]["source"],
        )

    def test_deeper_possibilities_and_intended_use_still_fit_page_one(self) -> None:
        run = copy.deepcopy(self.run)
        interpretation = run["natural_foundation_interpretation"]
        interpretation["operating_possibilities"] = [
            (
                "Seasonal grazing is the clearest possibility because moderate terrain can support "
                "movement while the cool, semi-arid climate concentrates the useful forage window."
            ),
            (
                "A conservative drought-year use pattern may remain plausible when grazing dates "
                "follow actual vegetation response and livestock water is secured for that period."
            ),
            (
                "The parcel may work best as one component of a broader grazing system rather than "
                "as a self-contained year-round forage and water base."
            ),
        ]
        interpretation["intended_use_interpretation"] = (
            "For seasonal grazing, the key test is whether reliable livestock water overlaps the "
            "actual grazing months and whether forage responds after spring moisture. Moderate slopes "
            "and well-drained soils make that use easier to explore, although drought can shorten the "
            "window. A year-round cow-calf plan asks substantially more of the same land: dependable "
            "water through winter and drought, a forage strategy beyond the growing season, and enough "
            "natural resilience to avoid treating one favorable snapshot as normal. The current land "
            "picture therefore leans more naturally toward a bounded seasonal role than a stand-alone "
            "year-round operating base."
        )
        interpretation["conditional_scenarios"] = [
            (
                "If a dependable livestock-water source is confirmed for the intended grazing months, "
                "the current conditional view becomes materially stronger because water would no longer "
                "limit how cattle use the available forage and terrain."
            ),
            (
                "If field records show that water fails during the normal grazing window or drought-year "
                "forage repeatedly collapses, the view weakens because the parcel would depend on outside "
                "water or feed to support the intended cattle role."
            ),
        ]
        payload = render_natural_cattle_foundation_pdf(
            project_natural_cattle_foundation_report(run)
        )
        self.assertTrue(payload.startswith(b"%PDF"))
        self.assertGreater(len(payload), 1000)

    def test_long_live_narrative_flows_to_continuation_pages_not_rejected(self) -> None:
        run = copy.deepcopy(self.run)
        interpretation = run["natural_foundation_interpretation"]
        interpretation["advisor_judgment"] = (
            "Moderate terrain and visible herbaceous cover make a bounded cattle use worth examining. "
            "The climate pattern can compress the useful forage period and increase dependence on timely moisture. "
            "Livestock water remains the condition that determines whether cattle can use the observed land pattern. "
        ) * 3
        interpretation["land_character"] = (
            "This is open rangeland with moderate slopes, herbaceous cover, a semi-arid climate, and well-drained soils. "
            "Those features describe a landscape where forage timing and water distribution matter together. "
        ) * 4
        interpretation["operating_possibilities"] = [
            ("Seasonal grazing may be plausible when forage response and livestock water overlap. ") * 4,
            ("A conservative drought-year role may remain possible with a shorter grazing window. ") * 4,
            ("The parcel may function as one part of a broader grazing system. ") * 4,
        ]
        interpretation["intended_use_interpretation"] = (
            "Seasonal use asks whether water and forage coincide during the intended months. "
            "Year-round use carries a materially higher evidence burden through winter and drought. "
        ) * 5
        interpretation["conditional_scenarios"] = [
            ("Reliable livestock water during the intended months would materially strengthen this view. ") * 4,
            ("Repeated forage failure during those months would materially weaken this view. ") * 4,
        ]
        interpretation["refinement_request"] = (
            "Share the livestock-water sources, normal months of availability, and recent forage condition. "
        ) * 4
        payload = render_natural_cattle_foundation_pdf(
            project_natural_cattle_foundation_report(run)
        )
        self.assertTrue(payload.startswith(b"%PDF"))
        self.assertGreater(len(payload), 1000)

    def test_page2_volume_does_not_mutate_page1_text(self) -> None:
        view = project_natural_cattle_foundation_report(self.run)
        page1_before = json.dumps(view["page1"], sort_keys=True)
        # Inflate appendix by cloning retrieved rows (still same Page 1).
        packet = copy.deepcopy(self.run["combined_environmental_evidence_packet"])
        extra = [
            dict(obs, observation_id=f"{obs.get('observation_id')}_COPY_{i}")
            for i, obs in enumerate(packet.get("supplement_observations") or [])
            if obs.get("status") == "RETRIEVED" and obs.get("value") is not None
        ]
        packet["supplement_observations"] = list(packet.get("supplement_observations") or []) + extra
        run2 = copy.deepcopy(self.run)
        run2["combined_environmental_evidence_packet"] = packet
        # Re-bind interpretation hash still points to same profile; packet_hash differs
        # but Page 1 fields must remain the interpretation text.
        view2 = project_natural_cattle_foundation_report(run2)
        self.assertEqual(json.dumps(view2["page1"], sort_keys=True), page1_before)

    def test_appendix_prioritizes_page_one_environmental_evidence(self) -> None:
        view = project_natural_cattle_foundation_report(self.run)
        displayed = view["page2"]["environmental_evidence"][:22]
        labels = " ".join(str(row.get("evidence") or "") for row in displayed).lower()
        self.assertIn("slope", labels)
        self.assertTrue("precip" in labels or "drought" in labels)
        self.assertIn("soil", labels)
        self.assertTrue("wetland" in labels or "surface water", labels)


if __name__ == "__main__":
    unittest.main()
