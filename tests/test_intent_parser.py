"""Tests for constrained LLM Intent Parser."""

from __future__ import annotations

import os
import unittest

from rangematch.intent_parser import normalize_live_intent_shape, parse_intent
from rangematch.llm_provider import OpenAILLMProvider


class IntentParserTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["RANGEMATCH_LLM_PROVIDER"] = "FIXTURE"

    def test_goal_directed_cow_calf_with_well(self):
        intent = parse_intent(
            user_request=(
                "I want to know whether this parcel can support a cow-calf operation, "
                "and I may drill a well."
            ),
            existing_land_profile_reference="test-data/land-profiles/land_profile_cper_001.json",
            provider_name="FIXTURE",
        )
        self.assertEqual(intent["intent_status"], "PARSED")
        self.assertEqual(intent["mode"], "GOAL_DIRECTED")
        self.assertEqual(intent["intended_operation"], "COW_CALF_OPERATION")
        self.assertIn("DRILL_WELL", intent["planned_actions"])
        self.assertTrue(intent["prohibited_inferences_applied"])
        self.assertEqual(
            intent["parcel_input_reference"]["kind"],
            "existing_land_profile_reference",
        )

    def test_discovery(self):
        intent = parse_intent(
            user_request="What can this parcel be used for?",
            provider_name="FIXTURE",
        )
        self.assertEqual(intent["intent_status"], "PARSED")
        self.assertEqual(intent["mode"], "DISCOVERY")
        self.assertIsNone(intent["intended_operation"])

    def test_batch_rejected(self):
        intent = parse_intent(
            user_request="Find the best 50 ranches in Colorado.",
            provider_name="FIXTURE",
        )
        self.assertEqual(intent["intent_status"], "REJECTED")
        self.assertEqual(intent["rejection_code"], "REJECTED_OUT_OF_SCOPE_BATCH")
        self.assertEqual(intent["planned_actions"], [])

    def test_unsupported_operation_not_mapped(self):
        intent = parse_intent(
            user_request="Can this parcel support a dairy operation?",
            provider_name="FIXTURE",
        )
        self.assertEqual(intent["intent_status"], "NEEDS_CLARIFICATION")
        self.assertIsNone(intent["intended_operation"])
        self.assertTrue(intent["clarification_questions"])

    def test_ui_overrides_are_authoritative(self):
        intent = parse_intent(
            user_request="What can this parcel be used for?",
            ui_mode="GOAL_DIRECTED",
            ui_intended_operation="SHEEP_GRAZING",
            ui_planned_actions=["SITE_VISIT"],
            provider_name="FIXTURE",
        )
        self.assertEqual(intent["mode"], "GOAL_DIRECTED")
        self.assertEqual(intent["intended_operation"], "SHEEP_GRAZING")
        self.assertEqual(intent["planned_actions"], ["SITE_VISIT"])
        self.assertTrue(intent["parser_provenance"]["ui_overrides_applied"])

    def test_live_provider_without_key_does_not_fixture_substitute(self):
        # Ensure OPENAI path does not fall back to fixture content.
        for key in ("RANGEMATCH_LLM_API_KEY", "OPENAI_API_KEY"):
            os.environ.pop(key, None)
        provider = OpenAILLMProvider()
        completion = provider.complete_json(
            system="x",
            user="{}",
            prompt_version="test",
        )
        self.assertEqual(completion.provider_status, "NOT_CONFIGURED")
        self.assertIsNone(completion.content)

        intent = parse_intent(
            user_request="Cow-calf check please",
            provider_name="OPENAI",
        )
        self.assertEqual(intent["intent_status"], "REJECTED")
        self.assertEqual(
            intent["parser_provenance"]["provider_status"], "NOT_CONFIGURED"
        )

    def test_incomplete_live_shape_repairs_from_deterministic_baseline(self):
        repaired, changed = normalize_live_intent_shape(
            {"mode": "GOAL_DIRECTED", "intended_operation": "COW_CALF_OPERATION"},
            fixture_key="intent_goal_directed_cow_calf",
        )
        self.assertTrue(changed)
        self.assertEqual(repaired["intent_status"], "PARSED")
        self.assertEqual(repaired["mode"], "GOAL_DIRECTED")
        self.assertEqual(repaired["intended_operation"], "COW_CALF_OPERATION")
        self.assertTrue(repaired["prohibited_inferences_applied"])


if __name__ == "__main__":
    unittest.main()
