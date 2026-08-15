"""HUMAN_ACCESS_INFRA_APPENDIX_ONLY — Additional Property Context contract tests."""

from __future__ import annotations

import unittest
from unittest import mock

from rangematch.advisor_property_context_appendix import (
    HUMAN_ACCESS_INFRA_APPENDIX_ONLY,
    MAXIMUM_ROWS,
    PAGE1_APPENDIX_POINTER,
    project_additional_property_context,
    validate_additional_property_context_rows,
    validate_property_context_against_primary,
)
from rangematch.advisor_property_context_collector import (
    collect_additional_property_context,
)
from rangematch.advisor_snapshot import (
    project_cattle_operating_snapshot,
    render_cattle_operating_snapshot_pdf,
    validate_snapshot_view,
)


def _road_obs(*, value: float = 0.0, state: str = "MAPPED_CANDIDATE") -> dict:
    return {
        "observation_id": "OBS_ROAD",
        "label": "Nearest mapped road distance",
        "value": value,
        "unit": "m",
        "evidence_state": state,
        "source_id": "US_CENSUS_TIGER_LINE_2025_ALL_ROADS",
        "land_fact_ref": "VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M",
        "allowed_support": ["physical road contact on the map"],
        "prohibited_support": ["legal access", "usable entrance"],
    }


def _packet_with_road(**kwargs) -> dict:
    return {
        "observations": [
            {
                "observation_id": "OBS_AREA",
                "label": "Mapped geometric area",
                "value": 120000.0,
                "unit": "m2",
                "evidence_state": "PARCEL_DERIVED",
                "source_id": "CONFIRMED_GEOMETRY",
            },
            _road_obs(**kwargs),
        ]
    }


class PropertyContextAppendixContractTests(unittest.TestCase):
    def test_contract_flag_locked_true(self) -> None:
        self.assertTrue(HUMAN_ACCESS_INFRA_APPENDIX_ONLY)
        self.assertEqual(MAXIMUM_ROWS, 4)

    def test_empty_when_road_unavailable(self) -> None:
        packet = _packet_with_road(state="SOURCE_UNAVAILABLE", value=None)
        packet["observations"][1]["value"] = None
        ctx = project_additional_property_context(packet)
        self.assertFalse(ctx["enabled"])
        self.assertEqual(ctx["rows"], [])

    def test_projects_road_boundary_contact(self) -> None:
        ctx = project_additional_property_context(_packet_with_road(value=0.0))
        self.assertTrue(ctx["enabled"])
        self.assertEqual(len(ctx["rows"]), 1)
        row = ctx["rows"][0]
        self.assertEqual(row["topic"], "Mapped road context")
        self.assertIn("reaches the parcel boundary", row["what_we_can_say"])
        self.assertIn("does not establish", row["what_it_does_not_establish"].lower())
        self.assertEqual(ctx["contract"]["may_trigger_F07"], True)
        self.assertEqual(ctx["contract"]["collection_role"], "APPENDIX_CONTEXT_COLLECTOR")
        self.assertEqual(ctx["contract"]["may_change_conclusion"], False)
        self.assertEqual(ctx["page1_pointer"], PAGE1_APPENDIX_POINTER)
        self.assertFalse(validate_additional_property_context_rows(ctx["rows"]))

    def test_max_four_rows_enforced(self) -> None:
        observations = [_road_obs(value=float(i)) for i in range(6)]
        # Distinct obs ids still classified via VAR_F07_ prefix.
        for index, row in enumerate(observations):
            row["observation_id"] = f"OBS_ROAD_{index}"
            row["land_fact_ref"] = "VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M"
        ctx = project_additional_property_context({"observations": observations})
        self.assertLessEqual(len(ctx["rows"]), 4)
        self.assertFalse(validate_additional_property_context_rows(ctx["rows"]))

    def test_rejects_prohibited_access_claims(self) -> None:
        rows = [
            {
                "topic": "Mapped road context",
                "what_we_can_say": "The property has easy access.",
                "how_to_read_it": "Legal access is present.",
                "what_it_does_not_establish": "n/a",
            }
        ]
        violations = validate_additional_property_context_rows(rows)
        codes = {row["code"] for row in violations}
        self.assertIn("PROPERTY_CONTEXT_PROHIBITED_CLAIM", codes)

    def test_rejects_primary_access_controlling_language(self) -> None:
        ctx = project_additional_property_context(_packet_with_road(value=0.0))
        violations = validate_property_context_against_primary(
            property_context=ctx,
            primary_prose="The controlling issue is legal access for this ranch.",
        )
        self.assertTrue(
            any(row["code"] == "PROPERTY_CONTEXT_PRIMARY_LEAK" for row in violations)
        )

    def test_projection_never_calls_f07_collect(self) -> None:
        with mock.patch(
            "rangematch.tool_runners.run_adapter_tiger_roads", create=True
        ) as tiger:
            with mock.patch(
                "rangematch.advisor_generic_collect.collect_advisor_factors", create=True
            ) as collect:
                project_additional_property_context(_packet_with_road(value=12.0))
                tiger.assert_not_called()
                collect.assert_not_called()

    def test_isolated_collector_projects_only_buyer_useful_f07_context(self) -> None:
        result = collect_additional_property_context(
            geometry={"type": "Polygon", "coordinates": []},
            geometry_id="g1",
            geometry_hash="a" * 64,
            geometry_reference="geometry:test",
            runner=lambda: {
                "canonical_source_id": "UNIT_TEST_TIGER",
                "land_facts": [
                    {
                        "variable_id": "VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M",
                        "value": 12.0,
                        "unit": "m",
                    },
                    {
                        "variable_id": "VAR_F07_MAPPED_ROAD_FEATURE_COUNT_IN_SEARCH_WINDOW",
                        "value": 45,
                        "unit": "count",
                    },
                ],
            },
        )
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(len(result["observations"]), 1)
        self.assertEqual(
            result["observations"][0]["land_fact_ref"],
            "VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M",
        )
        self.assertFalse(result["may_affect_natural_profile"])
        self.assertFalse(result["may_enter_primary_llm_workbench"])

    def test_isolated_collector_failure_is_fail_soft(self) -> None:
        def boom():
            raise RuntimeError("road provider unavailable")

        result = collect_additional_property_context(
            geometry={"type": "Polygon", "coordinates": []},
            geometry_id="g1",
            geometry_hash="a" * 64,
            geometry_reference="geometry:test",
            runner=boom,
        )
        self.assertEqual(result["status"], "SOURCE_UNAVAILABLE")
        self.assertEqual(result["observations"], [])
        self.assertIn("road provider unavailable", result["error"])


class SnapshotPropertyContextIntegrationTests(unittest.TestCase):
    def _minimal_run(self, packet: dict) -> dict:
        return {
            "run_id": "snap_ctx_1",
            "address": "300 Mireye Ranch Rd, Weld County, CO 80701",
            "parcel_geometry_confirmed": True,
            "geometry_hash": "a" * 64,
            "packet_hash": "b" * 64,
            "operating_profile_hash": "c" * 64,
            "packet": packet,
            "deal_context": {
                "context_version": 1,
                "geometry_hash": "a" * 64,
                "operation_type": "UNKNOWN",
            },
            "operating_conclusion": {
                "deal_context_version": 1,
                "operating_profile_hash": "c" * 64,
                "headline": "Water verification is the controlling next step for this parcel",
                "summary": (
                    "This parcel shows a plausible forage base and manageable terrain, but "
                    "mapped water remains unverified for cattle use. The next step is to "
                    "confirm water presence with the seller before relying on seasonal grazing."
                ),
                "primary_constraint": "Unverified livestock water",
                "status": "CONDITIONAL",
                "confidence": "LOW",
                "next_action": "Request seller water records for this parcel.",
                "next_spend_class": "REMOTE_INFORMATION_REQUEST",
                "what_would_change_view": ["Documented water source reliability"],
                "next_question": {
                    "question_id": "q1",
                    "prompt": "Is this intended for seasonal grazing or year-round cow-calf?",
                },
                "source": "DETERMINISTIC_FALLBACK",
                "validation_status": "PASSED",
            },
            "operating_profile": {
                "profile_hash": "c" * 64,
                "operating_domains": {
                    "feed": {"statements": []},
                    "drink": {"statements": []},
                    "move": {"statements": []},
                },
            },
        }

    def test_snapshot_moves_road_to_additional_property_context(self) -> None:
        run = self._minimal_run(_packet_with_road(value=0.0))
        with mock.patch(
            "rangematch.advisor_snapshot.generate_snapshot_narrative",
            return_value={
                "content": {
                    "bottom_line": (
                        "This parcel looks workable for cattle only after water is verified; "
                        "terrain and vegetation currently look secondary to that gap."
                    ),
                    "what_changed": (
                        "No buyer answer has been recorded yet, so the view still rests on "
                        "the initial parcel evidence and unanswered operation type."
                    ),
                    "ranch_reading": (
                        "The land reads as a usable cattle candidate on terrain and forage "
                        "signals, while mapped water remains a lead rather than proof of a "
                        "reliable drinker across the intended season."
                    ),
                    "next_steps": (
                        "Ask the seller for water-source records and then plan a short field "
                        "check of the mapped water leads before relying on this pasture."
                    ),
                    "copy_and_send": (
                        "Please share any well, spring, pond, or pipeline records for this "
                        "parcel, including seasonal reliability notes if available."
                    ),
                },
                "source": "DETERMINISTIC_FALLBACK",
            },
        ):
            view = project_cattle_operating_snapshot(run)
        evidence_labels = {row["evidence"] for row in view["appendix"]["rows"]}
        self.assertNotIn("Nearest mapped road distance", evidence_labels)
        self.assertIn("Mapped geometric area", evidence_labels)
        ctx = view["appendix"]["additional_property_context"]
        self.assertTrue(ctx["enabled"])
        self.assertEqual(view["page1_property_context_pointer"], PAGE1_APPENDIX_POINTER)
        self.assertFalse(validate_snapshot_view(view))
        payload = render_cattle_operating_snapshot_pdf(view)
        self.assertTrue(payload.startswith(b"%PDF"))
        self.assertIn(b"/Count 2", payload)
        # Content streams are compressed; contract is enforced on the view model.
        self.assertEqual(ctx["rows"][0]["topic"], "Mapped road context")
        self.assertIn("does not establish a legal entrance", ctx["rows"][0]["what_it_does_not_establish"])

    def test_snapshot_omits_context_section_when_empty(self) -> None:
        packet = {
            "observations": [
                {
                    "observation_id": "OBS_AREA",
                    "label": "Mapped geometric area",
                    "value": 120000.0,
                    "unit": "m2",
                    "evidence_state": "PARCEL_DERIVED",
                    "source_id": "CONFIRMED_GEOMETRY",
                }
            ]
        }
        run = self._minimal_run(packet)
        with mock.patch(
            "rangematch.advisor_snapshot.generate_snapshot_narrative",
            return_value={
                "content": {
                    "bottom_line": (
                        "This parcel still needs a clearer water picture before cattle use "
                        "can be treated as reliable for the intended season."
                    ),
                    "what_changed": (
                        "No buyer answer has been recorded yet, so the operating view remains "
                        "tied to the initial evidence only."
                    ),
                    "ranch_reading": (
                        "Terrain and area context are available, but water verification is "
                        "still the main open diligence item for cattle use."
                    ),
                    "next_steps": (
                        "Request seller water records and keep the review focused on natural "
                        "resource confirmation rather than access paperwork."
                    ),
                    "copy_and_send": (
                        "Please provide water-source documentation for this confirmed parcel."
                    ),
                },
                "source": "DETERMINISTIC_FALLBACK",
            },
        ):
            view = project_cattle_operating_snapshot(run)
        self.assertFalse(view["appendix"]["additional_property_context"]["enabled"])
        self.assertIsNone(view["page1_property_context_pointer"])
        self.assertFalse(validate_snapshot_view(view))
        payload = render_cattle_operating_snapshot_pdf(view)
        self.assertTrue(payload.startswith(b"%PDF"))
        self.assertIn(b"/Count 2", payload)
        # Compressed streams may still omit the literal title; absence is checked on the view.
        self.assertFalse(view["appendix"]["additional_property_context"]["enabled"])


if __name__ == "__main__":
    unittest.main()
