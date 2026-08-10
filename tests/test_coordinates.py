"""Unit tests for U.S. query-point validation (COORDINATE parcel entry)."""

from __future__ import annotations

import unittest

from rangematch.coordinates import (
    CoordinateValidationError,
    format_coord_input,
    parse_lat_lng_text,
    validate_us_query_point,
)


class CoordinateValidationTests(unittest.TestCase):
    def test_valid_us_point(self):
        out = validate_us_query_point(40.495, -104.895)
        self.assertTrue(out["within_us_envelope"])
        self.assertFalse(out["swap_detected"])
        self.assertIn("lookup point only", out["limitations"][0].lower())

    def test_swap_detected(self):
        with self.assertRaises(CoordinateValidationError) as ctx:
            validate_us_query_point(-104.895, 40.495)
        self.assertEqual(ctx.exception.code, "COORDINATES_APPEAR_SWAPPED")

    def test_outside_us(self):
        with self.assertRaises(CoordinateValidationError) as ctx:
            validate_us_query_point(51.5, -0.12)
        self.assertEqual(ctx.exception.code, "COORDINATES_OUTSIDE_US")

    def test_invalid_range(self):
        with self.assertRaises(CoordinateValidationError) as ctx:
            validate_us_query_point(200.0, -104.0)
        self.assertEqual(ctx.exception.code, "INVALID_COORDINATE_RANGE")

    def test_parse_lat_lng_text(self):
        lat, lng = parse_lat_lng_text("40.495, -104.895")
        self.assertAlmostEqual(lat, 40.495)
        self.assertAlmostEqual(lng, -104.895)
        self.assertEqual(format_coord_input(lat, lng), "40.495,-104.895")
        with self.assertRaises(CoordinateValidationError) as ctx:
            parse_lat_lng_text("not-a-coord")
        self.assertEqual(ctx.exception.code, "INVALID_COORDINATE_FORMAT")


if __name__ == "__main__":
    unittest.main()
