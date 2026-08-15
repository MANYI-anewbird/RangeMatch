"""Live-adapter collect budgets: timeout does not invent facts or block a packet."""

from __future__ import annotations

import time
import unittest

from rangematch.advisor_generic_collect import (
    ADAPTER_TIMEOUT_REASON,
    DEPENDENCY_MISSING_REASON,
    collect_live_advisor_factors,
    set_advisor_collect_timeouts_for_tests,
)


HASH = "c" * 64
GEOMETRY = {
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


class AdvisorGenericCollectTimeoutTests(unittest.TestCase):
    def tearDown(self) -> None:
        set_advisor_collect_timeouts_for_tests()

    def test_slow_adapter_times_out_and_others_continue(self) -> None:
        progress: list[str] = []

        def hang() -> dict:
            time.sleep(2)
            return {"should_not": "land"}

        def fast() -> dict:
            return {"mapped_candidate_count": 0, "candidate_inventory": []}

        collected = collect_live_advisor_factors(
            geometry=GEOMETRY,
            geometry_id="TEST_TIMEOUT",
            geometry_hash=HASH,
            geometry_reference="memory://timeout",
            adapter_timeout_s=0.15,
            total_budget_s=1.0,
            on_progress=lambda row: progress.append(
                f"{row['factor_id']}:{row['status']}"
            ),
            runners={
                "F01_TOPOGRAPHY": hang,
                "F03_LIVESTOCK_WATER": fast,
            },
        )
        self.assertEqual(
            collected["factor_errors"]["F01_TOPOGRAPHY"], ADAPTER_TIMEOUT_REASON
        )
        self.assertNotIn("F01_TOPOGRAPHY", collected["computed_factors"])
        self.assertIn("F03_LIVESTOCK_WATER", collected["computed_factors"])
        self.assertTrue(
            any("F01 timed out — continuing with remaining evidence" in note for note in collected["progress_notes"])
        )
        self.assertTrue(any(item.startswith("F01_TOPOGRAPHY:RUNNING") for item in progress))

    def test_budget_exhaustion_skips_remaining_without_waiting(self) -> None:
        collected = collect_live_advisor_factors(
            geometry=GEOMETRY,
            geometry_id="TEST_BUDGET",
            geometry_hash=HASH,
            geometry_reference="memory://budget",
            adapter_timeout_s=0.2,
            total_budget_s=0.0,
            runners={
                "F01_TOPOGRAPHY": lambda: {"summary": {"slope_median_degrees": 2.0}},
                "F07_ROAD_AND_PHYSICAL_ACCESS": lambda: time.sleep(1),
            },
        )
        self.assertIn(
            collected["factor_errors"]["F01_TOPOGRAPHY"],
            {"BUDGET_EXHAUSTED", ADAPTER_TIMEOUT_REASON},
        )
        self.assertEqual(collected["computed_factors"], {})

    def test_missing_netcdf4_marks_f05_and_keeps_other_adapters(self) -> None:
        def missing_netcdf4() -> dict:
            raise ModuleNotFoundError(name="netCDF4")

        def fast_f03() -> dict:
            return {"mapped_candidate_count": 0, "candidate_inventory": []}

        collected = collect_live_advisor_factors(
            geometry=GEOMETRY,
            geometry_id="TEST_NETCDF",
            geometry_hash=HASH,
            geometry_reference="memory://netcdf",
            adapter_timeout_s=1.0,
            total_budget_s=2.0,
            runners={
                "F05_CLIMATE_DROUGHT_EXPOSURE": missing_netcdf4,
                "F03_LIVESTOCK_WATER": fast_f03,
            },
        )
        self.assertEqual(
            collected["factor_errors"]["F05_CLIMATE_DROUGHT_EXPOSURE"],
            f"{DEPENDENCY_MISSING_REASON}:netCDF4",
        )
        self.assertNotIn("F05_CLIMATE_DROUGHT_EXPOSURE", collected["computed_factors"])
        self.assertIn("F03_LIVESTOCK_WATER", collected["computed_factors"])
        self.assertTrue(
            any("missing dependency netCDF4" in note for note in collected["progress_notes"])
        )

    def test_all_live_adapters_unavailable_returns_no_invented_factors(self) -> None:
        def boom() -> dict:
            raise ModuleNotFoundError(name="rasterio")

        collected = collect_live_advisor_factors(
            geometry=GEOMETRY,
            geometry_id="TEST_ALL_MISSING",
            geometry_hash=HASH,
            geometry_reference="memory://all_missing",
            adapter_timeout_s=1.0,
            total_budget_s=2.0,
            runners={
                "F01_TOPOGRAPHY": boom,
                "F02_HERBACEOUS_RESOURCE": boom,
                "F03_LIVESTOCK_WATER": boom,
                "F07_ROAD_AND_PHYSICAL_ACCESS": boom,
            },
        )
        self.assertEqual(collected["computed_factors"], {})
        self.assertTrue(
            all(
                str(reason).startswith(DEPENDENCY_MISSING_REASON)
                for reason in collected["factor_errors"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
