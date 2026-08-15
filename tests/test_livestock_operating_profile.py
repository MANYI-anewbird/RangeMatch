"""Gate 1: Livestock Operating Profile integrity — no LLM, no F01–F08, no Sheep."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from rangematch.advisor_brief import generate_deterministic_brief
from rangematch.advisor_contract import land_fact_index
from rangematch.advisor_generic_packet import project_generic_buyer_evidence_packet
from rangematch.advisor_packet import project_cper_buyer_evidence_packet
from rangematch.advisor_visit import derive_authoritative_visit_purpose
from rangematch.livestock_operating_profile import (
    OperatingProfileError,
    profile_for_llm,
    profile_hash,
    project_livestock_operating_profile,
    validate_operating_profile,
)

ROOT = Path(__file__).resolve().parents[1]
NAMBE_BUNDLE = ROOT / "test-data/advisor/nambe/nambe_advisor_report_bundle.json"
NAMBE_PROFILE = ROOT / "test-data/advisor/nambe/nambe_cattle_operating_profile.json"
CPER_UO = ROOT / "test-data/land-profiles/unified_output_cper_001.json"
HASH = "a" * 64


def _fact(variable_id: str, value: Any, *, unit: str | None = None) -> dict:
    return {
        "variable_id": variable_id,
        "value": value,
        "unit": unit,
        "temporal_semantics": "snapshot",
        "spatial_semantics": "parcel_aggregate",
        "source_id": "TEST_SOURCE",
        "geometry_hash": HASH,
    }


def _synthetic_uo(*, water_count: int = 0, drop: str | None = None) -> dict[str, Any]:
    facts = [
        _fact("VAR_F05_MEAN_ANNUAL_PRECIPITATION", 320.0, unit="mm"),
        _fact("VAR_F01_SLOPE_MEDIAN_DEGREES", 3.2, unit="deg"),
        _fact("VAR_F06_AREA_M2", 1_200_000.0, unit="m2"),
        _fact("VAR_F02_ANNUAL_HERB_PRODUCTION", 800.0, unit="kg/ha"),
        _fact("VAR_F03_MAPPED_WATER_CANDIDATE_COUNT", water_count),
        _fact("VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M", 12.0, unit="m"),
    ]
    if drop:
        facts = [row for row in facts if row["variable_id"] != drop]
    return {
        "parcel": {
            "geometry_id": "REAL_LISTING_PARCEL_GATE_001",
            "geometry_hash": HASH,
        },
        "factors": {"F_BUNDLE": {"land_facts": facts}},
    }


def _generic_packet(uo: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return project_generic_buyer_evidence_packet(
        uo,
        listing_claims=[],
        confirmation_status="CONFIRMED",
        unified_output_ref="memory://synthetic_uo",
        **kwargs,
    )


def _nambe() -> tuple[dict[str, Any], dict[str, Any]]:
    bundle = json.loads(NAMBE_BUNDLE.read_text(encoding="utf-8"))
    return bundle["generic_evidence_packet"], bundle["unified_output"]


def _codes(violations: list[dict[str, str]]) -> set[str]:
    return {row["code"] for row in violations}


def _statements(profile: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket in (profile.get("operating_domains") or {}).values():
        rows.extend(bucket.get("statements") or [])
    return rows


def _rehash(profile: dict[str, Any]) -> dict[str, Any]:
    profile["profile_hash"] = profile_hash(profile)
    return profile


class LivestockOperatingProfileTests(unittest.TestCase):
    def test_nambe_cattle_profile_fixture_and_hashes(self) -> None:
        packet, uo = _nambe()
        profile = project_livestock_operating_profile(packet, uo, species_lens="CATTLE")
        self.assertEqual(validate_operating_profile(profile, packet, uo), [])
        stored = json.loads(NAMBE_PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(stored, profile)
        self.assertEqual(profile["domain_attention_order"], ["DRINK", "MOVE", "FEED"])
        self.assertEqual(
            profile["action_execution_order"],
            [
                "ACTION_ACCESS_DOCUMENTS",
                "ACTION_WATER_LOCATION_OR_INVENTORY",
                "ACTION_INTERPRET_RAP_FORAGE",
            ],
        )
        types = {row["statement_type"]: row for row in _statements(profile)}
        self.assertEqual(types["DRAWABLE_WATER_NONE"]["displayable"], False)
        self.assertEqual(types["DRAWABLE_WATER_NONE"]["narrative_role"], "GUARDRAIL_ONLY")
        self.assertNotIn("DRINK_DRAWABLE_WATER_NONE", profile["operating_thesis_inputs"])
        self.assertIn("DRINK_MAPPED_HYDROGRAPHY_LEAD_COUNT", profile["operating_thesis_inputs"])
        self.assertEqual(types["PARCEL_COMPACTNESS"]["qualifiers"], ["ELONGATED"])
        self.assertEqual(types["PARCEL_FRAGMENTATION"]["qualifiers"], ["SINGLE_PART"])
        self.assertNotIn("DRAWABLE_WATER_DISTRIBUTION", types)
        visit = profile["field_visit_purpose"]
        self.assertEqual(visit, derive_authoritative_visit_purpose(packet))
        self.assertEqual(visit["purpose_type"], "WATER_INVENTORY_AFTER_ACCESS_DOCUMENT")
        self.assertEqual(visit["object_refs"], [])
        workbench = profile_for_llm(profile)
        self.assertIn("DRINK_DRAWABLE_WATER_NONE", {row["statement_id"] for row in workbench["operating_domains"]["drink"]["statements"]})
        self.assertNotIn("DRINK_DRAWABLE_WATER_NONE", workbench["operating_thesis_inputs"])
        brief = generate_deterministic_brief(packet, land_facts=land_fact_index(uo), unified_output=uo)
        self.assertEqual(brief["page_one_advisor"]["visit_purpose"], visit["visit_state"])

    def test_duplicate_statement_id_fails(self) -> None:
        packet, uo = _nambe()
        profile = project_livestock_operating_profile(packet, uo)
        clone = copy.deepcopy(profile["operating_domains"]["feed"]["statements"][0])
        profile["operating_domains"]["drink"]["statements"].append(clone)
        self.assertIn(
            "DUPLICATE_STATEMENT_ID",
            _codes(validate_operating_profile(_rehash(profile), packet, uo)),
        )

    def test_observation_value_change_changes_profile_hash(self) -> None:
        uo = _synthetic_uo()
        packet = _generic_packet(uo)
        first = project_livestock_operating_profile(packet, uo)
        mutated_uo = copy.deepcopy(uo)
        for fact in mutated_uo["factors"]["F_BUNDLE"]["land_facts"]:
            if fact["variable_id"] == "VAR_F02_ANNUAL_HERB_PRODUCTION":
                fact["value"] = 801.0
        mutated_packet = _generic_packet(mutated_uo)
        second = project_livestock_operating_profile(mutated_packet, mutated_uo)
        self.assertNotEqual(first["profile_hash"], second["profile_hash"])
        self.assertNotEqual(first["packet_hash"], second["packet_hash"])

    def test_geometry_hash_change_invalidates_old_move_statements(self) -> None:
        uo = _synthetic_uo()
        packet = _generic_packet(uo)
        old = project_livestock_operating_profile(packet, uo)
        old_hash = packet["parcel"]["geometry_hash"]
        new_hash = "b" * 64
        new_uo = copy.deepcopy(uo)
        new_uo["parcel"]["geometry_hash"] = new_hash
        for fact in new_uo["factors"]["F_BUNDLE"]["land_facts"]:
            fact["geometry_hash"] = new_hash
        new_packet = _generic_packet(new_uo)
        new = project_livestock_operating_profile(new_packet, new_uo)
        old_move_refs = {
            ref
            for row in old["operating_domains"]["move"]["statements"]
            for ref in row["evidence_refs"]
        }
        new_move_refs = {
            ref
            for row in new["operating_domains"]["move"]["statements"]
            for ref in row["evidence_refs"]
        }
        self.assertIn(old_hash, old_move_refs)
        self.assertNotIn(old_hash, new_move_refs)
        self.assertIn(new_hash, new_move_refs)
        codes = _codes(validate_operating_profile(old, new_packet, new_uo))
        self.assertTrue(
            {"PACKET_HASH_MISMATCH", "STATEMENT_EVIDENCE_UNKNOWN", "MOVE_GEOMETRY_HASH_MISSING"}
            & codes
        )

    def test_statement_type_domain_binding(self) -> None:
        packet, uo = _nambe()
        profile = project_livestock_operating_profile(packet, uo)
        profile["operating_domains"]["feed"]["statements"][0]["domain"] = "DRINK"
        self.assertIn(
            "STATEMENT_DOMAIN_MISMATCH",
            _codes(validate_operating_profile(_rehash(profile), packet, uo)),
        )
        moved = project_livestock_operating_profile(packet, uo)
        snap = copy.deepcopy(moved["operating_domains"]["feed"]["statements"][0])
        snap["domain"] = "DRINK"
        moved["operating_domains"]["drink"]["statements"].append(snap)
        codes = _codes(validate_operating_profile(_rehash(moved), packet, uo))
        self.assertIn("STATEMENT_TYPE_DOMAIN_MISMATCH", codes)

    def test_inference_policy_rejects_dangerous_and_overlap(self) -> None:
        packet, uo = _nambe()
        profile = project_livestock_operating_profile(packet, uo)
        feed = profile["operating_domains"]["feed"]["statements"][0]
        feed["allowed_inferences"] = ["CARRYING_CAPACITY"]
        codes = _codes(validate_operating_profile(_rehash(profile), packet, uo))
        self.assertIn("DANGEROUS_INFERENCE_ALLOWED", codes)
        self.assertIn("STATEMENT_INFERENCE_POLICY_MISMATCH", codes)
        profile = project_livestock_operating_profile(packet, uo)
        feed = profile["operating_domains"]["feed"]["statements"][0]
        feed["allowed_inferences"] = ["MODELED_VEGETATION_CONTEXT", "AVAILABLE_FORAGE"]
        feed["prohibited_inferences"] = ["AVAILABLE_FORAGE", "CARRYING_CAPACITY"]
        codes = _codes(validate_operating_profile(_rehash(profile), packet, uo))
        self.assertIn("ALLOWED_PROHIBITED_OVERLAP", codes)

    def test_reference_mutations_fail(self) -> None:
        packet, uo = _nambe()
        profile = project_livestock_operating_profile(packet, uo)
        profile["operating_domains"]["feed"]["statements"][0]["value_refs"] = ["OBS_DOES_NOT_EXIST"]
        self.assertIn(
            "VALUE_REF_UNKNOWN",
            _codes(validate_operating_profile(_rehash(profile), packet, uo)),
        )
        profile = project_livestock_operating_profile(packet, uo)
        profile["operating_domains"]["drink"]["statements"][0]["object_refs"] = ["FAKE_CANDIDATE"]
        self.assertIn(
            "OBJECT_REF_UNKNOWN",
            _codes(validate_operating_profile(_rehash(profile), packet, uo)),
        )
        profile = project_livestock_operating_profile(packet, uo)
        profile["field_visit_purpose"]["object_refs"] = [
            packet["candidate_objects"][0]["candidate_id"]
        ]
        codes = _codes(validate_operating_profile(_rehash(profile), packet, uo))
        self.assertTrue({"VISIT_OBJECT_NOT_DRAWABLE", "VISIT_PIN_WITHOUT_DRAWABLE"} & codes)
        profile = project_livestock_operating_profile(packet, uo)
        profile["operating_thesis_inputs"] = ["STATEMENT_DOES_NOT_EXIST"]
        self.assertIn(
            "THESIS_INPUT_UNKNOWN",
            _codes(validate_operating_profile(_rehash(profile), packet, uo)),
        )
        profile = project_livestock_operating_profile(packet, uo)
        profile["operating_thesis_inputs"].append("DRINK_DRAWABLE_WATER_NONE")
        self.assertIn(
            "THESIS_INPUT_UNKNOWN",
            _codes(validate_operating_profile(_rehash(profile), packet, uo)),
        )
        profile = project_livestock_operating_profile(packet, uo)
        profile["parcel_ref"]["geometry_hash"] = "c" * 64
        self.assertIn(
            "PARCEL_REF_MISMATCH",
            _codes(validate_operating_profile(_rehash(profile), packet, uo)),
        )
        profile = project_livestock_operating_profile(packet, uo)
        profile["parcel_ref"]["parcel_id"] = "OTHER_PARCEL"
        self.assertIn(
            "PARCEL_REF_MISMATCH",
            _codes(validate_operating_profile(_rehash(profile), packet, uo)),
        )
        profile = project_livestock_operating_profile(packet, uo)
        profile["parcel_ref"]["confirmation_status"] = "UNCONFIRMED"
        self.assertIn(
            "CONFIRMATION_STATUS_MISMATCH",
            _codes(validate_operating_profile(_rehash(profile), packet, uo)),
        )
        profile = project_livestock_operating_profile(packet, uo)
        profile["parcel_ref"]["policy_scope"] = "CPER_FIXTURE_ONLY"
        codes = _codes(validate_operating_profile(_rehash(profile), packet, uo))
        self.assertIn("POLICY_SCOPE_MISMATCH", codes)

    def test_profile_does_not_hand_copy_canonical_numbers(self) -> None:
        packet, uo = _nambe()
        profile = project_livestock_operating_profile(packet, uo)
        blob = json.dumps(profile["operating_domains"])
        self.assertNotIn("0.447565", blob)
        for row in packet["observations"]:
            value = row["value"]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            token = format(value, ".10g")
            if len(token) >= 4:
                self.assertNotIn(token, blob, row["observation_id"])
        for statement in _statements(profile):
            self.assertNotIn("value", statement)

    def test_empty_domains_excluded_from_llm_and_attention(self) -> None:
        packet, uo = _nambe()
        profile = project_livestock_operating_profile(packet, uo)
        workbench = profile_for_llm(profile)
        self.assertNotIn("contain", workbench["operating_domains"])
        injected = copy.deepcopy(profile)
        injected["operating_domains"]["contain"] = {"statements": []}
        injected["operating_domains"]["manage"] = {"statements": []}
        injected["available_domains"] = ["FEED", "DRINK", "MOVE", "CONTAIN"]
        injected["domain_attention_order"] = ["DRINK", "CONTAIN", "FEED", "MOVE"]
        stripped = profile_for_llm(injected)
        self.assertNotIn("contain", stripped["operating_domains"])
        self.assertNotIn("CONTAIN", stripped["available_domains"])
        codes = _codes(validate_operating_profile(_rehash(injected), packet, uo))
        self.assertTrue({"EMPTY_DOMAIN_PRESENT", "ATTENTION_EMPTY_DOMAIN", "PROFILE_SCHEMA_INVALID"} & codes)

    def test_attention_order_excludes_unpopulated_domain(self) -> None:
        uo = _synthetic_uo()
        uo["factors"]["F_BUNDLE"]["land_facts"] = [
            row
            for row in uo["factors"]["F_BUNDLE"]["land_facts"]
            if row["variable_id"]
            not in {"VAR_F02_ANNUAL_HERB_PRODUCTION", "VAR_F05_MEAN_ANNUAL_PRECIPITATION"}
        ]
        packet = _generic_packet(uo)
        profile = project_livestock_operating_profile(packet, uo)
        self.assertNotIn("FEED", profile["available_domains"])
        self.assertEqual(profile["domain_attention_order"], ["DRINK", "MOVE"])

    def test_action_order_mismatch_fails(self) -> None:
        packet, uo = _nambe()
        profile = project_livestock_operating_profile(packet, uo)
        profile["action_execution_order"] = list(reversed(profile["action_execution_order"]))
        self.assertIn(
            "ACTION_ORDER_MISMATCH",
            _codes(validate_operating_profile(_rehash(profile), packet, uo)),
        )

    def test_retract_rap_retracts_feed_statement(self) -> None:
        uo = _synthetic_uo()
        packet = _generic_packet(uo)
        first = project_livestock_operating_profile(packet, uo)
        self.assertTrue(
            any(
                row["statement_id"] == "FEED_MODELED_PRODUCTION_SNAPSHOT"
                for row in first["operating_domains"]["feed"]["statements"]
            )
        )
        dropped = _synthetic_uo(drop="VAR_F02_ANNUAL_HERB_PRODUCTION")
        dropped_packet = _generic_packet(dropped)
        second = project_livestock_operating_profile(dropped_packet, dropped)
        ids = {row["statement_id"] for row in _statements(second)}
        self.assertNotIn("FEED_MODELED_PRODUCTION_SNAPSHOT", ids)
        self.assertIn("FEED_PRECIPITATION_CONTEXT", ids)

    def test_f03_failed_is_not_no_water(self) -> None:
        uo = _synthetic_uo(water_count=0)
        packet = _generic_packet(uo, f03_status="FAILED")
        profile = project_livestock_operating_profile(packet, uo)
        drink = profile["operating_domains"]["drink"]["statements"][0]
        self.assertEqual(drink["statement_type"], "WATER_INVENTORY_UNAVAILABLE")
        self.assertEqual(drink["narrative_role"], "GUARDRAIL_ONLY")
        self.assertFalse(drink["displayable"])
        self.assertNotIn(drink["statement_id"], profile["operating_thesis_inputs"])
        self.assertIn("ABSENCE_FROM_FAILED_INVENTORY", drink["prohibited_inferences"])

    def test_refuses_cper_and_sheep(self) -> None:
        cper = json.loads(CPER_UO.read_text(encoding="utf-8"))
        packet = project_cper_buyer_evidence_packet(
            cper,
            listing_claims=[],
            confirmation_status="CONFIRMED",
        )
        with self.assertRaises(OperatingProfileError) as err:
            project_livestock_operating_profile(packet, cper)
        self.assertEqual(err.exception.code, "CPER_POLICY_ON_GENERIC_PROFILE")
        nambe_packet, nambe_uo = _nambe()
        with self.assertRaises(OperatingProfileError) as sheep:
            project_livestock_operating_profile(nambe_packet, nambe_uo, species_lens="SHEEP")
        self.assertEqual(sheep.exception.code, "SPECIES_LENS_NOT_IN_PHASE_1")

    def test_zero_mapped_water_is_action_input_not_absence(self) -> None:
        uo = _synthetic_uo(water_count=0)
        packet = _generic_packet(uo)
        profile = project_livestock_operating_profile(packet, uo)
        drink = profile["operating_domains"]["drink"]["statements"][0]
        self.assertEqual(drink["statement_type"], "NO_MAPPED_HYDROGRAPHY_LEADS")
        self.assertEqual(drink["narrative_role"], "ACTION_INPUT")
        self.assertFalse(drink["displayable"])
        self.assertNotIn(drink["statement_id"], profile["operating_thesis_inputs"])
        self.assertIn("NOT_ABSENCE_FINDING", drink["qualifiers"])


if __name__ == "__main__":
    unittest.main()
