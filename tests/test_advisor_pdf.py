"""PDF view model and renderer: Validator-gated, no CPER silent swap."""

from __future__ import annotations

import unittest

from rangematch.advisor_brief import generate_deterministic_brief
from rangematch.advisor_generic_packet import project_generic_buyer_evidence_packet
from rangematch.advisor_pdf import project_buyer_brief_pdf_model, render_three_page_pdf
from rangematch.f06_derivation import derive_f06_from_geometry
from rangematch.unified_output import project_unified_output
from rangematch.engine import evaluate_land_profile


SQUARE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-105.26, 39.62], [-105.25, 39.62], [-105.25, 39.63], [-105.26, 39.63], [-105.26, 39.62]]
                ],
            },
        }
    ],
}


def _generic_run() -> dict:
    geometry_hash = "a" * 64
    f06 = derive_f06_from_geometry(
        SQUARE,
        geometry_hash=geometry_hash,
        geometry_reference="memory://nambe-test",
        geometry_id="NAMBE_TEST",
        source_crs="EPSG:4326",
    )
    profile = {
        "land_profile_id": "ADVISOR_GENERIC_PDF",
        "version": "0.2.1",
        "geometry_id": "NAMBE_TEST",
        "geometry_reference": "memory://nambe-test",
        "geometry_hash": geometry_hash,
        "supported_use": "BUYER_DILIGENCE",
        "factors": {"F06_PARCEL_CONFIGURATION": f06},
    }
    match = evaluate_land_profile(profile)
    unified = project_unified_output(
        profile,
        match,
        mode="DISCOVERY",
        intended_operation=None,
        planned_actions=[],
        run_id="pdf_test",
        geometry=SQUARE,
        mireye_context=[],
    )
    packet = project_generic_buyer_evidence_packet(
        unified,
        listing_claims=[],
        confirmation_status="CONFIRMED",
        unified_output_ref="memory://pdf/unified_output",
    )
    brief = generate_deterministic_brief(
        packet,
        unified_output=unified,
        mireye_live={
            "lookup": {"ok": True, "endpoint": "/v1/lookup"},
            "contexts": {
                "PROPERTY_DILIGENCE_CONTEXT": {"status": "SUCCEEDED"},
                "POINT_LAND_CONTEXT": {"status": "SUCCEEDED"},
                "POINT_HAZARD_CONTEXT": {"status": "SUCCEEDED"},
            },
        },
    )
    return {
        "run_id": "advisor_pdf_test",
        "address": "4213 Nambe Road, Indian Hills, CO 80454",
        "packet_hash": brief["packet_hash"],
        "parcel_geometry_confirmed": True,
        "packet": packet,
        "brief": brief,
        "mireye_live": {
            "lookup": {"ok": True},
            "contexts": {
                "PROPERTY_DILIGENCE_CONTEXT": {"status": "SUCCEEDED"},
                "POINT_LAND_CONTEXT": {"status": "SUCCEEDED"},
                "POINT_HAZARD_CONTEXT": {"status": "SUCCEEDED"},
            },
        },
        "buyer_explanation": None,
    }


class AdvisorPdfTests(unittest.TestCase):
    def test_no_listing_page_two_is_public_evidence(self) -> None:
        run = _generic_run()
        self.assertEqual(run["brief"]["page_two_actions"]["page_mode"], "PUBLIC_EVIDENCE")
        self.assertIn("transaction documents", run["brief"]["page_two_actions"]["headline"])
        self.assertFalse(run["packet"]["listing_claims"])
        view = project_buyer_brief_pdf_model(run)
        self.assertEqual(view["page_two"]["mode"], "PUBLIC_EVIDENCE")
        self.assertIn("Mireye recognized", view["page_one"]["mireye_anchor"])
        self.assertTrue(view["page_three"]["mireye_provenance"])
        self.assertEqual(
            [row["label"] for row in view["page_three"]["mireye_provenance"]],
            [
                "Location recognition",
                "Property context",
                "Land context at centroid",
                "Hazard context at centroid",
            ],
        )
        self.assertTrue(
            all(row["status"] == "SUCCEEDED" for row in view["page_three"]["mireye_provenance"])
        )
        blob = repr(view).lower()
        self.assertNotIn("engineering_test_geometry_cper", blob)
        self.assertNotIn("excellent year-round water", blob)

    def test_renderer_emits_pdf_bytes(self) -> None:
        run = _generic_run()
        view = project_buyer_brief_pdf_model(run)
        payload = render_three_page_pdf(view)
        self.assertTrue(payload.startswith(b"%PDF"))
        self.assertGreater(len(payload), 800)

    def test_ranch_narrative_pdf_is_three_pages_without_unknown_cards(self) -> None:
        run = _generic_run()
        run["buyer_explanation"] = {
            "source": "STRUCTURED_FIXTURE",
            "validation_status": "PASSED",
            "sections": {
                "recommendation": "Request the access paper first.",
                "why": "Read this as a cattle diligence object, not a scored ranch.",
                "listing_jumps": "Feed, water investigation, and movement context set the next job.",
                "do_now": "Request the access paper first.",
                "if_changes": "If the entrance basis holds, schedule a water-inventory visit.",
                "professional_reminders": "Mapped water is a lead, not a drinker.",
            },
            "ranch_narrative": {
                "operating_thesis": "This tract already has a preliminary cattle operating picture from public evidence. Water investigation is the largest operating theme; access documents remain the first spend.",
                "ranch_reading": "Read this as a cattle diligence object, not a scored ranch.",
                "how_livestock_would_use_it": "Feed context, water investigation leads, and movement context jointly set a water-inventory visit after access paper.",
                "attention_pivot": {
                    "largest_operating_theme": "Water investigation is the largest cattle-operating theme on this tract.",
                    "first_action_id": "ACTION_ACCESS_DOCUMENTS",
                    "why_theme_and_action_differ": "Access documents still come first because they are cheaper than travel.",
                },
                "conditional_path": {
                    "if_access_holds": "If the entrance basis holds, schedule a water-inventory visit.",
                    "if_access_fails": "If the entrance basis cannot be shown, pause travel.",
                },
                "client_summary": "Request the access paper first. If it holds, use the trip for a water inventory.",
            },
            "narrative": {},
        }
        view = project_buyer_brief_pdf_model(run)
        self.assertTrue(view["ranch_narrative"])
        payload = render_three_page_pdf(view)
        self.assertTrue(payload.startswith(b"%PDF"))
        self.assertIn(b"/Count 3", payload)
        self.assertGreater(len(payload), 800)

    def test_brief_style_mireye_rows_do_not_render_as_none(self) -> None:
        run = _generic_run()
        run["brief"]["page_three_kitchen"]["mireye_provenance"] = [
            {
                "source_id": "MIREYE_LOOKUP",
                "role": "PARCEL_ENTRY",
                "ok": True,
                "canonical_for_parcel_facts": False,
                "spatial_meaning": "address_or_location_recognition",
            }
        ]
        view = project_buyer_brief_pdf_model(run)
        self.assertEqual(view["page_three"]["mireye_provenance"][0]["label"], "Location recognition")
        self.assertEqual(view["page_three"]["mireye_provenance"][0]["status"], "SUCCEEDED")


if __name__ == "__main__":
    unittest.main()
