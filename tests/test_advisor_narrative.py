from __future__ import annotations

import copy
import json
from pathlib import Path

from rangematch.advisor_insight import project_advisor_llm_workbench
from rangematch.advisor_narrative import NARRATIVE_SCHEMA, validate_advisor_narrative

ROOT = Path(__file__).resolve().parents[1]


def _workbench():
    return json.loads((ROOT / "test-data/advisor/nambe/nambe_advisor_report_bundle.json").read_text())["llm_workbench"]


def _narrative():
    return {
        "schema_version": NARRATIVE_SCHEMA,
        "thesis": "Confirm the entrance basis before using a field visit to investigate livestock water.",
        "executive_memo": "The tract already has enough public evidence to organize diligence, but the two signals most likely to be overread are road contact and mapped water. Water is the larger operating gap. Access documents should still come first because they can determine whether a trip has a defined job before travel money is spent.",
        "evidence_chain": [
            {"point":"Road contact creates a document question.","evidence_refs":["OBS_ROAD","BOTTLENECK_LEGAL_ACCESS"],"context_refs":[],"knowledge_refs":["LEGAL_ACCESS_DILIGENCE_001"],"interpretation":"A mapped road touching the outline creates a precise question for title, but it does not establish an entrance right.","decision_effect":"Request the documentary entrance basis before travel."},
            {"point":"Mapped water gives the visit a purpose.","evidence_refs":["OBS_WATER_COUNT"],"context_refs":[],"knowledge_refs":["LIVESTOCK_WATER_DILIGENCE_001"],"interpretation":"Mapped hydrography is enough to organize a field review, but none of it is yet dependable operating water.","decision_effect":"If access holds, make water verification the job of the visit."},
        ],
        "action_pivot":{"largest_gap":"Livestock water is the larger operating-evidence gap.","first_action_id":"ACTION_ACCESS_DOCUMENTS","first_action_reason":"Request access documents first because they can determine whether a trip has a defined job before travel.","deferred_action_ids":["ACTION_INTERPRET_RAP_FORAGE"],"deferred_reason":"More forage interpretation does not resolve entrance or operating water."},
        "conditional_path":{"if_favorable":"If the entrance basis holds, schedule a water-focused field review.","if_unfavorable":"If the entrance basis cannot be shown, pause travel and route the question to title.","still_unknown":"Neither branch establishes dependable livestock water or a purchase conclusion."},
        "client_summary":"We are not ruling the tract in or out. Confirm the entrance first, then decide whether a water-focused visit is worth the trip.",
        "professional_boundary":"This is pre-visit diligence sequencing, not a carrying capacity, legal, grazing, suitability, or purchase conclusion.",
    }


def test_narrative_passes_with_grounded_chain_and_legal_first_action():
    assert validate_advisor_narrative(_narrative(), _workbench()) == []


def test_narrative_fails_when_evidence_is_withdrawn():
    workbench = copy.deepcopy(_workbench())
    workbench["observations"] = [row for row in workbench["observations"] if row["observation_id"] != "OBS_ROAD"]
    codes = {row["code"] for row in validate_advisor_narrative(_narrative(), workbench)}
    assert "NARRATIVE_PACKET_REF_UNKNOWN" in codes


def test_narrative_fails_on_illegal_first_action_and_internal_id_in_prose():
    narrative = _narrative()
    narrative["action_pivot"]["first_action_id"] = "ACTION_WATER_LOCATION_OR_INVENTORY"
    narrative["thesis"] += " Then use ACTION_WATER_LOCATION_OR_INVENTORY."
    codes = {row["code"] for row in validate_advisor_narrative(narrative, _workbench())}
    assert "ILLEGAL_FIRST_ACTION" in codes
    assert "NARRATIVE_INTERNAL_ID" in codes


def test_narrative_rejects_operating_and_transaction_advice():
    narrative = _narrative()
    narrative["conditional_path"]["if_favorable"] = (
        "If access holds, proceed with livestock acquisition because ranch viability is confirmed."
    )
    codes = {row["code"] for row in validate_advisor_narrative(narrative, _workbench())}
    assert "NARRATIVE_PROHIBITED_CONCLUSION" in codes
