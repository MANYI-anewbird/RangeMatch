"""Deterministic F08 woody / shrub vegetation-structure derivation.

Implements docs/F08_WOODY_SHRUB_DERIVATION_SPEC.yaml@0.1.0.

Woody fractional cover is vegetation-structure context only — not browse,
obstruction, herbaceous replacement, carrying capacity, profitability, or
Cow-Calf versus Sheep ranking. Reuses the shared RAP coverV3 artifact with F02.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

DERIVATION_SPEC_VERSION = "F08_WOODY_SHRUB_DERIVATION_SPEC.yaml@0.1.0"
ALGORITHM_VERSION = "F08_WOODY_SHRUB_DERIVATION@0.1.0"
FACTOR_ID = "F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"
CANONICAL_SOURCE_ID = "USDA_ARS_RAP_V3_COVER"
LAND_FACT_UNIT = "fraction"
VALID_RANGE = [0.0, 1.0]

LIMITATIONS = [
    "Shrub and tree cover are modeled RAP fractional cover context only.",
    "Shrub cover is not browse availability, palatability, botanical composition, toxicity, or nutritive value.",
    "Tree cover is not automatic grazing obstruction or cattle/sheep exclusion.",
    "combined_modeled_woody_cover_fraction is derived SHR+TRE context, not an independent RAP canopy band.",
    "Woody cover does not prove low herbaceous production.",
    "F08 must not replace F02 herbaceous Land Facts.",
    "Mireye lcms_class / tree_canopy fields are point QA only and are not parcel Land Facts.",
    "Shared RAP coverage may be COVERAGE_UNQUANTIFIED; that is not complete pixel-area proof.",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_rap_cover_table(feature: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Parse RAP Feature properties.cover row-oriented table into a field map."""
    if not feature:
        return None
    props = feature.get("properties") if isinstance(feature, Mapping) else None
    if not isinstance(props, Mapping):
        # Allow bare properties dict or already-parsed cover payload.
        props = feature if isinstance(feature, Mapping) else None
    if not isinstance(props, Mapping):
        return None
    table = props.get("cover")
    if isinstance(table, list) and len(table) >= 2 and isinstance(table[0], list):
        header = table[0]
        row = table[1]
        return {str(key): value for key, value in zip(header, row)}
    return None


def percent_to_fraction(value: Any) -> float | None:
    """Convert RAP percent cover to Land Fact fraction in [0,1]. Null stays null."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) / 100.0
    try:
        text = str(value).strip()
        if text == "" or text.lower() in {"null", "none", "nan"}:
            return None
        return float(text) / 100.0
    except (TypeError, ValueError):
        return None


def combined_modeled_woody_cover_fraction(
    shrub_cover_fraction: float | None,
    tree_cover_fraction: float | None,
) -> float | None:
    """Derived SHR+TRE context. Null if either input is null. Never treat null as 0."""
    if shrub_cover_fraction is None or tree_cover_fraction is None:
        return None
    return float(shrub_cover_fraction) + float(tree_cover_fraction)


def extract_f02_cover_land_fact(f02_factor: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return the F02 RAP coverV3 Land Fact used for shared provenance, if present."""
    if not f02_factor:
        return None
    for fact in f02_factor.get("land_facts") or []:
        if not isinstance(fact, Mapping):
            continue
        provenance = fact.get("provenance") or {}
        endpoint = provenance.get("endpoint")
        source_ref = provenance.get("source_reference")
        if endpoint == "coverV3" or source_ref == "RAP_coverV3":
            return dict(fact)
        # Fallback: perennial herb cover is always from coverV3 in current profiles.
        if fact.get("variable_id") == "VAR_F02_PERENNIAL_HERB_COVER":
            return dict(fact)
    return None


def resolve_input_quality_state(
    *,
    shrub_cover_fraction: float | None,
    tree_cover_fraction: float | None,
    applicability_status: str | None,
    coverage_status: str | None,
    point_only_secondary: bool = False,
    conflicting_sources: bool = False,
) -> str:
    if conflicting_sources:
        return "CONFLICTING_SOURCES"
    if point_only_secondary:
        return "POINT_ONLY_SECONDARY"
    if shrub_cover_fraction is None and tree_cover_fraction is None:
        return "MISSING"
    applicability = applicability_status or "UNKNOWN"
    if applicability in {"OUTSIDE_DOCUMENTED_PRODUCT_SCOPE", "UNKNOWN"}:
        return "RAP_OUTSIDE_OR_UNKNOWN_APPLICABILITY"
    coverage = coverage_status or "UNKNOWN"
    if coverage in {None, "", "MISSING", "UNKNOWN"}:
        return "COVERAGE_MISSING"
    if coverage == "COVERAGE_UNQUANTIFIED":
        return "WOODY_CONTEXT_AVAILABLE_COVERAGE_UNQUANTIFIED"
    if coverage in {
        "COMPLETE_RANGELAND_COVERAGE",
        "PARTIAL_RANGELAND_COVERAGE",
    } and applicability == "IN_DOCUMENTED_PRODUCT_SCOPE":
        if shrub_cover_fraction is not None and tree_cover_fraction is not None:
            return "WOODY_CONTEXT_COMPLETE"
        return "COVERAGE_MISSING"
    return "COVERAGE_MISSING"


def derive_f08_from_rap_bands(
    *,
    raw_shr_percent: Any,
    raw_tre_percent: Any,
    source_year: int | None,
    mask: bool | None,
    geometry_hash: str | None,
    response_or_artifact_hash: str | None,
    applicability_status: str | None,
    coverage_status: str | None,
    coverage_record: Mapping[str, Any] | None = None,
    applicability_record: Mapping[str, Any] | None = None,
    fetched_at: str | None = None,
    geometry_id: str | None = None,
    geometry_reference: str | None = None,
    artifact_path: str | None = None,
    reused_existing_artifact: bool = False,
    duplicate_coverV3_fetch: bool = False,
    point_only_secondary: bool = False,
    conflicting_sources: bool = False,
    derived_at: str | None = None,
) -> dict[str, Any]:
    """Derive F08 Land Facts and factor payload from RAP SHR/TRE percent bands."""
    shrub = percent_to_fraction(raw_shr_percent)
    tree = percent_to_fraction(raw_tre_percent)
    combined = combined_modeled_woody_cover_fraction(shrub, tree)

    # Preserve explicit null RAP inputs: if the band key was present as null,
    # percent_to_fraction already returns None. If both missing entirely and
    # no secondary flags, quality becomes MISSING.
    state = resolve_input_quality_state(
        shrub_cover_fraction=shrub,
        tree_cover_fraction=tree,
        applicability_status=applicability_status,
        coverage_status=coverage_status,
        point_only_secondary=point_only_secondary,
        conflicting_sources=conflicting_sources,
    )

    applicability = dict(applicability_record or {})
    if applicability_status and "domain_status" not in applicability:
        applicability["domain_status"] = applicability_status

    coverage = dict(coverage_record or {})
    if coverage_status and "status" not in coverage:
        coverage["status"] = coverage_status

    raw_shr = None if raw_shr_percent is None else (
        float(raw_shr_percent)
        if isinstance(raw_shr_percent, (int, float)) and not isinstance(raw_shr_percent, bool)
        else raw_shr_percent
    )
    raw_tre = None if raw_tre_percent is None else (
        float(raw_tre_percent)
        if isinstance(raw_tre_percent, (int, float)) and not isinstance(raw_tre_percent, bool)
        else raw_tre_percent
    )

    shared_provenance = {
        "source_reference": "RAP_coverV3",
        "source_product_and_version": "RAP_v3",
        "endpoint": "coverV3",
        "canonical_source_id": CANONICAL_SOURCE_ID,
        "fetched_at": fetched_at,
        "geometry_hash": geometry_hash,
        "response_or_artifact_hash": response_or_artifact_hash,
        "request_parameters": {
            "mask": mask,
            "year": source_year,
        },
        "derivation_spec_version": DERIVATION_SPEC_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "raw_rap_shr_percent": raw_shr,
        "raw_rap_tre_percent": raw_tre,
        "artifact_path": artifact_path,
        "reused_existing_artifact": reused_existing_artifact,
        "duplicate_coverV3_fetch": duplicate_coverV3_fetch,
    }

    def _land_fact(variable_id: str, name: str, value: float | None, *, derived: bool = False) -> dict[str, Any]:
        return {
            "variable_id": variable_id,
            "name": name,
            "observation": {
                "value_state": "KNOWN" if value is not None else "UNKNOWN",
                "value": value,
                "unit": LAND_FACT_UNIT,
                "valid_range": list(VALID_RANGE),
                "spatial_semantics": "parcel_mean",
                "temporal_semantics": f"annual_{source_year}" if source_year is not None else None,
            },
            "source": {
                "provider": "USDA_ARS",
                "product": "RAP",
                "version": "v3",
                "data_kind": "MODELED",
                "adapter_id": "RAP_AGGREGATE_API_REUSE",
                "modeled": True,
                "derived_not_independent_band": derived,
            },
            "applicability": applicability,
            "coverage": coverage,
            "quality": {
                "confidence_state": (
                    "LIMITED_BY_UNQUANTIFIED_COVERAGE"
                    if coverage.get("status") == "COVERAGE_UNQUANTIFIED"
                    else "CONTEXT_ONLY"
                ),
                "modeled": True,
                "resolution": "30_meters_nominal",
            },
            "provenance": dict(shared_provenance),
            "limitations": list(LIMITATIONS),
        }

    land_facts = [
        _land_fact(
            "VAR_F08_SHRUB_COVER_FRACTION",
            "shrub_cover_fraction",
            shrub,
        ),
        _land_fact(
            "VAR_F08_TREE_COVER_FRACTION",
            "tree_cover_fraction",
            tree,
        ),
        _land_fact(
            "VAR_F08_COMBINED_MODELED_WOODY_COVER_FRACTION",
            "combined_modeled_woody_cover_fraction",
            combined,
            derived=True,
        ),
    ]

    return {
        "factor_id": FACTOR_ID,
        "input_quality_state": state,
        "derivation_spec": DERIVATION_SPEC_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "canonical_source_id": CANONICAL_SOURCE_ID,
        "geometry_id": geometry_id,
        "geometry_reference": geometry_reference,
        "geometry_hash": geometry_hash,
        "source_year": source_year,
        "mask": mask,
        "applicability_status": applicability_status,
        "coverage_status": coverage_status,
        "applicability": applicability,
        "coverage": coverage,
        "shrub_cover_fraction": shrub,
        "tree_cover_fraction": tree,
        "combined_modeled_woody_cover_fraction": combined,
        "unit": LAND_FACT_UNIT,
        "valid_range": list(VALID_RANGE),
        "raw_rap_shr_percent": raw_shr,
        "raw_rap_tre_percent": raw_tre,
        "response_or_artifact_hash": response_or_artifact_hash,
        "reused_existing_artifact": reused_existing_artifact,
        "duplicate_coverV3_fetch": duplicate_coverV3_fetch,
        "ranking_effect": "NONE",
        "derived_at": derived_at or _now_iso(),
        "land_facts": land_facts,
        "provenance": shared_provenance,
        "limitations": list(LIMITATIONS),
        "unknowns": [
            item
            for item in [
                (
                    "Shared RAP eligible/masked/no-data/valid parcel areas are not quantified."
                    if coverage_status == "COVERAGE_UNQUANTIFIED"
                    else None
                ),
                "Botanical composition of woody cover is not verified.",
                "Browse availability is not established.",
                "Woody obstruction class is not established.",
            ]
            if item
        ],
        "prohibited_interpretations_applied": True,
        "mireye_used_as_parcel_land_fact": False,
        "browse_inferred": False,
        "obstruction_inferred": False,
        "forced_sum_to_100": False,
        "null_treated_as_zero": False,
        "combined_included_in_composition_sum": False,
    }


def derive_f08_from_coverV3_artifact(
    coverV3_feature: Mapping[str, Any] | None,
    *,
    artifact_path: str | Path | None = None,
    response_or_artifact_hash: str | None = None,
    geometry_hash: str | None = None,
    applicability_status: str | None = None,
    coverage_status: str | None = None,
    coverage_record: Mapping[str, Any] | None = None,
    applicability_record: Mapping[str, Any] | None = None,
    fetched_at: str | None = None,
    geometry_id: str | None = None,
    geometry_reference: str | None = None,
    reused_existing_artifact: bool = False,
    duplicate_coverV3_fetch: bool = False,
    point_only_secondary: bool = False,
    conflicting_sources: bool = False,
    derived_at: str | None = None,
) -> dict[str, Any]:
    """Derive F08 from a RAP coverV3 Feature payload (or None → MISSING)."""
    if coverV3_feature is None and not point_only_secondary and not conflicting_sources:
        return derive_f08_from_rap_bands(
            raw_shr_percent=None,
            raw_tre_percent=None,
            source_year=None,
            mask=None,
            geometry_hash=geometry_hash,
            response_or_artifact_hash=response_or_artifact_hash,
            applicability_status=applicability_status,
            coverage_status=coverage_status,
            coverage_record=coverage_record,
            applicability_record=applicability_record,
            fetched_at=fetched_at,
            geometry_id=geometry_id,
            geometry_reference=geometry_reference,
            artifact_path=str(artifact_path) if artifact_path else None,
            reused_existing_artifact=reused_existing_artifact,
            duplicate_coverV3_fetch=duplicate_coverV3_fetch,
            derived_at=derived_at,
        )

    if point_only_secondary and coverV3_feature is None:
        result = derive_f08_from_rap_bands(
            raw_shr_percent=None,
            raw_tre_percent=None,
            source_year=None,
            mask=None,
            geometry_hash=geometry_hash,
            response_or_artifact_hash=response_or_artifact_hash,
            applicability_status=applicability_status,
            coverage_status=coverage_status,
            point_only_secondary=True,
            derived_at=derived_at,
        )
        result["input_quality_state"] = "POINT_ONLY_SECONDARY"
        return result

    if conflicting_sources:
        bands = parse_rap_cover_table(coverV3_feature) or {}
        result = derive_f08_from_rap_bands(
            raw_shr_percent=bands.get("SHR"),
            raw_tre_percent=bands.get("TRE"),
            source_year=_coerce_year(bands.get("year"), coverV3_feature),
            mask=_coerce_mask(coverV3_feature),
            geometry_hash=geometry_hash,
            response_or_artifact_hash=response_or_artifact_hash,
            applicability_status=applicability_status or "IN_DOCUMENTED_PRODUCT_SCOPE",
            coverage_status=coverage_status or "COVERAGE_UNQUANTIFIED",
            coverage_record=coverage_record,
            applicability_record=applicability_record,
            conflicting_sources=True,
            derived_at=derived_at,
        )
        result["input_quality_state"] = "CONFLICTING_SOURCES"
        return result

    bands = parse_rap_cover_table(coverV3_feature)
    if not bands:
        return derive_f08_from_rap_bands(
            raw_shr_percent=None,
            raw_tre_percent=None,
            source_year=None,
            mask=None,
            geometry_hash=geometry_hash,
            response_or_artifact_hash=response_or_artifact_hash,
            applicability_status=applicability_status,
            coverage_status=coverage_status,
            derived_at=derived_at,
        )

    path_str = str(artifact_path) if artifact_path else None
    artifact_hash = response_or_artifact_hash
    if artifact_hash is None and artifact_path is not None and Path(artifact_path).is_file():
        artifact_hash = sha256_file(artifact_path)

    return derive_f08_from_rap_bands(
        raw_shr_percent=bands.get("SHR"),
        raw_tre_percent=bands.get("TRE"),
        source_year=_coerce_year(bands.get("year"), coverV3_feature),
        mask=_coerce_mask(coverV3_feature),
        geometry_hash=geometry_hash,
        response_or_artifact_hash=artifact_hash,
        applicability_status=applicability_status,
        coverage_status=coverage_status,
        coverage_record=coverage_record,
        applicability_record=applicability_record,
        fetched_at=fetched_at,
        geometry_id=geometry_id,
        geometry_reference=geometry_reference,
        artifact_path=path_str,
        reused_existing_artifact=reused_existing_artifact,
        duplicate_coverV3_fetch=duplicate_coverV3_fetch,
        derived_at=derived_at,
    )


def _coerce_year(band_year: Any, feature: Mapping[str, Any] | None) -> int | None:
    if isinstance(band_year, (int, float)) and not isinstance(band_year, bool):
        return int(band_year)
    if feature:
        props = feature.get("properties") if isinstance(feature.get("properties"), Mapping) else feature
        if isinstance(props, Mapping):
            year = props.get("year")
            if isinstance(year, (int, float)) and not isinstance(year, bool):
                return int(year)
    return None


def _coerce_mask(feature: Mapping[str, Any] | None) -> bool | None:
    if not feature:
        return None
    props = feature.get("properties") if isinstance(feature.get("properties"), Mapping) else feature
    if isinstance(props, Mapping) and "mask" in props:
        return bool(props.get("mask"))
    return None


def derive_f08_reusing_f02_artifact(
    *,
    coverV3_artifact_path: str | Path,
    f02_factor: Mapping[str, Any],
    geometry_hash: str | None = None,
    geometry_id: str | None = None,
    geometry_reference: str | None = None,
    expected_artifact_hash: str | None = None,
    derived_at: str | None = None,
) -> dict[str, Any]:
    """Derive F08 by reading an existing coverV3 artifact shared with F02.

    Never issues a RAP network request. Verifies artifact hash against F02 when
    present. Shared applicability and coverage are copied from F02.
    """
    path = Path(coverV3_artifact_path)
    if not path.is_file():
        raise FileNotFoundError(f"RAP coverV3 artifact not found: {path}")

    artifact_hash = sha256_file(path)
    f02_cover = extract_f02_cover_land_fact(f02_factor)
    if f02_cover is None:
        raise ValueError("F02 coverV3 Land Fact not found; cannot share RAP provenance")

    f02_prov = f02_cover.get("provenance") or {}
    f02_hash = expected_artifact_hash or f02_prov.get("response_or_artifact_hash")
    if f02_hash and f02_hash != artifact_hash:
        raise ValueError(
            "F08 refuses mismatched coverV3 artifact hash vs F02: "
            f"artifact={artifact_hash} f02={f02_hash}"
        )

    geo_hash = geometry_hash or f02_prov.get("geometry_hash")
    if geo_hash and f02_prov.get("geometry_hash") and geo_hash != f02_prov.get("geometry_hash"):
        raise ValueError(
            "F08 refuses geometry_hash mismatch vs F02 shared coverV3 artifact"
        )

    request_params = f02_prov.get("request_parameters") or {}
    applicability = f02_cover.get("applicability") or {}
    coverage = f02_cover.get("coverage") or {}
    applicability_status = applicability.get("domain_status")
    coverage_status = coverage.get("status")

    cover_feature = json.loads(path.read_text())
    # Cross-check year/mask from artifact vs F02 request parameters.
    artifact_year = _coerce_year(None, cover_feature)
    artifact_mask = _coerce_mask(cover_feature)
    f02_year = request_params.get("year")
    f02_mask = request_params.get("mask")
    if f02_year is not None and artifact_year is not None and int(f02_year) != int(artifact_year):
        raise ValueError(
            f"F08 refuses source_year mismatch vs F02: artifact={artifact_year} f02={f02_year}"
        )
    if f02_mask is not None and artifact_mask is not None and bool(f02_mask) != bool(artifact_mask):
        raise ValueError(
            f"F08 refuses mask mismatch vs F02: artifact={artifact_mask} f02={f02_mask}"
        )

    result = derive_f08_from_coverV3_artifact(
        cover_feature,
        artifact_path=path,
        response_or_artifact_hash=artifact_hash,
        geometry_hash=geo_hash,
        applicability_status=applicability_status,
        coverage_status=coverage_status,
        coverage_record=coverage,
        applicability_record=applicability,
        fetched_at=f02_prov.get("fetched_at"),
        geometry_id=geometry_id,
        geometry_reference=geometry_reference,
        reused_existing_artifact=True,
        duplicate_coverV3_fetch=False,
        derived_at=derived_at,
    )
    result["shared_with_f02"] = {
        "same_artifact": True,
        "same_geometry_hash": True,
        "same_source_year": True,
        "same_mask": True,
        "same_applicability_status": True,
        "same_coverage_status": True,
        "f02_response_or_artifact_hash": f02_hash,
        "f08_response_or_artifact_hash": artifact_hash,
        "f02_source_year": f02_year,
        "f02_mask": f02_mask,
        "f02_applicability_status": applicability_status,
        "f02_coverage_status": coverage_status,
    }
    result["unknowns"] = [u for u in (result.get("unknowns") or []) if u]
    return result


def evaluate_f08_signal(factor: Mapping[str, Any] | None) -> dict[str, Any]:
    """Map F08 Factor payload to deterministic signal / explanation."""
    if not factor:
        return {
            "factor_id": FACTOR_ID,
            "signal": "UNKNOWN",
            "ranking_effect": "NONE",
            "explanation_code": "F08_EXPL_MISSING",
            "input_quality_state": "MISSING",
            "browse_inferred": False,
            "obstruction_inferred": False,
        }

    state = factor.get("input_quality_state") or "MISSING"
    mapping_states = {
        "WOODY_CONTEXT_AVAILABLE_COVERAGE_UNQUANTIFIED": (
            "NEEDS_VERIFICATION",
            "F08_EXPL_COVERAGE_UNQUANTIFIED",
        ),
        "WOODY_CONTEXT_COMPLETE": ("CONTEXT_DEPENDENT", "F08_EXPL_CONTEXT_ONLY"),
        "RAP_OUTSIDE_OR_UNKNOWN_APPLICABILITY": (
            "NEEDS_VERIFICATION",
            "F08_EXPL_APPLICABILITY",
        ),
        "COVERAGE_MISSING": ("NEEDS_VERIFICATION", "F08_EXPL_COVERAGE"),
        "POINT_ONLY_SECONDARY": ("NEEDS_VERIFICATION", "F08_EXPL_POINT_ONLY"),
        "CONFLICTING_SOURCES": ("NEEDS_VERIFICATION", "F08_EXPL_CONFLICT"),
        "MISSING": ("UNKNOWN", "F08_EXPL_MISSING"),
    }
    signal, explanation = mapping_states.get(
        state, ("NEEDS_VERIFICATION", "F08_EXPL_UNRECOGNIZED")
    )
    return {
        "factor_id": FACTOR_ID,
        "signal": signal,
        "ranking_effect": "NONE",
        "explanation_code": explanation,
        "input_quality_state": state,
        "shrub_cover_fraction": factor.get("shrub_cover_fraction"),
        "tree_cover_fraction": factor.get("tree_cover_fraction"),
        "combined_modeled_woody_cover_fraction": factor.get(
            "combined_modeled_woody_cover_fraction"
        ),
        "source_year": factor.get("source_year"),
        "mask": factor.get("mask"),
        "applicability_status": factor.get("applicability_status"),
        "coverage_status": factor.get("coverage_status"),
        "response_or_artifact_hash": factor.get("response_or_artifact_hash"),
        "reused_existing_artifact": factor.get("reused_existing_artifact"),
        "duplicate_coverV3_fetch": factor.get("duplicate_coverV3_fetch"),
        "algorithm_version": factor.get("algorithm_version"),
        "browse_inferred": False,
        "obstruction_inferred": False,
        "labeled_complete": state == "WOODY_CONTEXT_COMPLETE",
    }


def slim_f08_factor_for_profile(derived: Mapping[str, Any]) -> dict[str, Any]:
    """Compact factor section suitable for Land Profile storage."""
    return {
        "factor_id": derived.get("factor_id", FACTOR_ID),
        "input_quality_state": derived.get("input_quality_state"),
        "derivation_spec": derived.get("derivation_spec"),
        "algorithm_version": derived.get("algorithm_version"),
        "canonical_source_id": derived.get("canonical_source_id"),
        "geometry_id": derived.get("geometry_id"),
        "geometry_reference": derived.get("geometry_reference"),
        "geometry_hash": derived.get("geometry_hash"),
        "source_year": derived.get("source_year"),
        "mask": derived.get("mask"),
        "applicability_status": derived.get("applicability_status"),
        "coverage_status": derived.get("coverage_status"),
        "applicability": derived.get("applicability"),
        "coverage": derived.get("coverage"),
        "shrub_cover_fraction": derived.get("shrub_cover_fraction"),
        "tree_cover_fraction": derived.get("tree_cover_fraction"),
        "combined_modeled_woody_cover_fraction": derived.get(
            "combined_modeled_woody_cover_fraction"
        ),
        "unit": derived.get("unit"),
        "valid_range": derived.get("valid_range"),
        "raw_rap_shr_percent": derived.get("raw_rap_shr_percent"),
        "raw_rap_tre_percent": derived.get("raw_rap_tre_percent"),
        "response_or_artifact_hash": derived.get("response_or_artifact_hash"),
        "reused_existing_artifact": derived.get("reused_existing_artifact"),
        "duplicate_coverV3_fetch": derived.get("duplicate_coverV3_fetch"),
        "shared_with_f02": derived.get("shared_with_f02"),
        "ranking_effect": "NONE",
        "derived_at": derived.get("derived_at"),
        "land_facts": derived.get("land_facts"),
        "provenance": derived.get("provenance"),
        "limitations": derived.get("limitations"),
        "unknowns": derived.get("unknowns"),
        "prohibited_interpretations_applied": True,
        "mireye_used_as_parcel_land_fact": False,
        "browse_inferred": False,
        "obstruction_inferred": False,
        "forced_sum_to_100": False,
        "null_treated_as_zero": False,
        "combined_included_in_composition_sum": False,
        "result_reference": derived.get("result_reference"),
        "source_fixture_references": derived.get("source_fixture_references"),
        "live_gate": derived.get("live_gate"),
    }


def run_cper_f08_data_reuse_gate(
    *,
    repo_root: str | Path,
    write_artifacts: bool = True,
) -> dict[str, Any]:
    """CPER F08 gate: reuse existing F02 coverV3 artifact; no RAP network call."""
    root = Path(repo_root)
    geometry_path = root / "test-data/engineering_test_geometry_cper_001.geojson"
    profile_path = root / "test-data/land-profiles/land_profile_cper_001.json"
    artifact_path = root / "test-data/live-results/cper/rap_coverV3_2025.json"
    out_dir = root / "test-data/live-results/cper"

    profile = json.loads(profile_path.read_text())
    f02 = (profile.get("factors") or {}).get("F02_HERBACEOUS_RESOURCE") or {}
    geometry_hash = profile.get("geometry_hash") or sha256_file(geometry_path)

    derived = derive_f08_reusing_f02_artifact(
        coverV3_artifact_path=artifact_path,
        f02_factor=f02,
        geometry_hash=geometry_hash,
        geometry_id=profile.get("geometry_id") or "ENGINEERING_TEST_GEOMETRY_CPER_001",
        geometry_reference=(
            profile.get("geometry_reference")
            or "test-data/engineering_test_geometry_cper_001.geojson"
        ),
    )
    signal = evaluate_f08_signal(derived)

    live_gate = {
        "live_gate_id": "F08_RAP_COVERV3_DATA_REUSE_CPER",
        "status": (
            "DATA_REUSE_VERIFIED"
            if (
                derived.get("reused_existing_artifact") is True
                and derived.get("duplicate_coverV3_fetch") is False
                and derived.get("input_quality_state")
                == "WOODY_CONTEXT_AVAILABLE_COVERAGE_UNQUANTIFIED"
                and signal["signal"] == "NEEDS_VERIFICATION"
            )
            else "DATA_REUSE_NEEDS_ATTENTION"
        ),
        "network_rap_request_issued": False,
        "reused_existing_artifact": derived.get("reused_existing_artifact"),
        "duplicate_coverV3_fetch": derived.get("duplicate_coverV3_fetch"),
        "artifact_path": "test-data/live-results/cper/rap_coverV3_2025.json",
        "response_or_artifact_hash": derived.get("response_or_artifact_hash"),
        "shared_with_f02": derived.get("shared_with_f02"),
        "input_quality_state": derived.get("input_quality_state"),
        "signal": signal["signal"],
        "explanation_code": signal["explanation_code"],
        "ranking_effect": "NONE",
        "algorithm_version": ALGORITHM_VERSION,
        "derived_at": derived.get("derived_at"),
        "shrub_cover_fraction": derived.get("shrub_cover_fraction"),
        "tree_cover_fraction": derived.get("tree_cover_fraction"),
        "combined_modeled_woody_cover_fraction": derived.get(
            "combined_modeled_woody_cover_fraction"
        ),
        "raw_rap_shr_percent": derived.get("raw_rap_shr_percent"),
        "raw_rap_tre_percent": derived.get("raw_rap_tre_percent"),
    }
    derived["live_gate"] = live_gate
    derived["result_reference"] = (
        "test-data/live-results/cper/f08_derivation_result_2026-08-08.json"
    )
    derived["source_fixture_references"] = [
        "test-data/live-results/cper/rap_coverV3_2025.json",
        "test-data/live-results/cper/rap_request_2025.json",
    ]

    if write_artifacts:
        out_dir.mkdir(parents=True, exist_ok=True)
        result_path = out_dir / "f08_derivation_result_2026-08-08.json"
        result_path.write_text(json.dumps(derived, indent=2) + "\n")

        from rangematch.demo_report import write_demo_closure
        from rangematch.engine import evaluate_land_profile

        factor = slim_f08_factor_for_profile(derived)
        profile["factors"]["F08_WOODY_AND_SHRUB_VEGETATION_STRUCTURE"] = factor
        profile_path.write_text(json.dumps(profile, indent=2) + "\n")
        match_result = evaluate_land_profile(profile)
        (root / "test-data/land-profiles/match_result_cper_001.json").write_text(
            json.dumps(match_result, indent=2) + "\n"
        )
        write_demo_closure(
            profile_path,
            html_output=root
            / "test-data/land-profiles/land_profile_cper_001_demo_closure.html",
            json_output=root
            / "test-data/land-profiles/land_profile_cper_001_demo_closure.json",
        )

        gate_path = out_dir / "f08_live_gate_cper_2026-08-08.json"
        gate_path.write_text(json.dumps(live_gate, indent=2) + "\n")

    return {
        "derived": derived,
        "signal": signal,
        "live_gate": live_gate,
    }
