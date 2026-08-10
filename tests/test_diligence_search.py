"""Tests for the bounded Diligence Search Agent."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from rangematch.api import app, reset_store_for_tests
from rangematch.diligence_search import (
    _extract_response,
    _normalize_sources,
    run_diligence_search,
)


class DiligenceSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_store_for_tests()
        self.client = TestClient(app)

    def _investigation(self) -> str:
        created = self.client.post(
            "/v1/investigations",
            json={
                "existing_land_profile_reference": "test-data/land-profiles/land_profile_cper_001.json",
                "mode": "DISCOVERY",
                "intended_operation": None,
                "planned_actions": [],
                "execution_source": "DEMO_FIXTURE",
                "mireye_mode": "BLOCKED_EXTERNAL",
            },
        ).json()
        self.client.get("/v1/investigations/" + created["investigation_id"])
        return created["investigation_id"]

    def test_fixture_search_is_context_only_with_sources(self):
        result = run_diligence_search(
            jurisdiction={"county": "Weld", "state": "CO"},
            provider="FIXTURE",
        )
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["effect_on_engine"], "NONE")
        self.assertGreaterEqual(len(result["sources"]), 2)
        self.assertTrue(all(s["use_limit"] == "DILIGENCE_CONTEXT_ONLY" for s in result["sources"]))

    def test_source_gate_drops_unapproved_or_insecure_domains(self):
        sources = _normalize_sources(
            [
                {"title": "Good", "url": "https://www.nrcs.usda.gov/"},
                {"title": "Bad", "url": "https://example.com/opinion"},
                {"title": "Insecure", "url": "http://fema.gov/test"},
            ],
            searched_at="2026-08-08T00:00:00+00:00",
            jurisdiction="Weld, CO",
        )
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["domain"], "www.nrcs.usda.gov")

    def test_missing_live_key_fails_closed(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = run_diligence_search(
                jurisdiction={"state": "CO"}, provider="OPENAI"
            )
        self.assertEqual(result["status"], "NOT_CONFIGURED")
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["effect_on_engine"], "NONE")

    def test_extracts_response_sources_and_citations(self):
        summary, sources = _extract_response({
            "output": [
                {"type": "web_search_call", "action": {"sources": [{"url": "https://fema.gov/a", "title": "A"}]}},
                {"type": "message", "content": [{"type": "output_text", "text": "Review current rules.", "annotations": [{"type": "url_citation", "url": "https://www.nrcs.usda.gov/b", "title": "B"}]}]},
            ]
        })
        self.assertEqual(summary, "Review current rules.")
        self.assertEqual(len(sources), 2)

    def test_api_stores_fixture_search_beside_investigation(self):
        inv = self._investigation()
        posted = self.client.post(
            f"/v1/investigations/{inv}/diligence-search",
            json={"provider": "FIXTURE", "topics": ["CURRENT_DROUGHT"]},
        )
        self.assertEqual(posted.status_code, 200, posted.text)
        result = posted.json()["diligence_search"]
        self.assertEqual(result["topics"], ["CURRENT_DROUGHT"])
        self.assertEqual(result["effect_on_engine"], "NONE")
        fetched = self.client.get(f"/v1/investigations/{inv}/diligence-search")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["diligence_search"]["search_id"], result["search_id"])


if __name__ == "__main__":
    unittest.main()
