"""Generic Evidence Packet projector — no network, no CPER inheritance."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from rangematch.advisor_brief import generate_deterministic_brief
from rangematch.advisor_contract import land_fact_index, validate_packet, validate_three_page
from rangematch.advisor_generic_packet import (
    build_generic_minimal_policy,
    project_generic_buyer_evidence_packet,
)
from rangematch.advisor_packet import (
    CperDemoPolicyRejected,
    MissingPolicyError,
    build_cper_demo_policy,
    project_buyer_evidence_packet,
    project_cper_buyer_evidence_packet,
)

ROOT = Path(__file__).resolve().parents[1]
CPER_UO = ROOT / "test-data" / "land-profiles" / "unified_output_cper_001.json"
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
        "factors": {
            "F_BUNDLE": {"land_facts": facts},
        },
    }


def _inventory_one() -> dict[str, Any]:
    return {
        "candidate_inventory": [
            {
                "candidate_id": "USGS_NHDPLUS_HR:NHDWaterbody:99",
                "source_layer": "NHDWaterbody",
                "source_feature_id": "99",
                "intersects_parcel": True,
                "bbox": [-104.9, 40.49, -104.89, 40.5],
                "gnis_name": None,
            }
        ]
    }


class GenericEvidencePacketTests(unittest.TestCase):
    def test_generic_packet_validates_with_empty_claims(self) -> None:
        uo = _synthetic_uo(water_count=0)
        packet = project_generic_buyer_evidence_packet(
            uo,
            listing_claims=[],
            confirmation_status="CONFIRMED",
            unified_output_ref="memory://synthetic_uo",
            candidate_inventory=None,
        )
        facts = land_fact_index(uo)
        violations = validate_packet(packet, land_facts=facts)
        self.assertEqual(violations, [], violations)
        self.assertEqual(packet["technical_references"]["policy_scope"], "GENERIC_MINIMAL")
        self.assertEqual(packet["technical_references"]["policy"], "build_generic_minimal_policy")
        self.assertFalse(packet["parcel"]["is_engineering_test_geometry"])
        self.assertEqual(packet["listing_claims"], [])
        self.assertIsNone(packet["technical_references"]["f03_candidate_inventory"])
        action_ids = {row["action_id"] for row in packet["actions"]}
        self.assertIn("ACTION_ACCESS_DOCUMENTS", action_ids)
        self.assertTrue(
            {
                "ACTION_WATER_FIELD_CATEGORY",
                "ACTION_WATER_LOCATION_OR_INVENTORY",
                "ACTION_WATER_SOURCE_UNAVAILABLE",
                "ACTION_ASK_SELLER_WATER",
            }
            & action_ids
        )
        self.assertIn("ACTION_INTERPRET_RAP_FORAGE", action_ids)
        brief = generate_deterministic_brief(packet, land_facts=facts, unified_output=uo)
        self.assertEqual(validate_three_page(brief, packet, land_facts=facts), [])

    def test_f03_failed_and_no_cper_paths(self) -> None:
        uo = _synthetic_uo(water_count=0)
        packet = project_generic_buyer_evidence_packet(
            uo,
            listing_claims=[],
            confirmation_status="CONFIRMED",
            unified_output_ref="memory://synthetic_uo",
            f03_status="FAILED",
        )
        self.assertEqual(packet["candidate_objects"], [])
        self.assertEqual(packet["technical_references"]["f03_status"], "FAILED")
        water = next(
            row
            for row in packet["observations"]
            if row["observation_id"] == "OBS_WATER_COUNT"
        )
        self.assertEqual(water["evidence_state"], "SOURCE_UNAVAILABLE")
        blob = json.dumps(packet)
        self.assertNotIn("cper_f03", blob.lower())
        self.assertNotIn("ENGINEERING_TEST_GEOMETRY_CPER", blob)
        self.assertEqual(validate_packet(packet, land_facts=land_fact_index(uo)), [])

    def test_objects_without_listing_claims(self) -> None:
        uo = _synthetic_uo(water_count=1)
        packet = project_generic_buyer_evidence_packet(
            uo,
            listing_claims=[],
            confirmation_status="CONFIRMED",
            unified_output_ref="memory://synthetic_uo",
            candidate_inventory=_inventory_one(),
            f03_inventory_ref="memory://inventory",
        )
        self.assertEqual(len(packet["candidate_objects"]), 1)
        self.assertEqual(packet["technical_references"]["f03_candidate_inventory"], "memory://inventory")
        self.assertEqual(validate_packet(packet, land_facts=land_fact_index(uo)), [])

    def test_refuses_cper_fixture_and_cper_policy_on_real_parcel(self) -> None:
        cper = json.loads(CPER_UO.read_text(encoding="utf-8"))
        with self.assertRaises(MissingPolicyError):
            project_generic_buyer_evidence_packet(
                cper,
                listing_claims=[],
                unified_output_ref="test-data/land-profiles/unified_output_cper_001.json",
            )
        real = copy.deepcopy(cper)
        real["parcel"]["geometry_id"] = "REAL_LISTING_PARCEL_001"
        real["parcel"]["geometry_hash"] = HASH
        for factor in (real.get("factors") or {}).values():
            for fact in factor.get("land_facts") or []:
                fact["geometry_hash"] = HASH
        with self.assertRaises(CperDemoPolicyRejected):
            project_buyer_evidence_packet(
                real, listing_claims=[], policy=build_cper_demo_policy
            )

    def test_missing_land_fact_is_honest_not_invented(self) -> None:
        uo = _synthetic_uo(drop="VAR_F02_ANNUAL_HERB_PRODUCTION")
        packet = project_generic_buyer_evidence_packet(
            uo,
            listing_claims=[],
            confirmation_status="CONFIRMED",
            unified_output_ref="memory://partial_uo",
        )
        rap = next(
            row for row in packet["observations"] if row["observation_id"] == "OBS_RAP_PROD"
        )
        self.assertIsNone(rap["value"])
        self.assertEqual(rap["evidence_state"], "SOURCE_UNAVAILABLE")
        coverage = packet["technical_references"]["coverage_by_variable"]
        missing = next(
            row for row in coverage if row["variable_id"] == "VAR_F02_ANNUAL_HERB_PRODUCTION"
        )
        self.assertEqual(missing["status"], "MISSING")
        self.assertEqual(validate_packet(packet, land_facts=land_fact_index(uo)), [])

    def test_cper_projector_still_works(self) -> None:
        cper = json.loads(CPER_UO.read_text(encoding="utf-8"))
        packet = project_cper_buyer_evidence_packet(
            cper,
            listing_claims=[],
            confirmation_status="CONFIRMED",
        )
        self.assertEqual(packet["technical_references"]["policy_scope"], "CPER_FIXTURE_ONLY")

    def test_generic_policy_name_is_stable(self) -> None:
        self.assertEqual(build_generic_minimal_policy.__name__, "build_generic_minimal_policy")


if __name__ == "__main__":
    unittest.main()
