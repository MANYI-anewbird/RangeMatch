"""Tests for deterministic Buyer Report validator."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from rangematch.buyer_report import build_fixture_buyer_report
from rangematch.report_validator import validate_buyer_report


ROOT = Path(__file__).resolve().parents[1]
UO_PATH = ROOT / "test-data" / "land-profiles" / "unified_output_cper_001.json"


class ReportValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.uo = json.loads(UO_PATH.read_text(encoding="utf-8"))
        self.good = build_fixture_buyer_report(
            self.uo,
            mode="GOAL_DIRECTED",
            intended_operation="COW_CALF_OPERATION",
        )

    def test_good_report_passes(self):
        out = validate_buyer_report(self.good, unified_output=self.uo)
        self.assertEqual(out["validation_status"], "PASSED", out["validation_violations"])
        self.assertTrue(out["report_provenance"]["displayable"])

    def test_rejects_decision_label_change(self):
        bad = deepcopy(self.good)
        bad["operation_comparison"]["findings"] = [
            "Cow-Calf decision_label is ADVANCE.",
            "Sheep decision_label is ADVANCE.",
        ]
        # Also corrupt claim ledger
        for claim in bad["claim_ledger"]:
            if claim.get("claim_type") == "ENGINE_DECISION":
                claim["text"] = claim["text"].replace("HOLD", "ADVANCE")
        out = validate_buyer_report(bad, unified_output=self.uo)
        self.assertEqual(out["validation_status"], "FAILED")
        codes = {v["code"] for v in out["validation_violations"]}
        self.assertTrue(
            "AUTHORITY_DECISION_MISSING" in codes or "AUTHORITY_DECISION_MISMATCH" in codes,
            codes,
        )

    def test_rejects_carrying_capacity(self):
        bad = deepcopy(self.good)
        bad["claim_ledger"].append(
            {
                "claim_id": "C_BAD",
                "text": "Estimated carrying capacity is 40 AUMs.",
                "claim_type": "FACT",
                "evidence_refs": [],
                "numeric_refs": [],
                "certainty": "INFERRED",
                "operation_scope": None,
            }
        )
        out = validate_buyer_report(bad, unified_output=self.uo)
        self.assertEqual(out["validation_status"], "FAILED")
        self.assertTrue(
            any(v["code"] == "PROHIBITED_CARRYING_CAPACITY" for v in out["validation_violations"])
        )

    def test_rejects_hold_as_unsuitable(self):
        bad = deepcopy(self.good)
        bad["operation_comparison"]["findings"].append(
            "HOLD means this parcel is unsuitable for livestock."
        )
        out = validate_buyer_report(bad, unified_output=self.uo)
        self.assertEqual(out["validation_status"], "FAILED")
        self.assertTrue(
            any(v["code"] == "PROHIBITED_HOLD_AS_UNSUITABLE" for v in out["validation_violations"])
        )

    def test_rejects_omitted_material_unknown(self):
        bad = deepcopy(self.good)
        bad["key_unknowns"]["findings"] = ["Nothing important is unknown."]
        bad["key_unknowns"]["summary"] = "None"
        # Strip unknown mentions from claim ledger texts too
        bad["claim_ledger"] = [
            c
            for c in bad["claim_ledger"]
            if c.get("claim_type") != "UNKNOWN"
            and "F02" not in c.get("text", "")
            and "water" not in c.get("text", "").lower()
            and "legal access" not in c.get("text", "").lower()
            and "woody" not in c.get("text", "").lower()
        ]
        # Also scrub other sections that might mention F02/water/access
        for key in (
            "executive_summary",
            "land_and_resources",
            "diligence_plan",
            "operation_comparison",
            "methodology_and_limitations",
            "property",
            "resilience_and_hazards",
        ):
            sec = bad[key]
            sec["findings"] = [
                f
                for f in sec["findings"]
                if not any(
                    x in f.lower()
                    for x in (
                        "f02",
                        "herbaceous",
                        "forage",
                        "water",
                        "legal access",
                        "entrance",
                        "woody",
                        "shrub",
                        "browse",
                        "f03",
                        "f07",
                        "f08",
                    )
                )
            ]
            if "hold" in " ".join(sec["findings"]).lower():
                # keep HOLD explanation for other checks; unknowns are the focus
                pass
        out = validate_buyer_report(bad, unified_output=self.uo)
        self.assertEqual(out["validation_status"], "FAILED")
        self.assertTrue(
            any(v["code"] == "UNKNOWN_OMITTED" for v in out["validation_violations"]),
            out["validation_violations"],
        )

    def test_rejects_fabricated_url(self):
        bad = deepcopy(self.good)
        bad["claim_ledger"].append(
            {
                "claim_id": "C_URL",
                "text": "See https://example.invalid/secret-source for proof.",
                "claim_type": "CONTEXT",
                "evidence_refs": [],
                "numeric_refs": [],
                "certainty": "INFERRED",
                "operation_scope": None,
            }
        )
        out = validate_buyer_report(bad, unified_output=self.uo)
        self.assertEqual(out["validation_status"], "FAILED")
        self.assertTrue(any(v["code"] == "FABRICATED_URL" for v in out["validation_violations"]))

    def test_rejects_ungrounded_numeric(self):
        bad = deepcopy(self.good)
        bad["claim_ledger"].append(
            {
                "claim_id": "C_NUM",
                "text": "The parcel is exactly 9876.5 acres of irrigable land.",
                "claim_type": "FACT",
                "evidence_refs": [],
                "numeric_refs": [],
                "certainty": "INFERRED",
                "operation_scope": None,
            }
        )
        out = validate_buyer_report(bad, unified_output=self.uo)
        self.assertEqual(out["validation_status"], "FAILED")
        self.assertTrue(
            any(v["code"] == "NUMERIC_UNGROUNDED" for v in out["validation_violations"])
        )

    def test_rejects_fabricated_acres_in_section_finding(self):
        bad = deepcopy(self.good)
        bad["land_and_resources"]["findings"].append(
            "This parcel has 9999 acres."
        )
        out = validate_buyer_report(bad, unified_output=self.uo)
        self.assertEqual(out["validation_status"], "FAILED")
        self.assertFalse(out["report_provenance"]["displayable"])
        self.assertTrue(
            any(v["code"] == "NUMERIC_UNGROUNDED" for v in out["validation_violations"]),
            out["validation_violations"],
        )

    def test_rejects_invented_evidence_ref_declared_by_report(self):
        fabricated = "land_fact:F99_FAKE:VAR_INVENTED_ACRES"
        bad = deepcopy(self.good)
        bad["evidence_references"].append(
            {
                "ref_id": fabricated,
                "kind": "LAND_FACT",
                "label": "Invented acres",
                "factor_id": "F99_FAKE",
                "point_context": False,
            }
        )
        bad["claim_ledger"].append(
            {
                "claim_id": "C_FAKE_REF",
                "text": "Invented evidence supports a large irrigable area.",
                "claim_type": "FACT",
                "evidence_refs": [fabricated],
                "numeric_refs": [],
                "certainty": "INFERRED",
                "operation_scope": None,
            }
        )
        out = validate_buyer_report(bad, unified_output=self.uo)
        self.assertEqual(out["validation_status"], "FAILED")
        codes = {v["code"] for v in out["validation_violations"]}
        self.assertIn("FABRICATED_EVIDENCE_REF", codes, codes)
        self.assertIn("EVIDENCE_REF_UNRESOLVED", codes, codes)

    def test_rejects_unsupported_carrying_capacity_number(self):
        bad = deepcopy(self.good)
        bad["land_and_resources"]["summary"] = (
            "Estimated carrying capacity is 120 head on this parcel."
        )
        out = validate_buyer_report(bad, unified_output=self.uo)
        self.assertEqual(out["validation_status"], "FAILED")
        codes = {v["code"] for v in out["validation_violations"]}
        self.assertTrue(
            "PROHIBITED_CARRYING_CAPACITY" in codes or "NUMERIC_UNGROUNDED" in codes,
            codes,
        )

    def test_accepts_valid_rounding_via_numeric_refs(self):
        elev_ref = "land_fact:F01_TOPOGRAPHY:VAR_F01_ELEVATION_MEDIAN_M"
        good = deepcopy(self.good)
        good["claim_ledger"].append(
            {
                "claim_id": "C_ELEV_ROUND",
                "text": "Median elevation is about 1654 m.",
                "claim_type": "FACT",
                "evidence_refs": [elev_ref],
                "numeric_refs": [elev_ref],
                "certainty": "GROUNDED",
                "operation_scope": None,
            }
        )
        out = validate_buyer_report(good, unified_output=self.uo)
        self.assertEqual(out["validation_status"], "PASSED", out["validation_violations"])
        self.assertTrue(out["report_provenance"]["displayable"])

    def test_accepts_fraction_to_percent_conversion(self):
        shrub_ref = (
            "land_fact:F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE:"
            "VAR_F08_SHRUB_COVER_FRACTION"
        )
        good = deepcopy(self.good)
        good["claim_ledger"].append(
            {
                "claim_id": "C_SHRUB_PCT",
                "text": "Modeled shrub cover is about 6.7 percent.",
                "claim_type": "FACT",
                "evidence_refs": [shrub_ref],
                "numeric_refs": [shrub_ref],
                "certainty": "GROUNDED",
                "operation_scope": None,
            }
        )
        out = validate_buyer_report(good, unified_output=self.uo)
        self.assertEqual(out["validation_status"], "PASSED", out["validation_violations"])

    def test_valid_engine_labels_and_unknowns_remain_displayable(self):
        out = validate_buyer_report(self.good, unified_output=self.uo)
        self.assertEqual(out["validation_status"], "PASSED", out["validation_violations"])
        text = "\n".join(
            [
                str((out.get("operation_comparison") or {}).get("summary") or ""),
                *[
                    str(x)
                    for x in (
                        (out.get("operation_comparison") or {}).get("findings") or []
                    )
                ],
                str((out.get("key_unknowns") or {}).get("summary") or ""),
                *[
                    str(x)
                    for x in ((out.get("key_unknowns") or {}).get("findings") or [])
                ],
            ]
        )
        self.assertIn("HOLD", text)
        self.assertTrue(
            any(c.get("claim_type") == "UNKNOWN" for c in out.get("claim_ledger") or [])
        )
        self.assertRegex(text, r"F02|herbaceous|forage|water|access|woody|shrub")


if __name__ == "__main__":
    unittest.main()
