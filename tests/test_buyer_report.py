"""Tests for constrained Buyer Report generator."""

from __future__ import annotations

import json
import os
import ssl
import unittest
from pathlib import Path
from unittest import mock

from rangematch.buyer_report import (
    build_fixture_buyer_report,
    generate_buyer_report,
    merge_live_prose_onto_grounded_report,
)
from rangematch.llm_provider import OpenAILLMProvider


ROOT = Path(__file__).resolve().parents[1]
UO_PATH = ROOT / "test-data" / "land-profiles" / "unified_output_cper_001.json"


class BuyerReportTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["RANGEMATCH_LLM_PROVIDER"] = "FIXTURE"
        self.uo = json.loads(UO_PATH.read_text(encoding="utf-8"))

    def test_fixture_report_validates_and_is_displayable(self):
        report = generate_buyer_report(
            self.uo,
            mode="GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
            provider_name="FIXTURE",
        )
        self.assertEqual(report["validation_status"], "PASSED", report.get("validation_violations"))
        self.assertTrue(report["report_provenance"]["displayable"])
        self.assertIn(
            "evidence is incomplete",
            report["operation_comparison"]["summary"].lower()
            + " ".join(report["operation_comparison"]["findings"]).lower(),
        )
        self.assertEqual(report["match_result_hash"], self.uo["match_result_hash"])
        # Human language, not only raw IDs in executive findings
        blob = " ".join(report["land_and_resources"]["findings"]).lower()
        self.assertIn("herbaceous", blob)
        self.assertNotIn("carrying capacity", blob)

    def test_discovery_mode_peer_language(self):
        report = generate_buyer_report(
            self.uo,
            mode="DISCOVERY",
            intended_operation=None,
            provider_name="FIXTURE",
        )
        self.assertEqual(report["validation_status"], "PASSED", report.get("validation_violations"))
        text = " ".join(report["executive_summary"]["findings"]).lower()
        self.assertIn("peers", text)
        self.assertIn("no best-use", text)

    def test_openai_without_key_fails_closed(self):
        for key in ("RANGEMATCH_LLM_API_KEY", "OPENAI_API_KEY"):
            os.environ.pop(key, None)
        report = generate_buyer_report(
            self.uo,
            provider_name="OPENAI",
        )
        self.assertEqual(report["validation_status"], "FAILED")
        self.assertFalse(report["report_provenance"]["displayable"])
        self.assertEqual(report["report_provenance"]["provider_status"], "NOT_CONFIGURED")
        # Must not silently return fixture narrative
        self.assertEqual(report["claim_ledger"], [])

    def test_provider_not_configured_status(self):
        for key in ("RANGEMATCH_LLM_API_KEY", "OPENAI_API_KEY"):
            os.environ.pop(key, None)
        c = OpenAILLMProvider().complete_json(system="s", user="u", prompt_version="p")
        self.assertEqual(c.provider_status, "NOT_CONFIGURED")

    def test_openai_transport_uses_verified_tls_context(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}'

        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-key"}, clear=False):
            with mock.patch(
                "rangematch.llm_provider.urllib.request.urlopen",
                return_value=FakeResponse(),
            ) as opened:
                completion = OpenAILLMProvider().complete_json(
                    system="Return JSON",
                    user="{}",
                    prompt_version="test",
                )

        self.assertEqual(completion.provider_status, "OK")
        self.assertEqual(completion.content, {"ok": True})
        self.assertIsInstance(opened.call_args.kwargs.get("context"), ssl.SSLContext)
        self.assertEqual(opened.call_args.kwargs.get("timeout"), 60)

    def test_live_prose_overlay_cannot_replace_authority_or_evidence(self):
        grounded = build_fixture_buyer_report(
            self.uo,
            mode="GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
        )
        original_claims = json.loads(json.dumps(grounded["claim_ledger"]))
        original_refs = json.loads(json.dumps(grounded["evidence_references"]))
        merged = merge_live_prose_onto_grounded_report(
            grounded,
            {
                "sections": {
                    "executive_summary": {
                        "summary": "Buyer-readable summary.",
                        "findings": ["HOLD means evidence remains incomplete."],
                        "claim_ledger": [{"text": "REJECT"}],
                    }
                },
                "claim_ledger": [{"text": "REJECT"}],
                "evidence_references": [{"ref_id": "invented"}],
            },
        )
        self.assertEqual(merged["executive_summary"]["summary"], "Buyer-readable summary.")
        self.assertEqual(merged["claim_ledger"], original_claims)
        self.assertEqual(merged["evidence_references"], original_refs)


if __name__ == "__main__":
    unittest.main()
