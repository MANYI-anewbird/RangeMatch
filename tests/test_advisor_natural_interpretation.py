"""Phase 6 Gate: Natural Cattle Profile → advisor interpretation."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from rangematch.advisor_deal_context import create_deal_context, reset_deal_contexts_for_tests
from rangematch.advisor_insight import (
    NATURAL_FOUNDATION_CARD_IDS,
    load_approved_knowledge_cards,
)
from rangematch.advisor_natural_interpretation import (
    SOURCE_FALLBACK,
    SOURCE_LIVE,
    build_natural_interpretation_workbench,
    generate_natural_foundation_interpretation,
    interpretation_withdraws_with_profile,
    validate_natural_foundation_interpretation,
)
from rangematch.llm_provider import LLMCompletion
from rangematch.advisor_question import select_natural_environment_question
from rangematch.environmental_gap_detector import detect_environmental_gaps
from rangematch.environmental_supplement_runner import (
    build_combined_environmental_evidence_packet,
    execute_supplement_plan,
    unit_test_supplement_runners,
)
from rangematch.mireye_environmental_profile import validate_mireye_environmental_profile
from rangematch.mireye_first_collection import derive_confirmed_f06
from rangematch.natural_cattle_profile import (
    project_natural_cattle_profile,
    withdraw_observation_and_reproject,
)

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


def _nambe_profile_and_packet():
    mireye = json.loads(NAMBE_PROFILE.read_text(encoding="utf-8"))
    validate_mireye_environmental_profile(mireye)
    geometry_hash = mireye["parcel_ref"]["geometry_hash"]
    plan = detect_environmental_gaps(mireye, f06_geometry_hash=geometry_hash)
    execution = execute_supplement_plan(
        plan,
        geometry=SIMPLE_POLYGON,
        geometry_id="phase6",
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
    return profile, packet, geometry_hash


class Phase6NaturalInterpretationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_deal_contexts_for_tests()
        self.profile, self.packet, self.geometry_hash = _nambe_profile_and_packet()
        self.deal = create_deal_context(
            run_id="advisor_phase6_test01",
            parcel_resolution_id="res_phase6",
            geometry_hash=self.geometry_hash,
        )

    def test_natural_workbench_excludes_legal_access(self) -> None:
        cards = load_approved_knowledge_cards(workbench="natural_cattle")
        ids = {c["knowledge_id"] for c in cards}
        self.assertTrue(ids <= NATURAL_FOUNDATION_CARD_IDS)
        self.assertNotIn("LEGAL_ACCESS_DILIGENCE_001", ids)
        wb = build_natural_interpretation_workbench(
            natural_cattle_profile=self.profile,
            deal_context=self.deal,
            knowledge_cards=cards,
        )
        self.assertTrue(
            all(
                not str(row["knowledge_id"]).startswith("LEGAL_ACCESS")
                for row in wb["knowledge_cards"]
            )
        )
        self.assertNotIn("Q_ACCESS_DOCUMENTS", wb["allowed_question_ids"])

    def test_fallback_interpretation_validates_and_locks_profile_facts(self) -> None:
        result = generate_natural_foundation_interpretation(
            natural_cattle_profile=self.profile,
            deal_context=self.deal,
            provider_name="FIXTURE",
        )
        self.assertEqual(result["source"], SOURCE_FALLBACK)
        self.assertEqual(result["validation_status"], "PASSED")
        self.assertEqual(
            result["status"],
            self.profile["overall_natural_foundation"]["status"],
        )
        self.assertEqual(
            result["controlling_factor"]["domain"],
            self.profile["overall_natural_foundation"]["controlling_factor"]["domain"],
        )
        self.assertEqual(
            result["natural_cattle_profile_hash"], self.profile["profile_hash"]
        )
        self.assertTrue(result["advisor_view"])
        self.assertTrue(result["land_character"])
        self.assertTrue(result["advisor_judgment"])
        self.assertTrue(result["operating_possibilities"])
        self.assertTrue(result["conditional_scenarios"])
        self.assertTrue(result["integrated_natural_reading"])
        self.assertTrue(result["intended_use_interpretation"])
        self.assertTrue(result["what_would_change_the_view"])
        self.assertTrue(result["refinement_request"])
        self.assertTrue(result["cited_profile_refs"])
        self.assertNotEqual(result["next_question"]["question_id"], "Q_ACCESS_DOCUMENTS")
        blob = (
            result["advisor_view"]
            + result["integrated_natural_reading"]
            + result["intended_use_interpretation"]
        ).lower()
        self.assertNotIn("stocking rate", blob)
        self.assertNotIn("buy this", blob)
        self.assertNotIn("legal access", blob)

    def test_status_mutation_fails_validator(self) -> None:
        result = generate_natural_foundation_interpretation(
            natural_cattle_profile=self.profile,
            deal_context=self.deal,
            force_fallback=True,
        )
        poisoned = copy.deepcopy(result)
        poisoned["status"] = "ENVIRONMENTALLY_CONSTRAINED"
        violations = validate_natural_foundation_interpretation(
            poisoned,
            natural_cattle_profile=self.profile,
            deal_context=self.deal,
        )
        self.assertTrue(any(v["code"] == "STATUS_MUTATION" for v in violations))

    def test_dangling_profile_ref_fails_validator(self) -> None:
        result = generate_natural_foundation_interpretation(
            natural_cattle_profile=self.profile,
            deal_context=self.deal,
            force_fallback=True,
        )
        poisoned = copy.deepcopy(result)
        poisoned["cited_profile_refs"] = list(poisoned["cited_profile_refs"]) + [
            "REF_FROM_OTHER_RUN"
        ]
        violations = validate_natural_foundation_interpretation(
            poisoned,
            natural_cattle_profile=self.profile,
            deal_context=self.deal,
        )
        self.assertTrue(any(v["code"] == "DANGLING_PROFILE_REF" for v in violations))

    def test_question_policy_never_access(self) -> None:
        q = select_natural_environment_question(
            deal_context=self.deal,
            natural_cattle_profile=self.profile,
        )
        self.assertEqual(q["question_id"], "Q_OPERATION_TYPE")
        self.assertNotEqual(q["question_id"], "Q_ACCESS_DOCUMENTS")

    def test_withdrawal_changes_interpretation(self) -> None:
        before = generate_natural_foundation_interpretation(
            natural_cattle_profile=self.profile,
            deal_context=self.deal,
            force_fallback=True,
        )
        forage = next(
            row
            for row in self.profile["domains"]
            if row["domain"] == "FEED_VEGETATION"
        )
        refs = list(forage["supporting_refs"])
        self.assertTrue(refs)
        packet = copy.deepcopy(self.packet)
        for ref in refs:
            for key in (
                "mireye_observations",
                "core_observations",
                "supplement_observations",
            ):
                packet[key] = [
                    obs
                    for obs in (packet.get(key) or [])
                    if obs.get("observation_id") != ref
                ]
            packet["conflicts"] = [
                row
                for row in (packet.get("conflicts") or [])
                if ref
                not in {
                    str(row.get("mireye_ref") or ""),
                    str(row.get("supplement_ref") or ""),
                }
            ]
        after_profile = project_natural_cattle_profile(packet)
        after = interpretation_withdraws_with_profile(
            before=before,
            after_profile=after_profile,
            deal_context=self.deal,
        )
        self.assertNotEqual(
            after["natural_cattle_profile_hash"], before["natural_cattle_profile_hash"]
        )
        self.assertEqual(
            after["status"], after_profile["overall_natural_foundation"]["status"]
        )
        self.assertTrue(
            after["integrated_natural_reading"] != before["integrated_natural_reading"]
            or after["controlling_factor"] != before["controlling_factor"]
            or after["advisor_view"] != before["advisor_view"]
        )

    def test_force_fallback_on_bad_llm_does_not_fail_run(self) -> None:
        result = generate_natural_foundation_interpretation(
            natural_cattle_profile=self.profile,
            deal_context=self.deal,
            force_fallback=True,
        )
        self.assertEqual(result["source"], SOURCE_FALLBACK)
        self.assertEqual(result["validation_status"], "PASSED")

    def test_live_provider_single_string_array_is_one_item_not_characters(self) -> None:
        baseline = generate_natural_foundation_interpretation(
            natural_cattle_profile=self.profile,
            deal_context=self.deal,
            force_fallback=True,
        )
        change = "Request parcel-wide evidence that resolves the controlling uncertainty."
        long_advisor_view = (
            "The natural foundation is conditional because the controlling evidence is not yet reconciled. "
            "Terrain remains the controlling factor for this preliminary reading. "
            + ("Additional parcel evidence would refine the view. " * 20)
        )
        draft = {
            "land_character": baseline["land_character"],
            "advisor_judgment": baseline["advisor_judgment"],
            "operating_possibilities": baseline["operating_possibilities"],
            "conditional_scenarios": baseline["conditional_scenarios"],
            "advisor_view": long_advisor_view,
            "integrated_natural_reading": baseline["integrated_natural_reading"],
            "intended_use_interpretation": baseline["intended_use_interpretation"],
            "what_would_change_the_view": change,
            "refinement_request": baseline["refinement_request"],
            "optional_copy_ready_request": baseline["optional_copy_ready_request"],
            "cited_profile_refs": baseline["cited_profile_refs"],
            "knowledge_refs": baseline["knowledge_refs"],
            "next_question_id": baseline["next_question"]["question_id"],
        }
        provider = MagicMock()
        provider.complete_json.return_value = LLMCompletion(
            content={"natural_foundation_interpretation": draft},
            provider="DEEPSEEK",
            model_id="deepseek-chat",
            prompt_version="test",
            generated_at="2026-08-15T00:00:00+00:00",
            provider_status="OK",
        )
        with patch(
            "rangematch.advisor_natural_interpretation.get_provider",
            return_value=provider,
        ):
            result = generate_natural_foundation_interpretation(
                natural_cattle_profile=self.profile,
                deal_context=self.deal,
                provider_name="DEEPSEEK",
            )
        self.assertEqual(result["source"], SOURCE_LIVE, result.get("provenance"))
        self.assertEqual(result["validation_status"], "PASSED")
        self.assertEqual(result["what_would_change_the_view"], [change])
        self.assertLessEqual(len(result["advisor_view"]), 600)
        self.assertTrue(result["advisor_view"].endswith("."))

    def test_live_provider_overlong_prose_is_compacted_not_fallback(self) -> None:
        baseline = generate_natural_foundation_interpretation(
            natural_cattle_profile=self.profile,
            deal_context=self.deal,
            force_fallback=True,
        )
        draft = {
            "land_character": (
                "This parcel reads as open rangeland with a terrain pattern that can shape cattle movement. "
                + "It is important to note that more data may be helpful. "
                + ("The observed land pattern remains relevant to seasonal cattle use. " * 30)
            ),
            "advisor_judgment": baseline["advisor_judgment"],
            "operating_possibilities": baseline["operating_possibilities"],
            "conditional_scenarios": baseline["conditional_scenarios"],
            "advisor_view": baseline["advisor_view"],
            "integrated_natural_reading": baseline["integrated_natural_reading"],
            "intended_use_interpretation": baseline["intended_use_interpretation"],
            "what_would_change_the_view": baseline["what_would_change_the_view"],
            "refinement_request": baseline["refinement_request"],
            "optional_copy_ready_request": baseline["optional_copy_ready_request"],
            "cited_profile_refs": baseline["cited_profile_refs"],
            "knowledge_refs": baseline["knowledge_refs"],
            "next_question_id": baseline["next_question"]["question_id"],
        }
        provider = MagicMock()
        provider.complete_json.return_value = LLMCompletion(
            content={"natural_foundation_interpretation": draft},
            provider="DEEPSEEK",
            model_id="deepseek-chat",
            prompt_version="test",
            generated_at="2026-08-15T00:00:00+00:00",
            provider_status="OK",
        )
        with patch(
            "rangematch.advisor_natural_interpretation.get_provider",
            return_value=provider,
        ):
            result = generate_natural_foundation_interpretation(
                natural_cattle_profile=self.profile,
                deal_context=self.deal,
                provider_name="DEEPSEEK",
            )
        self.assertEqual(result["source"], SOURCE_LIVE)
        self.assertEqual(result["validation_status"], "PASSED")
        self.assertLessEqual(len(result["land_character"]), 1000)
        self.assertNotIn("important to note", result["land_character"].lower())
        self.assertEqual(
            result["land_character"].count(
                "The observed land pattern remains relevant to seasonal cattle use."
            ),
            1,
        )

    def test_live_provider_prohibited_disclaimer_is_removed_not_full_fallback(self) -> None:
        baseline = generate_natural_foundation_interpretation(
            natural_cattle_profile=self.profile,
            deal_context=self.deal,
            force_fallback=True,
        )
        draft = {
            key: baseline[key]
            for key in (
                "land_character",
                "advisor_judgment",
                "operating_possibilities",
                "conditional_scenarios",
                "advisor_view",
                "integrated_natural_reading",
                "intended_use_interpretation",
                "what_would_change_the_view",
                "refinement_request",
                "optional_copy_ready_request",
                "cited_profile_refs",
                "knowledge_refs",
            )
        }
        draft["advisor_judgment"] = (
            "The terrain and vegetation pattern make seasonal cattle use worth examining. "
            "This is not a stocking rate opinion."
        )
        draft["operating_possibilities"] = [
            "This is not a stocking rate opinion.",
            "No legal access conclusion is provided.",
        ]
        draft["next_question_id"] = baseline["next_question"]["question_id"]
        provider = MagicMock()
        provider.complete_json.return_value = LLMCompletion(
            content={"natural_foundation_interpretation": draft},
            provider="DEEPSEEK",
            model_id="deepseek-chat",
            prompt_version="test",
            generated_at="2026-08-15T00:00:00+00:00",
            provider_status="OK",
        )
        with patch(
            "rangematch.advisor_natural_interpretation.get_provider",
            return_value=provider,
        ):
            result = generate_natural_foundation_interpretation(
                natural_cattle_profile=self.profile,
                deal_context=self.deal,
                provider_name="DEEPSEEK",
            )
        self.assertEqual(result["source"], SOURCE_LIVE, result.get("provenance"))
        self.assertEqual(result["validation_status"], "PASSED")
        self.assertNotIn("stocking rate", result["advisor_judgment"].lower())
        self.assertTrue(result["operating_possibilities"])
        self.assertNotIn(
            "stocking rate",
            " ".join(result["operating_possibilities"]).lower(),
        )

    def test_empty_change_list_uses_field_fallback_not_full_report_fallback(self) -> None:
        baseline = generate_natural_foundation_interpretation(
            natural_cattle_profile=self.profile,
            deal_context=self.deal,
            force_fallback=True,
        )
        draft = {
            key: baseline[key]
            for key in (
                "land_character",
                "advisor_judgment",
                "operating_possibilities",
                "conditional_scenarios",
                "advisor_view",
                "integrated_natural_reading",
                "intended_use_interpretation",
                "refinement_request",
                "optional_copy_ready_request",
                "cited_profile_refs",
                "knowledge_refs",
            )
        }
        draft["what_would_change_the_view"] = []
        draft["next_question_id"] = baseline["next_question"]["question_id"]
        provider = MagicMock()
        provider.complete_json.return_value = LLMCompletion(
            content={"natural_foundation_interpretation": draft},
            provider="DEEPSEEK",
            model_id="deepseek-chat",
            prompt_version="test",
            generated_at="2026-08-15T00:00:00+00:00",
            provider_status="OK",
        )
        with patch(
            "rangematch.advisor_natural_interpretation.get_provider",
            return_value=provider,
        ):
            result = generate_natural_foundation_interpretation(
                natural_cattle_profile=self.profile,
                deal_context=self.deal,
                provider_name="DEEPSEEK",
            )
        self.assertEqual(result["source"], SOURCE_LIVE, result.get("provenance"))
        self.assertEqual(result["validation_status"], "PASSED")
        self.assertEqual(
            result["what_would_change_the_view"], result["conditional_scenarios"]
        )

    def test_spatial_and_professional_overreach_is_removed_without_full_fallback(self) -> None:
        baseline = generate_natural_foundation_interpretation(
            natural_cattle_profile=self.profile,
            deal_context=self.deal,
            force_fallback=True,
        )
        draft = {
            key: baseline[key]
            for key in (
                "land_character",
                "advisor_judgment",
                "operating_possibilities",
                "conditional_scenarios",
                "advisor_view",
                "integrated_natural_reading",
                "intended_use_interpretation",
                "what_would_change_the_view",
                "refinement_request",
                "optional_copy_ready_request",
                "cited_profile_refs",
                "knowledge_refs",
            )
        }
        draft["land_character"] = (
            "The terrain and vegetation describe a dry foothill rangeland. "
            "There is no mapped surface water on the parcel itself."
        )
        draft["advisor_judgment"] = (
            "The moderate terrain makes a bounded seasonal cattle evaluation plausible. "
            "The well-drained soil is favorable for hoof health. "
            "Water is the main limiting factor."
        )
        draft["operating_possibilities"] = [
            "Year-round use would require substantial water development and supplemental feed."
        ]
        draft["next_question_id"] = baseline["next_question"]["question_id"]
        provider = MagicMock()
        provider.complete_json.return_value = LLMCompletion(
            content={"natural_foundation_interpretation": draft},
            provider="DEEPSEEK",
            model_id="deepseek-chat",
            prompt_version="test",
            generated_at="2026-08-15T00:00:00+00:00",
            provider_status="OK",
        )
        with patch(
            "rangematch.advisor_natural_interpretation.get_provider",
            return_value=provider,
        ):
            result = generate_natural_foundation_interpretation(
                natural_cattle_profile=self.profile,
                deal_context=self.deal,
                provider_name="DEEPSEEK",
            )
        self.assertEqual(result["source"], SOURCE_LIVE, result.get("provenance"))
        self.assertEqual(result["validation_status"], "PASSED")
        prose = json.dumps(result).lower()
        self.assertNotIn("no mapped surface water on the parcel", prose)
        self.assertNotIn("hoof health", prose)
        self.assertNotIn("substantial water development", prose)
        self.assertNotIn("supplemental feed", prose)
        self.assertNotIn("water is the main limiting factor", prose)
        self.assertIn("combined terrain and vegetation", prose)

    def test_live_provider_structured_lists_render_as_natural_language(self) -> None:
        baseline = generate_natural_foundation_interpretation(
            natural_cattle_profile=self.profile,
            deal_context=self.deal,
            force_fallback=True,
        )
        draft = {
            "land_character": baseline["land_character"],
            "advisor_judgment": baseline["advisor_judgment"],
            "operating_possibilities": [
                {
                    "possibility": "Seasonal grazing may be plausible",
                    "why_plausible": "Moderate terrain and the observed vegetation pattern support a bounded grazing window.",
                }
            ],
            "conditional_scenarios": [
                {
                    "condition": "If dependable livestock water is confirmed for the intended months, the view becomes stronger because cattle could use the observed forage window.",
                    "impact": "strengthen",
                },
                {
                    "condition": "If water fails during that window, the view becomes weaker because the intended use would depend on outside supply.",
                    "impact": "weaken",
                },
            ],
            "advisor_view": baseline["advisor_view"],
            "integrated_natural_reading": baseline["integrated_natural_reading"],
            "intended_use_interpretation": baseline["intended_use_interpretation"],
            "what_would_change_the_view": baseline["what_would_change_the_view"],
            "refinement_request": baseline["refinement_request"],
            "optional_copy_ready_request": baseline["optional_copy_ready_request"],
            "cited_profile_refs": baseline["cited_profile_refs"],
            "knowledge_refs": baseline["knowledge_refs"],
            "next_question_id": baseline["next_question"]["question_id"],
        }
        provider = MagicMock()
        provider.complete_json.return_value = LLMCompletion(
            content={"natural_foundation_interpretation": draft},
            provider="DEEPSEEK",
            model_id="deepseek-chat",
            prompt_version="test",
            generated_at="2026-08-15T00:00:00+00:00",
            provider_status="OK",
        )
        with patch(
            "rangematch.advisor_natural_interpretation.get_provider",
            return_value=provider,
        ):
            result = generate_natural_foundation_interpretation(
                natural_cattle_profile=self.profile,
                deal_context=self.deal,
                provider_name="DEEPSEEK",
            )
        self.assertEqual(result["source"], SOURCE_LIVE)
        self.assertEqual(result["validation_status"], "PASSED")
        rendered = " ".join(
            result["operating_possibilities"] + result["conditional_scenarios"]
        )
        self.assertNotIn("{", rendered)
        self.assertNotIn("}", rendered)
        self.assertIn("Seasonal grazing may be plausible.", rendered)
        self.assertIn("If dependable livestock water", rendered)

    def test_deal_context_operation_type_narrows_intended_use(self) -> None:
        from rangematch.advisor_deal_context import update_deal_context

        initial = generate_natural_foundation_interpretation(
            natural_cattle_profile=self.profile,
            deal_context=self.deal,
            force_fallback=True,
        )
        updated = update_deal_context(
            run_id=self.deal["run_id"],
            expected_geometry_hash=self.geometry_hash,
            expected_context_version=self.deal["context_version"],
            operation_type="SEASONAL_GRAZING",
            append_answer={
                "field": "operation_type",
                "value": "SEASONAL_GRAZING",
            },
        )
        revised = generate_natural_foundation_interpretation(
            natural_cattle_profile=self.profile,
            deal_context=updated,
            previous_interpretation=initial,
            force_fallback=True,
        )
        self.assertIn("seasonal grazing", revised["intended_use_interpretation"].lower())
        self.assertNotEqual(
            revised["intended_use_interpretation"],
            initial["intended_use_interpretation"],
        )
        self.assertEqual(revised["status"], initial["status"])
        self.assertEqual(
            revised["controlling_factor"]["domain"],
            initial["controlling_factor"]["domain"],
        )


if __name__ == "__main__":
    unittest.main()
