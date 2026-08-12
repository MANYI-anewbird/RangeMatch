"""CPER fallback boundary fixtures: listing, water, F03, context, non-drawable objects."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from rangematch.advisor_brief import generate_deterministic_brief
from rangematch.advisor_contract import land_fact_index, validate_packet, validate_three_page
from rangematch.advisor_packet import (
    F03_FAILED,
    F03_INVENTORY_REF,
    F03_REMOTE_PILOT_REF,
    project_cper_buyer_evidence_packet,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "test-data" / "advisor" / "boundary"


def _uo() -> dict:
    return json.loads((ROOT / "test-data/land-profiles/unified_output_cper_001.json").read_text())


def _claims() -> list[dict]:
    return json.loads((ROOT / "test-data/advisor/cper_listing_claims_fixture.json").read_text())[
        "listing_claims"
    ]


def _inventory() -> dict:
    return json.loads((ROOT / F03_INVENTORY_REF).read_text())


def _pilot() -> dict:
    return json.loads((ROOT / F03_REMOTE_PILOT_REF).read_text())


def _set_water_count(uo: dict, value: int | None) -> None:
    for fact in uo["factors"]["F03_LIVESTOCK_WATER"]["land_facts"]:
        if fact["variable_id"] == "VAR_F03_MAPPED_WATER_CANDIDATE_COUNT":
            fact["value"] = value
            return
    raise KeyError("VAR_F03_MAPPED_WATER_CANDIDATE_COUNT")


def _write(name: str, payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _visible(brief: dict) -> str:
    page = brief.get("page_one_advisor") or {}
    messages = ((brief.get("page_two_actions") or {}).get("messages")) or []
    return "\n".join(
        [
            str(page.get("how_the_tract_reads") or ""),
            *list(page.get("listing_outruns_evidence") or []),
            *list(page.get("do_today") or []),
            str(page.get("visit_guidance") or ""),
            *(str(row.get("body") or "") for row in messages),
        ]
    )


class AdvisorBoundaryFixtureTests(unittest.TestCase):
    def test_no_listing_has_no_claim_theater(self) -> None:
        uo = _uo()
        packet = project_cper_buyer_evidence_packet(
            uo,
            listing_claims=[],
            candidate_inventory=_inventory(),
            remote_pilot=_pilot(),
        )
        facts = land_fact_index(uo)
        brief = generate_deterministic_brief(packet, land_facts=facts, unified_output=uo)
        _write("no_listing_packet.json", packet)
        self.assertEqual(packet["listing_claims"], [])
        self.assertEqual(packet["claim_evidence_gaps"], [])
        self.assertEqual(brief["page_one_advisor"]["listing_outruns_evidence"], [])
        self.assertFalse(any("excellent year-round water" in line.lower() for line in brief["page_one_advisor"]["do_today"]))
        self.assertIn("ACTION_ACCESS_DOCUMENTS", {row["action_id"] for row in packet["actions"]})
        self.assertEqual(validate_packet(packet, land_facts=facts), [])
        self.assertEqual(validate_three_page(brief, packet, land_facts=facts), [])

    def test_no_mapped_water_is_not_absence(self) -> None:
        uo = _uo()
        _set_water_count(uo, 0)
        packet = project_cper_buyer_evidence_packet(
            uo,
            listing_claims=_claims(),
            candidate_inventory={"candidate_inventory": []},
        )
        facts = land_fact_index(uo)
        brief = generate_deterministic_brief(packet, land_facts=facts, unified_output=uo)
        _write("no_mapped_water_packet.json", packet)
        visible = _visible(brief).lower()
        self.assertEqual(packet["candidate_objects"], [])
        self.assertEqual(packet["technical_references"]["f03_status"], "AVAILABLE")
        self.assertEqual(packet["actions"][1]["action_id"], "ACTION_ASK_SELLER_WATER")
        self.assertNotIn("review the mapped water feature areas", visible)
        self.assertNotIn("no water", visible)
        self.assertIn("developed", visible)
        water_gap = next(row for row in packet["claim_evidence_gaps"] if row["claim_id"] == "CLAIM_WATER_001")
        self.assertIn("No mapped hydrography leads", water_gap["supported_portion"])
        self.assertEqual(validate_three_page(brief, packet, land_facts=facts), [])

    def test_f03_failure_is_not_zero_candidates(self) -> None:
        uo = _uo()
        _set_water_count(uo, None)
        packet = project_cper_buyer_evidence_packet(
            uo,
            listing_claims=_claims(),
            f03_status=F03_FAILED,
        )
        facts = land_fact_index(uo)
        brief = generate_deterministic_brief(packet, land_facts=facts, unified_output=uo)
        _write("f03_failed_packet.json", packet)
        water = next(row for row in packet["observations"] if row["observation_id"] == "OBS_WATER_COUNT")
        visible = _visible(brief).lower()
        self.assertEqual(packet["technical_references"]["f03_status"], "FAILED")
        self.assertEqual(packet["candidate_objects"], [])
        self.assertEqual(water["evidence_state"], "SOURCE_UNAVAILABLE")
        self.assertIsNone(water["value"])
        self.assertEqual(packet["actions"][1]["action_id"], "ACTION_WATER_SOURCE_UNAVAILABLE")
        self.assertNotIn("no leads", visible)
        self.assertNotIn("no water", visible)
        self.assertIn("unavailable", visible)
        self.assertEqual(validate_three_page(brief, packet, land_facts=facts), [])

    def test_decision_context_changes_action_order(self) -> None:
        uo = _uo()
        inventory, pilot, claims = _inventory(), _pilot(), _claims()
        pre = project_cper_buyer_evidence_packet(
            uo,
            listing_claims=claims,
            candidate_inventory=inventory,
            remote_pilot=pilot,
            decision_context={
                "current_stage": "PRE_VISIT",
                "decision_deadline": "THIS_WEEK",
                "candidate_actions": ["REQUEST_DOCUMENTS", "SCHEDULE_FIELD_VISIT"],
                "user_question": "Should I fly this weekend?",
                "goal": "CHOOSE_NEXT_DILIGENCE_SPEND_NOT_PURCHASE",
            },
        )
        title = project_cper_buyer_evidence_packet(
            uo,
            listing_claims=claims,
            candidate_inventory=inventory,
            remote_pilot=pilot,
            decision_context={
                "current_stage": "TITLE_REVIEW_ACTIVE",
                "decision_deadline": "THIS_WEEK",
                "candidate_actions": ["REQUEST_DOCUMENTS"],
                "user_question": "Title is already looking at access.",
                "goal": "CHOOSE_NEXT_DILIGENCE_SPEND_NOT_PURCHASE",
            },
        )
        field = project_cper_buyer_evidence_packet(
            uo,
            listing_claims=claims,
            candidate_inventory=inventory,
            remote_pilot=pilot,
            decision_context={
                "current_stage": "FIELD_VISIT_ALREADY_BOOKED",
                "decision_deadline": "THIS_WEEK",
                "candidate_actions": ["SCHEDULE_FIELD_VISIT"],
                "user_question": "The visit is booked.",
                "goal": "CHOOSE_NEXT_DILIGENCE_SPEND_NOT_PURCHASE",
            },
        )
        unconfirmed = project_cper_buyer_evidence_packet(
            uo,
            listing_claims=claims,
            candidate_inventory=inventory,
            remote_pilot=pilot,
            confirmation_status="UNCONFIRMED",
            decision_context={
                "current_stage": "PARCEL_CONFIRMATION",
                "decision_deadline": "TODAY",
                "candidate_actions": ["CONFIRM_PARCEL"],
                "user_question": "Is this the right outline?",
                "goal": "CHOOSE_NEXT_DILIGENCE_SPEND_NOT_PURCHASE",
            },
        )
        _write("decision_context_pre_visit_packet.json", pre)
        _write("decision_context_title_review_packet.json", title)
        _write("decision_context_field_booked_packet.json", field)
        _write("decision_context_unconfirmed_packet.json", unconfirmed)
        self.assertEqual(
            [row["action_id"] for row in pre["actions"]],
            ["ACTION_ACCESS_DOCUMENTS", "ACTION_WATER_FIELD_CATEGORY"],
        )
        self.assertEqual([row["action_id"] for row in title["actions"]], ["ACTION_WATER_FIELD_CATEGORY"])
        self.assertNotIn("ACTION_ACCESS_DOCUMENTS", {row["action_id"] for row in title["actions"]})
        self.assertEqual(
            [row["action_id"] for row in field["actions"]],
            ["ACTION_WATER_FIELD_CATEGORY", "ACTION_ACCESS_DOCUMENTS"],
        )
        self.assertTrue(all(row["specificity"] == "CATEGORY_LEVEL" for row in field["actions"]))
        self.assertEqual([row["action_id"] for row in unconfirmed["actions"]], ["ACTION_CONFIRM_PARCEL"])
        codes = {row["code"] for row in validate_packet(unconfirmed, land_facts=land_fact_index(uo))}
        self.assertIn("PARCEL_UNCONFIRMED", codes)
        self.assertEqual(pre["observations"], title["observations"])
        self.assertEqual(pre["candidate_objects"], field["candidate_objects"])

    def test_identities_without_geometry_stay_off_the_map(self) -> None:
        uo = _uo()
        packet = project_cper_buyer_evidence_packet(
            uo,
            listing_claims=_claims(),
            candidate_inventory=_inventory(),
        )
        facts = land_fact_index(uo)
        brief = generate_deterministic_brief(packet, land_facts=facts, unified_output=uo)
        _write("not_drawable_packet.json", packet)
        objects = packet["candidate_objects"]
        self.assertEqual(len(objects), 9)
        self.assertTrue(
            all(row["geometry"]["field_navigation_precision"] == "NOT_NAVIGABLE" for row in objects)
        )
        self.assertEqual(brief["page_three_kitchen"]["map_layers"], [])
        self.assertEqual(packet["actions"][1]["action_id"], "ACTION_WATER_LOCATION_OR_INVENTORY")
        self.assertTrue(all(row["specificity"] == "CATEGORY_LEVEL" for row in packet["actions"]))
        visible = _visible(brief).lower()
        self.assertNotIn("on the report map", visible)
        self.assertNotIn("地图标出", visible)
        object_level = copy.deepcopy(packet)
        object_level["actions"][1]["specificity"] = "OBJECT_LEVEL"
        object_level["actions"][1]["candidate_id"] = objects[0]["candidate_id"]
        codes = {row["code"] for row in validate_packet(object_level, land_facts=facts)}
        self.assertIn("NAVIGATION_NOT_ALLOWED", codes)
        self.assertEqual(validate_three_page(brief, packet, land_facts=facts), [])


if __name__ == "__main__":
    unittest.main()
