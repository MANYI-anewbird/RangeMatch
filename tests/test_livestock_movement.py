"""Phase 3 movement labels: compactness, fragmentation, drawable-water distribution."""

from __future__ import annotations

import unittest
from typing import Any

from rangematch.advisor_generic_packet import project_generic_buyer_evidence_packet
from rangematch.livestock_movement import (
    COMPACT,
    CONCENTRATED,
    ELONGATED,
    FRAGMENTED_MULTIPART,
    MULTIPART,
    SINGLE_PART,
    classify_compactness,
    classify_drawable_water_distribution,
    classify_fragmentation,
    derive_movement_labels,
)
from rangematch.livestock_operating_profile import project_livestock_operating_profile

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


def _uo_with_geometry(*, extras: dict[str, Any] | None = None, geometry: dict | None = None) -> dict:
    facts = [
        _fact("VAR_F05_MEAN_ANNUAL_PRECIPITATION", 320.0, unit="mm"),
        _fact("VAR_F01_SLOPE_MEDIAN_DEGREES", 3.2, unit="deg"),
        _fact("VAR_F06_AREA_M2", 1_200_000.0, unit="m2"),
        _fact("VAR_F02_ANNUAL_HERB_PRODUCTION", 800.0, unit="kg/ha"),
        _fact("VAR_F03_MAPPED_WATER_CANDIDATE_COUNT", 2),
        _fact("VAR_F07_NEAREST_MAPPED_ROAD_DISTANCE_M", 12.0, unit="m"),
    ]
    uo: dict[str, Any] = {
        "parcel": {"geometry_id": "REAL_LISTING_PARCEL_GATE_001", "geometry_hash": HASH},
        "factors": {
            "F_BUNDLE": {"land_facts": facts},
            "F06_PARCEL_CONFIGURATION": {
                "evaluation_extras": extras
                or {
                    "compactness": 0.70,
                    "polygon_part_count": 1,
                    "geometry_hash": HASH,
                },
                "provenance": {"geometry_hash": HASH},
            },
        },
    }
    if geometry:
        uo["geometry"] = geometry
    return uo


def _drawable(cid: str, bbox: list[float]) -> dict[str, Any]:
    return {
        "candidate_id": cid,
        "candidate_type": "WATERBODY",
        "source_feature_type": "NHDWaterbody",
        "source_feature_id": cid,
        "geometry": {
            "kind": "BBOX",
            "centroid": None,
            "bbox": bbox,
            "field_navigation_precision": "AREA_ONLY",
        },
        "evidence_state": "MAPPED_CANDIDATE",
    }


class LivestockMovementTests(unittest.TestCase):
    def test_compactness_labels(self) -> None:
        self.assertEqual(classify_compactness(0.70, 1), COMPACT)
        self.assertEqual(classify_compactness(0.447, 1), ELONGATED)
        self.assertEqual(classify_compactness(0.90, 2), FRAGMENTED_MULTIPART)
        self.assertEqual(classify_fragmentation(1), SINGLE_PART)
        self.assertEqual(classify_fragmentation(3), MULTIPART)

    def test_stale_f06_hash_skips_shape_labels(self) -> None:
        uo = _uo_with_geometry(
            extras={"compactness": 0.70, "polygon_part_count": 1, "geometry_hash": "b" * 64}
        )
        packet = project_generic_buyer_evidence_packet(
            uo, listing_claims=[], confirmation_status="CONFIRMED", unified_output_ref="memory://x"
        )
        labels = derive_movement_labels(packet, uo, geometry_hash=HASH)
        self.assertIsNone(labels["compactness"])
        self.assertIsNone(labels["fragmentation"])

    def test_no_distribution_without_drawable(self) -> None:
        uo = _uo_with_geometry()
        packet = project_generic_buyer_evidence_packet(
            uo, listing_claims=[], confirmation_status="CONFIRMED", unified_output_ref="memory://x"
        )
        label, refs = classify_drawable_water_distribution(uo, packet)
        self.assertIsNone(label)
        self.assertEqual(refs, [])

    def test_concentrated_drawable_distribution(self) -> None:
        geometry = {
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
        }
        uo = _uo_with_geometry(geometry=geometry)
        packet = project_generic_buyer_evidence_packet(
            uo,
            listing_claims=[],
            confirmation_status="CONFIRMED",
            unified_output_ref="memory://x",
            candidate_inventory={
                "candidate_inventory": [
                    {
                        "candidate_id": "USGS_NHDPLUS_HR:NHDWaterbody:1",
                        "source_layer": "NHDWaterbody",
                        "source_feature_id": "1",
                        "intersects_parcel": True,
                        "bbox": [0.48, 0.48, 0.52, 0.52],
                    },
                    {
                        "candidate_id": "USGS_NHDPLUS_HR:NHDWaterbody:2",
                        "source_layer": "NHDWaterbody",
                        "source_feature_id": "2",
                        "intersects_parcel": True,
                        "bbox": [0.49, 0.49, 0.51, 0.51],
                    },
                ]
            },
        )
        for row in packet["candidate_objects"]:
            row["geometry"]["field_navigation_precision"] = "AREA_ONLY"
        label, refs = classify_drawable_water_distribution(uo, packet)
        self.assertEqual(label, CONCENTRATED)
        self.assertEqual(len(refs), 2)
        profile = project_livestock_operating_profile(packet, uo)
        types = {
            row["statement_type"]: row for row in profile["operating_domains"]["move"]["statements"]
        }
        self.assertEqual(types["DRAWABLE_WATER_DISTRIBUTION"]["qualifiers"], [CONCENTRATED])
        self.assertEqual(types["PARCEL_COMPACTNESS"]["qualifiers"], [COMPACT])

    def test_geometry_change_drops_old_shape_binding(self) -> None:
        uo = _uo_with_geometry()
        packet = project_generic_buyer_evidence_packet(
            uo, listing_claims=[], confirmation_status="CONFIRMED", unified_output_ref="memory://x"
        )
        first = project_livestock_operating_profile(packet, uo)
        new_hash = "b" * 64
        new_uo = _uo_with_geometry(
            extras={"compactness": 0.40, "polygon_part_count": 2, "geometry_hash": new_hash}
        )
        new_uo["parcel"]["geometry_hash"] = new_hash
        for fact in new_uo["factors"]["F_BUNDLE"]["land_facts"]:
            fact["geometry_hash"] = new_hash
        new_packet = project_generic_buyer_evidence_packet(
            new_uo, listing_claims=[], confirmation_status="CONFIRMED", unified_output_ref="memory://y"
        )
        second = project_livestock_operating_profile(new_packet, new_uo)
        first_shape = {
            row["statement_type"]: row["qualifiers"]
            for row in first["operating_domains"]["move"]["statements"]
            if row["statement_type"] in {"PARCEL_COMPACTNESS", "PARCEL_FRAGMENTATION"}
        }
        second_shape = {
            row["statement_type"]: row["qualifiers"]
            for row in second["operating_domains"]["move"]["statements"]
            if row["statement_type"] in {"PARCEL_COMPACTNESS", "PARCEL_FRAGMENTATION"}
        }
        self.assertEqual(first_shape["PARCEL_COMPACTNESS"], [COMPACT])
        self.assertEqual(second_shape["PARCEL_COMPACTNESS"], [FRAGMENTED_MULTIPART])
        self.assertEqual(second_shape["PARCEL_FRAGMENTATION"], [MULTIPART])
        self.assertNotEqual(first["profile_hash"], second["profile_hash"])


if __name__ == "__main__":
    unittest.main()
