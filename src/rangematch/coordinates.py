"""U.S. query-point validation for parcel resolution (competition Demo).

Coordinates are parcel *lookup* points only — never F01–F08 geometry,
never auto-buffered circles. Uses Mireye US envelope bounds.
"""

from __future__ import annotations

from typing import Any

# Mireye Field Catalog us_envelope (v0.14.0)
US_LAT_MIN = 18.0
US_LAT_MAX = 72.0
US_LNG_MIN = -180.0
US_LNG_MAX = -65.0


class CoordinateValidationError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}:{message}")


def _in_us(lat: float, lng: float) -> bool:
    return US_LAT_MIN <= lat <= US_LAT_MAX and US_LNG_MIN <= lng <= US_LNG_MAX


def parse_lat_lng_text(text: str) -> tuple[float, float]:
    raw = (text or "").strip()
    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    if len(parts) != 2:
        raise CoordinateValidationError(
            "INVALID_COORDINATE_FORMAT",
            "coordinates must be 'lat,lng' (decimal degrees)",
        )
    try:
        lat = float(parts[0])
        lng = float(parts[1])
    except ValueError as exc:
        raise CoordinateValidationError(
            "INVALID_COORDINATE_FORMAT",
            "coordinates must be numeric lat,lng",
        ) from exc
    return lat, lng


def validate_us_query_point(lat: float, lng: float) -> dict[str, Any]:
    """Validate a query point for COORDINATE parcel lookup.

    Detects likely lat/lng swap when the swapped pair falls in the US envelope
    but the given pair does not. Absolute degree bounds are checked after swap
    detection so classic lng,lat mistakes (e.g. -104.9, 40.5) surface as swap.
    """
    if not (-180.0 <= lat <= 180.0) or not (-180.0 <= lng <= 180.0):
        raise CoordinateValidationError(
            "INVALID_COORDINATE_RANGE",
            "coordinates must be decimal degrees within [-180,180]",
        )

    if _in_us(lat, lng):
        return {
            "latitude": lat,
            "longitude": lng,
            "within_us_envelope": True,
            "swap_detected": False,
            "limitations": [
                "Coordinates are a parcel lookup point only — not a parcel boundary.",
                "Do not treat the pin as F01–F08 geometry; confirm a returned polygon.",
            ],
        }

    # Classic swap: user entered lng,lat
    if _in_us(lng, lat):
        raise CoordinateValidationError(
            "COORDINATES_APPEAR_SWAPPED",
            "values look like longitude,latitude — enter latitude first (lat,lng)",
        )

    if not (-90.0 <= lat <= 90.0):
        raise CoordinateValidationError(
            "INVALID_COORDINATE_RANGE",
            "latitude must be [-90,90] and longitude [-180,180]",
        )

    raise CoordinateValidationError(
        "COORDINATES_OUTSIDE_US",
        f"point outside U.S. envelope "
        f"(lat {US_LAT_MIN}–{US_LAT_MAX}, lng {US_LNG_MIN}–{US_LNG_MAX})",
    )


def format_coord_input(lat: float, lng: float) -> str:
    return f"{lat},{lng}"
