"""Shared Mireye lookup sample payloads for Advisor tests.

Import as ``from mireye_lookup_samples import UNIQUE_WITH_POLYGON`` when
``tests`` is on ``PYTHONPATH`` (see ``[tool.pytest.ini_options].pythonpath``).
Do not import sibling test modules (e.g. ``tests.test_advisor_parcel_gate``);
that breaks bare ``pytest`` collection when only ``src`` is on the path.
"""

from __future__ import annotations

UNIQUE_WITH_POLYGON = {
    "disposition": "resolved",
    "confidence": 0.92,
    "normalized_address": "300 Mireye Ranch Rd, Weld County, CO 80701",
    "accuracy_type": "rooftop",
    "accuracy": 1.0,
    "match_type": "address",
    "fetched_at": "2026-08-08T16:00:00+00:00",
    "request_id": "advisor_gate_unique",
    "lat": 40.495,
    "lng": -104.895,
    "resolved_location": {"lat": 40.495, "lng": -104.895, "source": "geocode"},
    "parcel_unavailable": False,
    "parcel": {
        "parcel_id": "MIREYE-GATE-001",
        "apn": "R1234567",
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
    },
    "fields": {},
    "partial_failures": [],
}
