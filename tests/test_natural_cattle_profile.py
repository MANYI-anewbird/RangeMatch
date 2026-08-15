"""Phase 5 Gate: Combined Packet → Natural Cattle Profile."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from rangematch.environmental_gap_detector import detect_environmental_gaps
from rangematch.environmental_supplement_runner import (
    build_combined_environmental_evidence_packet,
    execute_supplement_plan,
    unit_test_supplement_runners,
)
from rangematch.mireye_environmental_profile import validate_mireye_environmental_profile
from rangematch.mireye_first_collection import derive_confirmed_f06
from rangematch.natural_cattle_profile import (
    APPROVED_HARD_CONSTRAINT_RULES,
    DOMAIN_FEED,
    DOMAIN_SOIL,
    DOMAIN_WATER,
    NaturalCattleProfileError,
    STATUS_CONSTRAINED,
    STATUS_CONDITIONAL,
    STATUS_INSUFFICIENT,
    STATUS_PROMISING,
    compute_natural_cattle_profile_hash,
    project_natural_cattle_profile,
    validate_natural_cattle_profile,
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


def _nambe_packet() -> dict:
    profile = json.loads(NAMBE_PROFILE.read_text(encoding="utf-8"))
    validate_mireye_environmental_profile(profile)
    geometry_hash = profile["parcel_ref"]["geometry_hash"]
    plan = detect_environmental_gaps(profile, f06_geometry_hash=geometry_hash)
    execution = execute_supplement_plan(
        plan,
        geometry=SIMPLE_POLYGON,
        geometry_id="phase5",
        geometry_hash=geometry_hash,
        runners=unit_test_supplement_runners(),
    )
    f06 = derive_confirmed_f06(SIMPLE_POLYGON, geometry_hash=geometry_hash)
    return build_combined_environmental_evidence_packet(
        mireye_profile=profile,
        gap_plan=plan,
        supplement_execution=execution,
        f06=f06,
    )


class Phase5NaturalCattleProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.packet = _nambe_packet()
        self.profile = project_natural_cattle_profile(self.packet)

    def test_schema_and_five_domains(self) -> None:
        validate_natural_cattle_profile(self.profile)
        domains = [row["domain"] for row in self.profile["domains"]]
        self.assertEqual(
            domains,
            [
                "TERRAIN",
                "FEED_VEGETATION",
                "WATER",
                "CLIMATE_HAZARD",
                "SOIL_ECOLOGY",
            ],
        )
        labels = [row["buyer_label"] for row in self.profile["domains"]]
        self.assertEqual(labels, ["Terrain", "Forage", "Water", "Climate", "Soil"])
        soil = next(row for row in self.profile["domains"] if row["domain"] == DOMAIN_SOIL)
        self.assertTrue(soil["reading"])
        self.assertIn(soil["confidence"], {"HIGH", "MEDIUM", "LOW", "INSUFFICIENT"})

    def test_every_supporting_ref_exists_in_packet(self) -> None:
        known = set()
        for key in (
            "mireye_observations",
            "core_observations",
            "supplement_observations",
        ):
            for obs in self.packet.get(key) or []:
                if obs.get("observation_id"):
                    known.add(obs["observation_id"])
        for row in self.profile["domains"]:
            for ref in row["supporting_refs"]:
                self.assertIn(ref, known)
            self.assertIsInstance(row["limitations"], list)
            self.assertIn(row["confidence"], {"HIGH", "MEDIUM", "LOW", "INSUFFICIENT"})

    def test_point_vs_parcel_is_scale_difference_not_conflict(self) -> None:
        self.assertTrue(
            any(
                row.get("kind") == "SPATIAL_SCALE_DIFFERENCE"
                for row in self.packet["conflicts"]
            )
        )
        terrain = next(
            row for row in self.profile["domains"] if row["domain"] == "TERRAIN"
        )
        self.assertEqual(terrain["evidence_classes"]["conflict_count"], 0)
        self.assertEqual(terrain["conflict_refs"], [])
        self.assertTrue(
            any("different spatial scales" in note for note in terrain["limitations"])
        )
        controlling = self.profile["overall_natural_foundation"]["controlling_factor"]
        self.assertNotEqual(
            controlling.get("reason"),
            "unresolved multi-source or cross-semantics conflict in Combined Packet",
        )

    def test_material_same_semantics_conflict_is_still_retained(self) -> None:
        packet = copy.deepcopy(self.packet)
        terrain_refs = [
            obs["observation_id"]
            for key in ("mireye_observations", "supplement_observations")
            for obs in packet.get(key) or []
            if obs.get("domain") == "TERRAIN" and obs.get("observation_id")
        ]
        self.assertGreaterEqual(len(terrain_refs), 2)
        packet["conflicts"].append(
            {
                "domain": "TERRAIN",
                "kind": "SAME_FIELD_MULTI_PROVIDER",
                "mireye_ref": terrain_refs[0],
                "supplement_ref": terrain_refs[-1],
                "resolution": "KEEP_BOTH_DO_NOT_AVERAGE",
            }
        )
        profile = project_natural_cattle_profile(packet)
        terrain = next(row for row in profile["domains"] if row["domain"] == "TERRAIN")
        self.assertEqual(terrain["evidence_classes"]["conflict_count"], 1)
        self.assertTrue(terrain["conflict_refs"])

    def test_source_unavailable_does_not_invent_negative_water_fact(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["supplement_observations"] = [
            obs
            for obs in packet["supplement_observations"]
            if obs.get("domain") != DOMAIN_WATER or obs.get("status") != "RETRIEVED"
        ]
        packet["mireye_observations"] = [
            obs
            for obs in packet["mireye_observations"]
            if obs.get("domain") != DOMAIN_WATER
            or obs.get("status") not in {"RETRIEVED", "PARTIAL"}
        ]
        packet["supplement_observations"].append(
            {
                "observation_id": "SUPPLEMENT_FAILURE_F03_LIVESTOCK_WATER",
                "field_id": "F03_LIVESTOCK_WATER",
                "domain": DOMAIN_WATER,
                "value": None,
                "status": "SOURCE_UNAVAILABLE",
                "spatial_semantics": "PARCEL",
                "provider": "RANGEMATCH_SUPPLEMENT",
            }
        )
        packet["conflicts"] = [
            row for row in packet["conflicts"] if row.get("domain") != DOMAIN_WATER
        ]
        profile = project_natural_cattle_profile(packet)
        water = next(row for row in profile["domains"] if row["domain"] == DOMAIN_WATER)
        blob = (water["reading"] + " " + " ".join(water["limitations"])).lower()
        self.assertIn("not evidence of no water", blob)
        self.assertIn("does not establish that the parcel lacks water", blob)
        self.assertNotEqual(
            profile["overall_natural_foundation"]["status"], STATUS_CONSTRAINED
        )

    def test_point_context_not_promoted_in_reading(self) -> None:
        for row in self.profile["domains"]:
            classes = row["evidence_classes"]
            if classes["parcel_count"] == 0 and (
                classes["point_count"] or classes["context_count"]
            ):
                self.assertEqual(row["confidence"], "LOW")
                self.assertTrue(
                    any("not promoted" in note.lower() for note in row["limitations"])
                )

    def test_rap_forage_domain_forbids_stocking_inference(self) -> None:
        forage = next(row for row in self.profile["domains"] if row["domain"] == DOMAIN_FEED)
        blob = (forage["reading"] + " " + " ".join(forage["limitations"])).lower()
        self.assertIn("stocking", blob)
        self.assertTrue(
            any(
                code.startswith("RAP_IS_NOT_STOCKING")
                for code in self.profile["prohibited_inferences"]
            )
        )

    def test_infrastructure_excluded(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["mireye_observations"].append(
            {
                "observation_id": "OBS_ROAD_NEAREST",
                "field_id": "nearest_mapped_road_distance_m",
                "domain": "ACCESS",
                "value": 12.0,
                "status": "RETRIEVED",
                "spatial_semantics": "CONTEXT",
                "provider": "MIREYE",
            }
        )
        profile = project_natural_cattle_profile(packet)
        blob = json.dumps(profile).lower()
        self.assertNotIn("obs_road_nearest", blob)
        self.assertNotIn("nearest_mapped_road", blob)
        self.assertNotIn("\"access\"", blob)

    def test_environmentally_constrained_disabled_without_registry(self) -> None:
        self.assertEqual(len(APPROVED_HARD_CONSTRAINT_RULES), 0)
        self.assertNotEqual(
            self.profile["overall_natural_foundation"]["status"], STATUS_CONSTRAINED
        )
        self.assertIsNone(
            self.profile["overall_natural_foundation"]["approved_hard_constraint_rule_id"]
        )
        self.assertIn(
            self.profile["overall_natural_foundation"]["status"],
            {STATUS_PROMISING, STATUS_CONDITIONAL, STATUS_INSUFFICIENT},
        )

    def test_profile_hash_ignores_built_at(self) -> None:
        a = project_natural_cattle_profile(self.packet, built_at="2026-01-01T00:00:00+00:00")
        b = project_natural_cattle_profile(self.packet, built_at="2026-08-15T12:00:00+00:00")
        self.assertEqual(a["profile_hash"], b["profile_hash"])
        self.assertNotEqual(a["provenance"]["built_at"], b["provenance"]["built_at"])
        self.assertEqual(a["profile_hash"], compute_natural_cattle_profile_hash(a))

    def test_evidence_withdrawal_changes_domain_and_overall(self) -> None:
        forage = next(row for row in self.profile["domains"] if row["domain"] == DOMAIN_FEED)
        before_refs = list(forage["supporting_refs"])
        self.assertTrue(before_refs)

        packet = copy.deepcopy(self.packet)
        for ref in before_refs:
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

        withdrawn = project_natural_cattle_profile(packet)
        forage_after = next(
            row for row in withdrawn["domains"] if row["domain"] == DOMAIN_FEED
        )
        self.assertEqual(forage_after["supporting_refs"], [])
        self.assertEqual(forage_after["confidence"], "INSUFFICIENT")
        self.assertNotEqual(forage_after["reading"], forage["reading"])
        self.assertNotIn(before_refs[0], forage_after["supporting_refs"])
        # Helper path also drops a single ref cleanly.
        one = withdraw_observation_and_reproject(
            self.packet, observation_id=before_refs[0]
        )
        forage_one = next(row for row in one["domains"] if row["domain"] == DOMAIN_FEED)
        self.assertNotIn(before_refs[0], forage_one["supporting_refs"])

    def test_controlling_factor_present(self) -> None:
        overall = self.profile["overall_natural_foundation"]
        controlling = overall["controlling_factor"]
        self.assertTrue(controlling["resolved"])
        self.assertIn(
            controlling["domain"],
            {
                "TERRAIN",
                "FEED_VEGETATION",
                "WATER",
                "CLIMATE_HAZARD",
                "SOIL_ECOLOGY",
            },
        )
        self.assertTrue(controlling["reason"])
        domain_row = next(
            row
            for row in self.profile["domains"]
            if row["domain"] == controlling["domain"]
        )
        self.assertEqual(controlling["supporting_refs"], domain_row["supporting_refs"])
        self.assertTrue(overall["headline"])
        self.assertTrue(overall["judgment"])
        validate_natural_cattle_profile(self.profile, packet=self.packet)


class Gate51HardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.packet = _nambe_packet()
        self.profile = project_natural_cattle_profile(self.packet)

    def test_dangling_supporting_ref_fails_closed(self) -> None:
        broken = copy.deepcopy(self.profile)
        broken["domains"][0]["supporting_refs"] = list(
            broken["domains"][0]["supporting_refs"]
        ) + ["EVIDENCE_FROM_ANOTHER_RUN"]
        broken["profile_hash"] = compute_natural_cattle_profile_hash(broken)
        with self.assertRaises(NaturalCattleProfileError) as ctx:
            validate_natural_cattle_profile(broken, packet=self.packet)
        self.assertIn("dangling_supporting_ref", str(ctx.exception))

    def test_stale_controlling_factor_refs_fail_closed(self) -> None:
        broken = copy.deepcopy(self.profile)
        broken["overall_natural_foundation"]["controlling_factor"]["supporting_refs"] = [
            "STALE_CTRL_REF"
        ]
        broken["profile_hash"] = compute_natural_cattle_profile_hash(broken)
        with self.assertRaises(NaturalCattleProfileError):
            validate_natural_cattle_profile(broken, packet=self.packet)

    def test_cross_run_packet_cannot_validate_or_mutate_this_profile(self) -> None:
        other = copy.deepcopy(self.packet)
        other["packet_hash"] = "b" * 64
        other["run_id"] = "other_run"
        frozen_hash = self.profile["profile_hash"]
        # Mutating another run's packet must not alter this profile object.
        other["mireye_observations"] = []
        self.assertEqual(self.profile["profile_hash"], frozen_hash)
        with self.assertRaises(NaturalCattleProfileError) as ctx:
            validate_natural_cattle_profile(self.profile, packet=other)
        self.assertIn("packet_hash_mismatch", str(ctx.exception))

    def test_semantic_hash_stable_under_order_and_built_at(self) -> None:
        shuffled = copy.deepcopy(self.packet)
        shuffled["mireye_observations"] = list(
            reversed(list(shuffled["mireye_observations"]))
        )
        shuffled["supplement_observations"] = list(
            reversed(list(shuffled["supplement_observations"]))
        )
        a = project_natural_cattle_profile(
            self.packet, built_at="2026-01-01T00:00:00+00:00"
        )
        b = project_natural_cattle_profile(
            shuffled, built_at="2026-12-31T23:59:59+00:00"
        )
        self.assertEqual(a["profile_hash"], b["profile_hash"])

    def test_removing_supporting_evidence_changes_profile_hash(self) -> None:
        forage = next(row for row in self.profile["domains"] if row["domain"] == DOMAIN_FEED)
        self.assertTrue(forage["supporting_refs"])
        target = forage["supporting_refs"][0]
        after = withdraw_observation_and_reproject(self.packet, observation_id=target)
        self.assertNotEqual(after["profile_hash"], self.profile["profile_hash"])
        forage_after = next(row for row in after["domains"] if row["domain"] == DOMAIN_FEED)
        self.assertNotIn(target, forage_after["supporting_refs"])

    def test_limitation_cannot_author_land_fact_or_status(self) -> None:
        poisoned = copy.deepcopy(self.profile)
        poisoned["domains"][2]["reading"] = "Water: no water on the parcel."
        poisoned["profile_hash"] = compute_natural_cattle_profile_hash(poisoned)
        with self.assertRaises(NaturalCattleProfileError) as ctx:
            validate_natural_cattle_profile(poisoned, packet=self.packet)
        self.assertIn("limitation_impersonating_fact", str(ctx.exception))

        # SOURCE_UNAVAILABLE-only water stays non-constrained and non-negative.
        packet = copy.deepcopy(self.packet)
        packet["mireye_observations"] = [
            obs
            for obs in packet["mireye_observations"]
            if obs.get("domain") != DOMAIN_WATER
            or obs.get("status") not in {"RETRIEVED", "PARTIAL"}
        ]
        packet["supplement_observations"] = [
            obs
            for obs in packet["supplement_observations"]
            if obs.get("domain") != DOMAIN_WATER or obs.get("status") != "RETRIEVED"
        ] + [
            {
                "observation_id": "SUPPLEMENT_FAILURE_WATER_ONLY",
                "field_id": "F03_LIVESTOCK_WATER",
                "domain": DOMAIN_WATER,
                "value": None,
                "status": "SOURCE_UNAVAILABLE",
                "spatial_semantics": "PARCEL",
                "provider": "RANGEMATCH_SUPPLEMENT",
            }
        ]
        packet["conflicts"] = [
            row for row in packet["conflicts"] if row.get("domain") != DOMAIN_WATER
        ]
        profile = project_natural_cattle_profile(packet)
        water = next(row for row in profile["domains"] if row["domain"] == DOMAIN_WATER)
        self.assertEqual(water["supporting_refs"], [])
        self.assertEqual(water["confidence"], "INSUFFICIENT")
        self.assertNotEqual(
            profile["overall_natural_foundation"]["status"], STATUS_CONSTRAINED
        )
        self.assertNotIn(
            "SUPPLEMENT_FAILURE_WATER_ONLY",
            profile["overall_natural_foundation"]["supporting_refs"],
        )

    def test_redundant_evidence_withdrawal(self) -> None:
        packet = copy.deepcopy(self.packet)
        # Ensure Soil has two independent PARCEL retrieved refs.
        packet["supplement_observations"] = [
            obs
            for obs in packet["supplement_observations"]
            if obs.get("domain") != DOMAIN_SOIL
        ] + [
            {
                "observation_id": "SOIL_PARCEL_A",
                "field_id": "VAR_F04_SDA_VALID_COVERAGE_FRACTION",
                "domain": DOMAIN_SOIL,
                "value": 0.8,
                "unit": "fraction",
                "status": "RETRIEVED",
                "spatial_semantics": "PARCEL",
                "provider": "RANGEMATCH_SUPPLEMENT",
            },
            {
                "observation_id": "SOIL_PARCEL_B",
                "field_id": "VAR_F04_KNOWN_COMPONENT_SHARE",
                "domain": DOMAIN_SOIL,
                "value": 0.7,
                "unit": "fraction",
                "status": "RETRIEVED",
                "spatial_semantics": "PARCEL",
                "provider": "RANGEMATCH_SUPPLEMENT",
            },
        ]
        packet["mireye_observations"] = [
            obs
            for obs in packet["mireye_observations"]
            if obs.get("domain") != DOMAIN_SOIL
            or obs.get("status") not in {"RETRIEVED", "PARTIAL"}
        ]
        packet["conflicts"] = [
            row for row in packet["conflicts"] if row.get("domain") != DOMAIN_SOIL
        ]
        # Keep packet_hash stable string for validator binding in this synthetic case.
        base = project_natural_cattle_profile(packet)
        soil = next(row for row in base["domains"] if row["domain"] == DOMAIN_SOIL)
        self.assertGreaterEqual(len(soil["supporting_refs"]), 2)
        self.assertEqual(soil["confidence"], "HIGH")
        before_reading = soil["reading"]
        before_hash = base["profile_hash"]

        one_removed = withdraw_observation_and_reproject(
            packet, observation_id="SOIL_PARCEL_A"
        )
        soil_one = next(row for row in one_removed["domains"] if row["domain"] == DOMAIN_SOIL)
        self.assertNotIn("SOIL_PARCEL_A", soil_one["supporting_refs"])
        self.assertIn("SOIL_PARCEL_B", soil_one["supporting_refs"])
        self.assertNotEqual(soil_one["confidence"], "INSUFFICIENT")
        self.assertIn("PARCEL", soil_one["reading"])
        self.assertNotEqual(one_removed["profile_hash"], before_hash)
        # Reading may change counts but remains a supported soil reading.
        self.assertNotEqual(soil_one["supporting_refs"], soil["supporting_refs"])

        packet2 = copy.deepcopy(packet)
        for key in ("mireye_observations", "core_observations", "supplement_observations"):
            packet2[key] = [
                obs
                for obs in (packet2.get(key) or [])
                if obs.get("observation_id") not in {"SOIL_PARCEL_A", "SOIL_PARCEL_B"}
            ]
        final = project_natural_cattle_profile(packet2)
        soil_final = next(row for row in final["domains"] if row["domain"] == DOMAIN_SOIL)
        self.assertEqual(soil_final["supporting_refs"], [])
        self.assertEqual(soil_final["confidence"], "INSUFFICIENT")
        self.assertNotEqual(soil_final["reading"], before_reading)
        self.assertNotEqual(final["profile_hash"], one_removed["profile_hash"])

    def test_controlling_factor_recomputed_after_withdrawal(self) -> None:
        controlling = self.profile["overall_natural_foundation"]["controlling_factor"]
        self.assertTrue(controlling["resolved"])
        stale_domain = controlling["domain"]
        stale_refs = list(controlling["supporting_refs"])
        self.assertTrue(stale_refs)

        packet = copy.deepcopy(self.packet)
        for ref in stale_refs:
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

        recomputed = project_natural_cattle_profile(packet)
        new_ctrl = recomputed["overall_natural_foundation"]["controlling_factor"]
        # Stale controlling factor must not survive with the old supporting refs.
        self.assertNotEqual(new_ctrl["supporting_refs"], stale_refs)
        if new_ctrl.get("resolved"):
            self.assertTrue(new_ctrl.get("domain"))
            if new_ctrl["domain"] == stale_domain:
                # Same domain only allowed if it still has different remaining support.
                self.assertTrue(new_ctrl["supporting_refs"])
                self.assertTrue(
                    set(new_ctrl["supporting_refs"]).isdisjoint(set(stale_refs))
                )
            domain_row = next(
                row
                for row in recomputed["domains"]
                if row["domain"] == new_ctrl["domain"]
            )
            self.assertEqual(new_ctrl["supporting_refs"], domain_row["supporting_refs"])
        else:
            self.assertIsNone(new_ctrl.get("domain"))
            self.assertEqual(new_ctrl["supporting_refs"], [])
        self.assertNotEqual(recomputed["profile_hash"], self.profile["profile_hash"])
        validate_natural_cattle_profile(recomputed, packet=packet)


if __name__ == "__main__":
    unittest.main()
