#!/usr/bin/env python3
"""Regenerate the Nambe Cattle Operating Profile fixture. Run explicitly; tests must not write it."""

from __future__ import annotations

import json
from pathlib import Path

from rangematch.livestock_operating_profile import project_livestock_operating_profile

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "test-data/advisor/nambe/nambe_advisor_report_bundle.json"
OUT = ROOT / "test-data/advisor/nambe/nambe_cattle_operating_profile.json"


def main() -> None:
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
    profile = project_livestock_operating_profile(
        bundle["generic_evidence_packet"],
        bundle["unified_output"],
        species_lens="CATTLE",
    )
    OUT.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} profile_hash={profile['profile_hash']}")


if __name__ == "__main__":
    main()
