"""Place-input cleanup: language only. Mireye still locates the parcel.

Clean US street addresses and lat,lng go straight to Mireye.
Messy language may call an LLM to structure the query.
The LLM must not invent coordinates, polygons, or a confirmed parcel.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from rangematch.coordinates import (
    CoordinateValidationError,
    format_coord_input,
    parse_lat_lng_text,
    validate_us_query_point,
)

PLACE_PROMPT_VERSION = "RANGEMATCH_PLACE_NORMALIZER@0.1.0"
ASK_FOR_MORE = (
    "Add a U.S. state, ZIP code, or lat,lng so Mireye can look up a parcel. "
    "RangeMatch will not guess a coordinate or invent a boundary."
)

PLACE_SYSTEM_PROMPT = """You only tidy a place string for a U.S. parcel lookup.

Return JSON with:
  input_type: ADDRESS | COORDINATE | NEEDS_MORE
  normalized_address: string or null
  latitude: number or null
  longitude: number or null
  needs_user: string or null

Rules:
- Do not invent latitude or longitude. COORDINATE only if those numbers are already in the input.
- Do not invent a street number, city, or parcel the user did not name.
- Do not return geometry, APN, parcel_id, or candidates.
- Do not claim a parcel is confirmed.
- If the place is too vague, input_type=NEEDS_MORE and ask for state, ZIP, or lat,lng.
- ADDRESS: expand Rd/St abbreviations and add a state if the user already named it. latitude and longitude must be null.
"""

PLACE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "input_type",
        "normalized_address",
        "latitude",
        "longitude",
        "needs_user",
    ],
    "properties": {
        "input_type": {"type": "string", "enum": ["ADDRESS", "COORDINATE", "NEEDS_MORE"]},
        "normalized_address": {"type": ["string", "null"]},
        "latitude": {"type": ["number", "null"]},
        "longitude": {"type": ["number", "null"]},
        "needs_user": {"type": ["string", "null"]},
    },
}

_STREET_SUFFIX = re.compile(
    r"\b(road|rd|street|st|avenue|ave|lane|ln|drive|dr|court|ct|circle|cir|"
    r"boulevard|blvd|highway|hwy|way|trail|trl|place|pl|parkway|pkwy|"
    r"county\s+road|cr|fm|ranch\s+rd)\b",
    re.I,
)
_STATE_ABBR = re.compile(
    r"\b(AL|AK|AZ|AR|CA|CO|CT|DC|DE|FL|GA|HI|IA|ID|IL|IN|KS|KY|LA|MA|MD|ME|"
    r"MI|MN|MO|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|"
    r"VA|VT|WA|WI|WV|WY)\b",
)
_STATE_NAME = re.compile(
    r"\b(alabama|alaska|arizona|arkansas|california|colorado|connecticut|"
    r"delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|"
    r"kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|"
    r"mississippi|missouri|montana|nebraska|nevada|new\s+hampshire|"
    r"new\s+jersey|new\s+mexico|new\s+york|north\s+carolina|north\s+dakota|"
    r"ohio|oklahoma|oregon|pennsylvania|rhode\s+island|south\s+carolina|"
    r"south\s+dakota|tennessee|texas|utah|vermont|virginia|washington|"
    r"west\s+virginia|wisconsin|wyoming)\b",
    re.I,
)
_ZIP = re.compile(r"\b\d{5}(?:-\d{4})?\b")
_HOUSE_NUMBER = re.compile(r"^\s*\d+[A-Za-z]?(?:\s|$)")
_MESSY_CUE = re.compile(
    r"\b(near|around|about|somewhere|kinda|maybe|off\s+of|by\s+the|"
    r"that\s+ranch|the\s+ranch|i\s+think|look(?:ing)?\s+at|where\s+is|"
    r"find|what(?:'s| is))\b",
    re.I,
)
_STOP = frozenset(
    {
        "near",
        "around",
        "about",
        "somewhere",
        "the",
        "a",
        "an",
        "of",
        "off",
        "by",
        "at",
        "in",
        "on",
        "to",
        "and",
        "ranch",
        "property",
        "land",
        "place",
        "tract",
        "parcel",
        "that",
        "this",
        "maybe",
        "kinda",
        "please",
        "find",
        "looking",
    }
)
_STATE_ALIASES = {
    "co": "colorado",
    "colorado": "co",
    "tx": "texas",
    "texas": "tx",
    "nm": "newmexico",
    "wy": "wyoming",
    "wyoming": "wy",
    "ok": "oklahoma",
    "oklahoma": "ok",
    "ks": "kansas",
    "kansas": "ks",
    "ne": "nebraska",
    "nebraska": "ne",
    "mt": "montana",
    "montana": "mt",
    "sd": "southdakota",
    "nd": "northdakota",
    "az": "arizona",
    "arizona": "az",
    "ut": "utah",
    "utah": "ut",
    "nv": "nevada",
    "nevada": "nv",
    "ca": "california",
    "california": "ca",
    "or": "oregon",
    "oregon": "or",
    "wa": "washington",
    "washington": "wa",
    "id": "idaho",
    "idaho": "id",
}

_PLACE_FN: Callable[..., dict[str, Any]] | None = None


def set_advisor_place_normalize_for_tests(fn: Callable[..., dict[str, Any]] | None) -> None:
    global _PLACE_FN
    _PLACE_FN = fn


def classify_place_input(place: str) -> dict[str, Any]:
    text = (place or "").strip()
    try:
        lat, lng = parse_lat_lng_text(text)
        validated = validate_us_query_point(lat, lng)
    except CoordinateValidationError:
        return {
            "kind": "address",
            "input": text,
            "input_kind": "ADDRESS",
            "latitude": None,
            "longitude": None,
        }
    return {
        "kind": "coord",
        "input": format_coord_input(validated["latitude"], validated["longitude"]),
        "input_kind": "COORDINATE",
        "latitude": validated["latitude"],
        "longitude": validated["longitude"],
    }


def place_needs_llm_cleanup(place: str) -> bool:
    """True only for messy language. Clean streets and coords skip the LLM."""
    text = (place or "").strip()
    if not text:
        return False
    classified = classify_place_input(text)
    if classified["input_kind"] == "COORDINATE":
        return False
    if _MESSY_CUE.search(text) or "?" in text:
        return True
    has_number = bool(_HOUSE_NUMBER.search(text))
    has_suffix = bool(_STREET_SUFFIX.search(text))
    has_state = bool(_STATE_ABBR.search(text) or _STATE_NAME.search(text))
    has_zip = bool(_ZIP.search(text))
    if has_number and has_suffix:
        return False
    if (has_state or has_zip) and (has_suffix or has_number or "," in text):
        return False
    if has_state or has_zip:
        return False
    return True


def _tokens(text: str) -> set[str]:
    parts = re.findall(r"[a-z0-9]+", (text or "").lower())
    out: set[str] = set()
    for part in parts:
        if part in _STOP or len(part) < 2:
            continue
        out.add(part)
        alias = _STATE_ALIASES.get(part)
        if alias:
            out.add(alias.replace(" ", ""))
    return out


def _input_contains_point(text: str, lat: float, lng: float) -> bool:
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", text or "")]
    if len(nums) < 2:
        return False
    for i, a in enumerate(nums):
        for b in nums[i + 1 :]:
            if abs(a - lat) <= 0.02 and abs(b - lng) <= 0.02:
                return True
            if abs(a - lng) <= 0.02 and abs(b - lat) <= 0.02:
                return True
    return False


def _address_keeps_user_place(raw: str, normalized: str) -> bool:
    user = _tokens(raw)
    kept = _tokens(normalized)
    if not user:
        return False
    return user <= kept


def _fixture_key(raw: str) -> str:
    blob = re.sub(r"\s+", " ", (raw or "").strip().lower())
    if "near nunn" in blob:
        return "advisor_place_near_nunn"
    return "advisor_place_needs_more"


def _public_row(
    *,
    raw: str,
    lookup_input: str,
    input_kind: str,
    llm_used: bool,
    status: str,
    note: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict[str, Any]:
    return {
        "raw_input": raw,
        "lookup_input": lookup_input,
        "input_type": input_kind,
        "normalized_address": lookup_input if input_kind == "ADDRESS" else None,
        "latitude": latitude,
        "longitude": longitude,
        "llm_used": llm_used,
        "status": status,
        "note": note,
    }


def _direct(raw: str, classified: dict[str, Any], *, note: str) -> dict[str, Any]:
    return {
        "lookup_input": classified["input"],
        "kind": classified["kind"],
        "input_kind": classified["input_kind"],
        "latitude": classified.get("latitude"),
        "longitude": classified.get("longitude"),
        "llm_used": False,
        "status": "DIRECT",
        "public": _public_row(
            raw=raw,
            lookup_input=classified["input"],
            input_kind=classified["input_kind"],
            llm_used=False,
            status="DIRECT",
            note=note,
            latitude=classified.get("latitude"),
            longitude=classified.get("longitude"),
        ),
    }


def _needs_more(raw: str, message: str, *, llm_used: bool) -> dict[str, Any]:
    return {
        "lookup_input": raw,
        "kind": "address",
        "input_kind": "ADDRESS",
        "latitude": None,
        "longitude": None,
        "llm_used": llm_used,
        "status": "NEEDS_MORE",
        "message": message,
        "public": _public_row(
            raw=raw,
            lookup_input=raw,
            input_kind="NEEDS_MORE",
            llm_used=llm_used,
            status="NEEDS_MORE",
            note=message,
        ),
    }


def _apply_llm_payload(raw: str, payload: dict[str, Any]) -> dict[str, Any]:
    input_type = str(payload.get("input_type") or "").strip().upper()
    if input_type == "NEEDS_MORE":
        return _needs_more(
            raw,
            str(payload.get("needs_user") or "").strip() or ASK_FOR_MORE,
            llm_used=True,
        )
    if input_type == "COORDINATE":
        lat = payload.get("latitude")
        lng = payload.get("longitude")
        try:
            lat_f = float(lat)
            lng_f = float(lng)
        except (TypeError, ValueError):
            return _needs_more(raw, ASK_FOR_MORE, llm_used=True)
        if not _input_contains_point(raw, lat_f, lng_f):
            return _needs_more(
                raw,
                "The input cleaner must not invent coordinates. "
                "Enter lat,lng yourself, or a fuller street address.",
                llm_used=True,
            )
        try:
            validated = validate_us_query_point(lat_f, lng_f)
        except CoordinateValidationError as exc:
            return _needs_more(raw, exc.message, llm_used=True)
        lookup = format_coord_input(validated["latitude"], validated["longitude"])
        return {
            "lookup_input": lookup,
            "kind": "coord",
            "input_kind": "COORDINATE",
            "latitude": validated["latitude"],
            "longitude": validated["longitude"],
            "llm_used": True,
            "status": "CLEANED",
            "public": _public_row(
                raw=raw,
                lookup_input=lookup,
                input_kind="COORDINATE",
                llm_used=True,
                status="CLEANED",
                note="Coordinates were already in the typed input; Mireye still locates the parcel.",
                latitude=validated["latitude"],
                longitude=validated["longitude"],
            ),
        }
    if input_type != "ADDRESS":
        return _needs_more(raw, ASK_FOR_MORE, llm_used=True)
    normalized = str(payload.get("normalized_address") or "").strip()
    if not normalized or not _address_keeps_user_place(raw, normalized):
        return _needs_more(
            raw,
            "Could not tidy that place without inventing a location. "
            + ASK_FOR_MORE,
            llm_used=True,
        )
    if payload.get("latitude") is not None or payload.get("longitude") is not None:
        # Ignore invented coordinates; keep the address string only.
        pass
    return {
        "lookup_input": normalized,
        "kind": "address",
        "input_kind": "ADDRESS",
        "latitude": None,
        "longitude": None,
        "llm_used": True,
        "status": "CLEANED",
        "public": _public_row(
            raw=raw,
            lookup_input=normalized,
            input_kind="ADDRESS",
            llm_used=True,
            status="CLEANED",
            note="Input format was tidied. Mireye still has to locate and confirm the parcel.",
        ),
    }


def prepare_advisor_place(
    place: str,
    *,
    provider_name: str | None = None,
) -> dict[str, Any]:
    """Return the Mireye lookup input. Never invents a parcel."""
    raw = (place or "").strip()
    if not raw:
        return _needs_more(
            raw,
            "Enter a U.S. street address or lat,lng before running the Agent.",
            llm_used=False,
        )
    if _PLACE_FN is not None:
        return _PLACE_FN(raw)

    try:
        classified = classify_place_input(raw)
    except CoordinateValidationError as exc:
        return _needs_more(raw, exc.message, llm_used=False)

    if classified["input_kind"] == "COORDINATE":
        return _direct(
            raw,
            classified,
            note="Coordinates go to Mireye directly. The pin is not a parcel boundary.",
        )
    if not place_needs_llm_cleanup(raw):
        return _direct(
            raw,
            classified,
            note="Standard street or city+state input goes to Mireye directly.",
        )

    from rangematch.llm_provider import configured_provider_name, get_provider

    requested = (provider_name or configured_provider_name()).strip().upper()
    provider = get_provider(requested)
    completion = provider.complete_json(
        system=PLACE_SYSTEM_PROMPT,
        user=json.dumps({"place": raw}, ensure_ascii=False),
        prompt_version=PLACE_PROMPT_VERSION,
        fixture_key=_fixture_key(raw) if requested == "FIXTURE" else None,
        response_schema=PLACE_OUTPUT_SCHEMA if requested in {"OPENAI", "DEEPSEEK"} else None,
    )
    if completion.content is None or not isinstance(completion.content, dict):
        return _needs_more(
            raw,
            ASK_FOR_MORE
            if completion.provider_status in {"NOT_CONFIGURED", "FAILED_EXTERNAL", "FIXTURE"}
            else ASK_FOR_MORE,
            llm_used=requested != "FIXTURE",
        )
    return _apply_llm_payload(raw, completion.content)

