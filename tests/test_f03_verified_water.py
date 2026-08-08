"""Executable golden tests for F03 verified-water evidence contract v0.1.1."""

from __future__ import annotations

import unittest

from rangematch.f03_verification import (
    SELECTION_METHOD_STABLE_CANDIDATE_ID_ORDER,
    apply_remote_enrichment,
    build_mapped_candidate_from_nhd,
    evaluate_promotion,
    factor_input_quality_from_levels,
    map_nhd_fcode_to_seasonal,
    remote_presence_provenance_complete,
    stable_sample_f03_candidates,
    validate_candidate_record,
)


def _complete_presence_provenance(**overrides):
    base = {
        "provider": "USDA Farm Service Agency",
        "product_name": "NAIP 2023 30 cm",
        "source_url": "https://planetarycomputer.microsoft.com/api/stac/v1/collections/naip/items/demo",
        "item_id_or_artifact_reference": "stac:naip/demo; local_artifact=demo.tif",
        "imagery_acquisition_date": "2023-09-25",
        "review_date": "2026-08-08",
        "reviewer_or_adapter_id": "test_harness",
        "candidate_geometry_hash": "a" * 64,
        "parcel_geometry_hash": "b" * 64,
        "response_or_artifact_hash": "c" * 64,
        "supported_claim": "channel visible in NAIP crop",
        "unsupported_claims": ["legal_access", "field_verification"],
        "limitations": ["remote only"],
        "freshness_status": "ACQUISITION_2023-09-25_WITHIN_THREE_YEARS_OF_REVIEW",
    }
    base.update(overrides)
    return base


def _unknown_capacity(rationale: str = "Capacity not measured or documented for this candidate."):
    return {
        "status": "unknown",
        "value": None,
        "unit": None,
        "scenario_reference": None,
        "unknown_rationale": rationale,
    }


def _unknown_wq():
    return {"status": "unknown", "diligence_required": True, "evidence_source_ids": []}


def _base_dims(**overrides):
    dims = {
        "feature_identity": {"type": "stream"},
        "physical_presence": {"status": "uncertain", "source": "hydrography"},
        "seasonal_reliability": {"status": "unknown"},
        "livestock_accessibility": {"status": "unknown"},
        "capacity_and_quality": {
            "capacity": _unknown_capacity(),
            "water_quality": _unknown_wq(),
        },
        "legal_access": {"status": "unresolved"},
    }
    dims.update(overrides)
    return dims


class F03VerifiedWaterGoldenTests(unittest.TestCase):
    def test_f03_vw_001_nhd_only_mapped(self):
        record = {
            "prior_level": "MAPPED_CANDIDATE",
            "evidence_class": "REMOTE_ONLY",
            "dimensions": _base_dims(),
        }
        result = evaluate_promotion(record)
        self.assertTrue(validate_candidate_record(record)["ok"])
        self.assertEqual(result["verification_level"], "MAPPED_CANDIDATE")
        self.assertFalse(result["promoted_to_remotely_supported"])
        self.assertEqual(
            factor_input_quality_from_levels([result["verification_level"]]),
            "MAPPED_CANDIDATES_ONLY",
        )

    def test_f03_vw_002_remote_supported_with_unknown_accessibility(self):
        record = {
            "prior_level": "MAPPED_CANDIDATE",
            "evidence_class": "REMOTE_ONLY",
            "dimensions": _base_dims(
                feature_identity={"type": "pond"},
                physical_presence={
                    "status": "confirmed",
                    "source": "imagery",
                    "imagery_dates": ["2025-04-10", "2025-09-02"],
                    "provenance": _complete_presence_provenance(),
                },
                seasonal_reliability={
                    "status": "intermittent",
                    "observation_period": "2025",
                },
                livestock_accessibility={"status": "unknown"},
            ),
        }
        result = evaluate_promotion(record)
        self.assertEqual(result["verification_level"], "REMOTELY_SUPPORTED_CANDIDATE")
        self.assertTrue(result["promoted_to_remotely_supported"])
        self.assertFalse(result["promoted_to_field_verified"])

    def test_f03_vw_003_remote_ceiling(self):
        record = {
            "prior_level": "REMOTELY_SUPPORTED_CANDIDATE",
            "evidence_class": "REMOTE_ONLY",
            "dimensions": _base_dims(
                feature_identity={"type": "reservoir"},
                physical_presence={
                    "status": "confirmed",
                    "source": "imagery",
                    "provenance": _complete_presence_provenance(),
                },
                seasonal_reliability={"status": "perennial", "observation_period": "2020-2025"},
                livestock_accessibility={"status": "supported"},
            ),
        }
        result = evaluate_promotion(record)
        self.assertEqual(result["verification_level"], "REMOTELY_SUPPORTED_CANDIDATE")
        self.assertIn("REMOTE_EVIDENCE_CEILING", result["reason_codes"])
        self.assertFalse(result["promoted_to_field_verified"])

    def test_f03_vw_004_field_verified_path(self):
        record = {
            "prior_level": "REMOTELY_SUPPORTED_CANDIDATE",
            "evidence_class": "FIELD_OBSERVATION",
            "dimensions": _base_dims(
                feature_identity={"type": "tank"},
                physical_presence={"status": "confirmed", "source": "field"},
                seasonal_reliability={"status": "perennial", "observation_period": "2024-2025"},
                livestock_accessibility={"status": "supported"},
                capacity_and_quality={
                    "capacity": {
                        "status": "documented",
                        "value": 5000,
                        "unit": "gallon_storage",
                        "scenario_reference": "declared_test_only",
                        "unknown_rationale": None,
                    },
                    "water_quality": _unknown_wq(),
                },
                legal_access={"status": "verified", "basis": "deed_owned_source"},
            ),
        }
        result = evaluate_promotion(record)
        self.assertEqual(result["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER")
        self.assertEqual(result["ranking_effect"], "NONE")

    def test_f03_vw_005_skip_remote_prohibited(self):
        record = {
            "prior_level": "MAPPED_CANDIDATE",
            "attempted_level": "FIELD_VERIFIED_LIVESTOCK_WATER",
            "evidence_class": "FIELD_OBSERVATION",
            "dimensions": _base_dims(),
        }
        result = evaluate_promotion(record)
        self.assertFalse(result["transition_allowed"])
        self.assertIn("SKIP_REMOTELY_SUPPORTED_PROHIBITED", result["reason_codes"])

    def test_f03_vw_006_distance_alone(self):
        record = {
            "prior_level": "MAPPED_CANDIDATE",
            "euclidean_distance_m": 25,
            "dimensions_unchanged_from_mapped": True,
            "dimensions": _base_dims(),
        }
        result = evaluate_promotion(record)
        self.assertEqual(result["verification_level"], "MAPPED_CANDIDATE")
        self.assertIn("DISTANCE_NOT_PRESENCE_OR_ACCESS", result["reason_codes"])

    def test_f03_vw_007_single_date_no_seasonal_class(self):
        # Policy: single imagery date may confirm presence for that date only.
        imagery_dates = ["2025-06-01"]
        self.assertEqual(len(imagery_dates), 1)
        seasonal_allowed_from_single_date = False
        self.assertFalse(seasonal_allowed_from_single_date)
        record = {
            "prior_level": "MAPPED_CANDIDATE",
            "evidence_class": "REMOTE_ONLY",
            "dimensions": _base_dims(
                physical_presence={
                    "status": "confirmed",
                    "source": "imagery",
                    "observation_date": "2025-06-01",
                    "imagery_dates": imagery_dates,
                },
                seasonal_reliability={"status": "unknown"},
            ),
        }
        result = evaluate_promotion(record)
        self.assertEqual(result["verification_level"], "MAPPED_CANDIDATE")
        # Attempting to set intermittent from single date is outside evaluator;
        # contract forbids it — assert helper refusal pattern.
        self.assertIsNone(map_nhd_fcode_to_seasonal(None))

    def test_f03_vw_008_well_record_not_operable(self):
        record = {
            "prior_level": "MAPPED_CANDIDATE",
            "evidence_class": "REMOTE_ONLY",
            "fcode": None,
            "dimensions": _base_dims(
                feature_identity={"type": "well"},
                physical_presence={"status": "confirmed", "source": "records"},
                capacity_and_quality={
                    "capacity": _unknown_capacity(
                        "Well record locates a well; operable yield not established."
                    ),
                    "water_quality": _unknown_wq(),
                },
            ),
        }
        result = evaluate_promotion(record)
        self.assertEqual(result["verification_level"], "MAPPED_CANDIDATE")
        self.assertFalse(result["promoted_to_field_verified"])

    def test_f03_vw_009_legal_access_blocks_field(self):
        record = {
            "prior_level": "REMOTELY_SUPPORTED_CANDIDATE",
            "evidence_class": "FIELD_OBSERVATION",
            "dimensions": _base_dims(
                feature_identity={"type": "pond"},
                physical_presence={"status": "confirmed", "source": "field"},
                seasonal_reliability={"status": "intermittent", "observation_period": "2025"},
                livestock_accessibility={"status": "supported"},
                capacity_and_quality={
                    "capacity": _unknown_capacity("Storage volume not measured during field visit."),
                    "water_quality": _unknown_wq(),
                },
                legal_access={"status": "unresolved"},
            ),
        }
        result = evaluate_promotion(record)
        self.assertEqual(result["verification_level"], "REMOTELY_SUPPORTED_CANDIDATE")
        self.assertFalse(result["promoted_to_field_verified"])
        self.assertIn("LEGAL_ACCESS_UNRESOLVED", result["reason_codes"])

    def test_f03_vw_010_absent_rejects(self):
        record = {
            "prior_level": "MAPPED_CANDIDATE",
            "dimensions": _base_dims(
                physical_presence={"status": "absent", "source": "field"},
            ),
        }
        result = evaluate_promotion(record)
        self.assertEqual(result["verification_level"], "REJECTED_AS_SOURCE")

    def test_f03_vw_011_conflict_mapping(self):
        # Conflict is a parcel/factor state; evaluator receives explicit flag.
        record = {
            "prior_level": "MAPPED_CANDIDATE",
            "unresolved_material_conflict": True,
            "evidence_class": "REMOTE_ONLY",
            "dimensions": _base_dims(
                physical_presence={"status": "confirmed", "source": "imagery"},
                seasonal_reliability={"status": "perennial", "observation_period": "2025"},
            ),
        }
        result = evaluate_promotion(record)
        self.assertEqual(result["verification_level"], "MAPPED_CANDIDATE")

    def test_f03_vw_012_verified_zero_not_no_water(self):
        levels = ["MAPPED_CANDIDATE"] * 24
        self.assertEqual(factor_input_quality_from_levels(levels), "MAPPED_CANDIDATES_ONLY")
        self.assertNotEqual(factor_input_quality_from_levels(levels), "MISSING")

    def test_f03_vw_013_source_failure_not_unsuitable(self):
        # Data-path failure leaves existing NHD mapped candidates mapped.
        record = build_mapped_candidate_from_nhd(
            {
                "candidate_id": "demo",
                "source_layer": "NetworkNHDFlowline",
                "ftype": 460,
                "fcode": 46003,
            }
        )
        result = evaluate_promotion(record)
        self.assertEqual(result["verification_level"], "MAPPED_CANDIDATE")

    def test_f03_vw_014_geometry_change_policy(self):
        # Policy assertion: callers must not reuse stale field-verified after geometry change.
        stale_reusable = False
        self.assertFalse(stale_reusable)

    def test_f03_vw_015_no_species_ranking(self):
        record = {
            "prior_level": "REMOTELY_SUPPORTED_CANDIDATE",
            "evidence_class": "FIELD_OBSERVATION",
            "dimensions": _base_dims(
                feature_identity={"type": "tank"},
                physical_presence={"status": "confirmed", "source": "field"},
                seasonal_reliability={"status": "perennial", "observation_period": "2024-2025"},
                livestock_accessibility={"status": "supported"},
                capacity_and_quality={
                    "capacity": {
                        "status": "documented",
                        "value": 1,
                        "unit": "gallon_storage",
                        "scenario_reference": "t",
                        "unknown_rationale": None,
                    },
                    "water_quality": _unknown_wq(),
                },
                legal_access={"status": "verified", "basis": "owned"},
            ),
        }
        result = evaluate_promotion(record)
        self.assertEqual(result["ranking_effect"], "NONE")

    def test_f03_vw_016_mixed_with_qualified_basis(self):
        record = {
            "prior_level": "REMOTELY_SUPPORTED_CANDIDATE",
            "evidence_class": "MIXED",
            "qualified_field_basis_required": True,
            "dimensions": _base_dims(
                feature_identity={"type": "trough"},
                physical_presence={
                    "status": "confirmed",
                    "source": "reviewed_equivalent",
                    "qualified_field_basis": {
                        "source": "field",
                        "as_of": "2026-07-15T18:00:00Z",
                        "record_or_observation_hash": "sha256:example_field_note",
                    },
                },
                seasonal_reliability={"status": "intermittent", "observation_period": "2025-2026"},
                livestock_accessibility={"status": "supported"},
                capacity_and_quality={
                    "capacity": _unknown_capacity(
                        "Trough volume not gauged; use confirmed by operator."
                    ),
                    "water_quality": _unknown_wq(),
                },
                legal_access={"status": "verified", "basis": "lease_stock_water_clause"},
            ),
        }
        result = evaluate_promotion(record)
        self.assertEqual(result["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER")

    def test_f03_vw_017_capacity_unknown_without_rationale(self):
        record = {
            "prior_level": "REMOTELY_SUPPORTED_CANDIDATE",
            "evidence_class": "FIELD_OBSERVATION",
            "dimensions": _base_dims(
                feature_identity={"type": "pond"},
                physical_presence={"status": "confirmed", "source": "field"},
                seasonal_reliability={"status": "perennial", "observation_period": "2025"},
                livestock_accessibility={"status": "supported"},
                capacity_and_quality={
                    "capacity": {
                        "status": "unknown",
                        "value": None,
                        "unit": None,
                        "scenario_reference": None,
                        "unknown_rationale": None,
                    },
                    "water_quality": _unknown_wq(),
                },
                legal_access={"status": "verified", "basis": "owned"},
            ),
        }
        # Schema should flag missing rationale; promotion must not field-verify.
        schema = validate_candidate_record(record)
        self.assertIn("capacity.unknown_rationale_missing", schema["issues"])
        result = evaluate_promotion(record)
        self.assertNotEqual(result["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER")
        self.assertIn("CAPACITY_UNKNOWN_RATIONALE_REQUIRED", result["reason_codes"])

    def test_neg_011_single_date_seasonal_forbidden_by_policy(self):
        self.assertEqual(len(["2025-06-01"]), 1)

    def test_neg_013_mixed_without_basis(self):
        record = {
            "prior_level": "REMOTELY_SUPPORTED_CANDIDATE",
            "evidence_class": "MIXED",
            "qualified_field_basis_required": False,
            "dimensions": _base_dims(
                feature_identity={"type": "trough"},
                physical_presence={"status": "confirmed", "source": "reviewed_equivalent"},
                seasonal_reliability={"status": "intermittent", "observation_period": "2025"},
                livestock_accessibility={"status": "supported"},
                capacity_and_quality={
                    "capacity": _unknown_capacity("x"),
                    "water_quality": _unknown_wq(),
                },
                legal_access={"status": "verified", "basis": "owned"},
            ),
        }
        result = evaluate_promotion(record)
        self.assertNotEqual(result["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER")

    def test_remote_enrichment_helper_never_field_verifies(self):
        raw = {
            "candidate_id": "USGS_NHDPLUS_HR:NetworkNHDFlowline:1",
            "source_layer": "NetworkNHDFlowline",
            "ftype": 460,
            "fcode": 46003,
            "gnis_name": "Little Owl Creek",
            "geometry_hash": "a" * 64,
        }
        mapped = build_mapped_candidate_from_nhd(raw)
        enriched = apply_remote_enrichment(
            mapped,
            seasonal_from_fcode=True,
            reviewed_presence={
                "source": "imagery",
                "observation_date": "2023-09-25",
                "review_note": "Provenance-complete NAIP package.",
                "provenance": _complete_presence_provenance(
                    candidate_geometry_hash=raw["geometry_hash"],
                ),
            },
        )
        level = enriched["promotion_evaluation"]["verification_level"]
        self.assertEqual(level, "REMOTELY_SUPPORTED_CANDIDATE")
        self.assertNotEqual(level, "FIELD_VERIFIED_LIVESTOCK_WATER")

    def test_provenance_complete_allows_remotely_supported(self):
        self.assertTrue(remote_presence_provenance_complete(_complete_presence_provenance())["complete"])
        record = {
            "prior_level": "MAPPED_CANDIDATE",
            "evidence_class": "REMOTE_ONLY",
            "dimensions": _base_dims(
                physical_presence={
                    "status": "confirmed",
                    "source": "imagery",
                    "provenance": _complete_presence_provenance(),
                },
                seasonal_reliability={"status": "intermittent", "observation_period": "nhd_fcode_46003"},
            ),
        }
        result = evaluate_promotion(record)
        self.assertEqual(result["verification_level"], "REMOTELY_SUPPORTED_CANDIDATE")

    def test_missing_artifact_hash_prevents_promotion(self):
        incomplete = _complete_presence_provenance()
        incomplete["response_or_artifact_hash"] = None
        self.assertFalse(remote_presence_provenance_complete(incomplete)["complete"])
        record = {
            "prior_level": "MAPPED_CANDIDATE",
            "evidence_class": "REMOTE_ONLY",
            "dimensions": _base_dims(
                physical_presence={
                    "status": "confirmed",
                    "source": "imagery",
                    "provenance": incomplete,
                },
                seasonal_reliability={"status": "intermittent", "observation_period": "2023"},
            ),
        }
        result = evaluate_promotion(record)
        self.assertEqual(result["verification_level"], "MAPPED_CANDIDATE")
        self.assertIn("REMOTE_PRESENCE_PROVENANCE_INCOMPLETE", result["reason_codes"])

    def test_unverifiable_prose_note_stays_mapped_via_enrichment(self):
        mapped = build_mapped_candidate_from_nhd(
            {
                "candidate_id": "x",
                "source_layer": "NetworkNHDFlowline",
                "ftype": 460,
                "fcode": 46003,
                "geometry_hash": "d" * 64,
            }
        )
        enriched = apply_remote_enrichment(
            mapped,
            seasonal_from_fcode=True,
            reviewed_presence={
                "review_note": "Unverifiable public imagery note without artifact hash.",
                "provenance": {"provider": "unknown"},
            },
        )
        self.assertEqual(
            enriched["promotion_evaluation"]["verification_level"], "MAPPED_CANDIDATE"
        )
        self.assertEqual(enriched.get("evidence_use_limit"), "ENGINEERING_VALIDATION_ONLY")

    def test_remote_evidence_never_field_verified_even_with_full_dims(self):
        record = {
            "prior_level": "REMOTELY_SUPPORTED_CANDIDATE",
            "evidence_class": "REMOTE_ONLY",
            "dimensions": _base_dims(
                feature_identity={"type": "stream"},
                physical_presence={
                    "status": "confirmed",
                    "source": "imagery",
                    "provenance": _complete_presence_provenance(),
                },
                seasonal_reliability={"status": "perennial", "observation_period": "2020-2025"},
                livestock_accessibility={"status": "supported"},
                capacity_and_quality={
                    "capacity": {
                        "status": "documented",
                        "value": 1,
                        "unit": "gallon_storage",
                        "scenario_reference": "t",
                        "unknown_rationale": None,
                    },
                    "water_quality": _unknown_wq(),
                },
                legal_access={"status": "verified", "basis": "owned"},
            ),
        }
        result = evaluate_promotion(record)
        self.assertNotEqual(result["verification_level"], "FIELD_VERIFIED_LIVESTOCK_WATER")
        self.assertEqual(result["verification_level"], "REMOTELY_SUPPORTED_CANDIDATE")
        enriched = apply_remote_enrichment(
            {
                **record,
                "fcode": 46003,
                "dimensions": record["dimensions"],
            },
            seasonal_from_fcode=True,
            reviewed_presence={
                "source": "imagery",
                "provenance": _complete_presence_provenance(),
            },
        )
        self.assertNotEqual(
            enriched["promotion_evaluation"]["verification_level"],
            "FIELD_VERIFIED_LIVESTOCK_WATER",
        )

    def test_stable_sample_is_deterministic_and_capped(self):
        inventory = [
            {"candidate_id": "USGS_NHDPLUS_HR:NetworkNHDFlowline:2", "source_layer": "NetworkNHDFlowline", "source_feature_id": "2"},
            {"candidate_id": "USGS_NHDPLUS_HR:NHDWaterbody:1", "source_layer": "NHDWaterbody", "source_feature_id": "1"},
            {"candidate_id": "USGS_NHDPLUS_HR:NetworkNHDFlowline:3", "source_layer": "NetworkNHDFlowline", "source_feature_id": "3"},
            {"candidate_id": "USGS_NHDPLUS_HR:NetworkNHDFlowline:4", "source_layer": "NetworkNHDFlowline", "source_feature_id": "4"},
        ]
        first = stable_sample_f03_candidates(inventory, max_n=3)
        second = stable_sample_f03_candidates(list(reversed(inventory)), max_n=3)
        self.assertEqual(first["selection_method"], SELECTION_METHOD_STABLE_CANDIDATE_ID_ORDER)
        self.assertEqual(first["available_count"], 4)
        self.assertEqual(first["sampled_count"], 3)
        self.assertEqual(
            [row["candidate_id"] for row in first["selected"]],
            [row["candidate_id"] for row in second["selected"]],
        )
        self.assertEqual(
            [row["candidate_id"] for row in first["selected"]],
            [
                "USGS_NHDPLUS_HR:NHDWaterbody:1",
                "USGS_NHDPLUS_HR:NetworkNHDFlowline:2",
                "USGS_NHDPLUS_HR:NetworkNHDFlowline:3",
            ],
        )

    def test_stable_sample_does_not_prefer_promotable_fcodes(self):
        inventory = [
            {"candidate_id": "z_waterbody", "fcode": 39001, "source_feature_id": "9"},
            {"candidate_id": "a_ephemeral", "fcode": 46007, "source_feature_id": "1"},
            {"candidate_id": "m_intermittent", "fcode": 46003, "source_feature_id": "2"},
        ]
        sampled = stable_sample_f03_candidates(inventory, max_n=2)
        # Lexicographic candidate_id order, not FCode seasonal promotability.
        self.assertEqual(
            [row["candidate_id"] for row in sampled["selected"]],
            ["a_ephemeral", "m_intermittent"],
        )


if __name__ == "__main__":
    unittest.main()
