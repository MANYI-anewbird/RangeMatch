"""Natural Cattle Profile — Phase 5 deterministic projector.

Combined Environmental Evidence Packet → five-domain natural foundation.
No LLM. No PDF. No access/infrastructure. No stocking inference.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from rangematch.unified_output import sha256_canonical

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "docs" / "schemas" / "natural_cattle_profile.schema.json"

SCHEMA_VERSION = "natural_cattle_profile@1.0.0"
PROJECTOR_ID = "NATURAL_CATTLE_PROFILE_PROJECTOR@1.0.0"

DOMAIN_TERRAIN = "TERRAIN"
DOMAIN_FEED = "FEED_VEGETATION"
DOMAIN_WATER = "WATER"
DOMAIN_CLIMATE = "CLIMATE_HAZARD"
DOMAIN_SOIL = "SOIL_ECOLOGY"

DOMAIN_ORDER: tuple[str, ...] = (
    DOMAIN_TERRAIN,
    DOMAIN_FEED,
    DOMAIN_WATER,
    DOMAIN_CLIMATE,
    DOMAIN_SOIL,
)

BUYER_LABELS: dict[str, str] = {
    DOMAIN_TERRAIN: "Terrain",
    DOMAIN_FEED: "Forage",
    DOMAIN_WATER: "Water",
    DOMAIN_CLIMATE: "Climate",
    DOMAIN_SOIL: "Soil",
}

STATUS_PROMISING = "PROMISING_NATURAL_FOUNDATION"
STATUS_CONDITIONAL = "CONDITIONAL_NATURAL_FOUNDATION"
STATUS_CONSTRAINED = "ENVIRONMENTALLY_CONSTRAINED"
STATUS_INSUFFICIENT = "INSUFFICIENT_ENVIRONMENTAL_EVIDENCE"

CONF_HIGH = "HIGH"
CONF_MEDIUM = "MEDIUM"
CONF_LOW = "LOW"
CONF_INSUFFICIENT = "INSUFFICIENT"

CONF_RANK = {
    CONF_HIGH: 3,
    CONF_MEDIUM: 2,
    CONF_LOW: 1,
    CONF_INSUFFICIENT: 0,
}

# Empty until a reviewed scientific rule is added. Missing data never fills this.
APPROVED_HARD_CONSTRAINT_RULES: dict[str, Mapping[str, Any]] = {}

PROHIBITED_INFERENCES: tuple[str, ...] = (
    "MISSING_WATER_IS_NOT_NO_WATER",
    "SOURCE_UNAVAILABLE_IS_NOT_NEGATIVE_NATURAL_FACT",
    "POINT_OR_CONTEXT_IS_NOT_PARCEL_FACT",
    "RAP_IS_NOT_STOCKING_RATE_OR_AVAILABLE_FORAGE",
    "NDVI_IS_NOT_STOCKING_RATE_OR_AVAILABLE_FORAGE",
    "ACCESS_INFRASTRUCTURE_EXCLUDED_FROM_NATURAL_PROFILE",
    "ENVIRONMENTALLY_CONSTRAINED_REQUIRES_APPROVED_HARD_CONSTRAINT",
)

_INFRA_MARKERS: tuple[str, ...] = (
    "road",
    "access",
    "fence",
    "corral",
    "power",
    "building",
    "structure",
    "title",
    "easement",
    "f07",
    "obs_road",
    "nearest_mapped_road",
)


class NaturalCattleProfileError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


@lru_cache(maxsize=1)
def load_natural_cattle_profile_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_natural_cattle_profile(
    profile: Mapping[str, Any],
    *,
    packet: Mapping[str, Any] | None = None,
) -> None:
    Draft202012Validator(load_natural_cattle_profile_schema()).validate(profile)
    if profile.get("profile_hash") != compute_natural_cattle_profile_hash(profile):
        raise NaturalCattleProfileError(
            "profile_hash_mismatch",
            "stored profile_hash does not match semantic hash",
        )
    overall = profile.get("overall_natural_foundation") or {}
    if overall.get("status") == STATUS_CONSTRAINED:
        rule_id = overall.get("approved_hard_constraint_rule_id")
        if not rule_id or rule_id not in APPROVED_HARD_CONSTRAINT_RULES:
            raise NaturalCattleProfileError(
                "constrained_without_approved_rule",
                "ENVIRONMENTALLY_CONSTRAINED requires an approved hard-constraint rule",
            )

    _validate_limitation_not_fact(profile)

    if packet is not None:
        _validate_refs_against_packet(profile, packet)


def packet_evidence_index(packet: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Index Combined Packet observations by observation_id (all rows, incl. failures)."""
    index: dict[str, dict[str, Any]] = {}
    for key in ("mireye_observations", "core_observations", "supplement_observations"):
        for obs in packet.get(key) or []:
            if not isinstance(obs, Mapping):
                continue
            oid = str(obs.get("observation_id") or "").strip()
            if oid:
                index[oid] = dict(obs)
    return index


def _eligible_support_obs(obs: Mapping[str, Any]) -> bool:
    return _usable_status(str(obs.get("status"))) and obs.get("value") is not None


def _validate_refs_against_packet(
    profile: Mapping[str, Any],
    packet: Mapping[str, Any],
) -> None:
    index = packet_evidence_index(packet)
    overall = profile.get("overall_natural_foundation") or {}
    profile_packet_hash = str(profile.get("packet_hash") or "")
    packet_hash = str(packet.get("packet_hash") or "")
    if profile_packet_hash and packet_hash and profile_packet_hash != packet_hash:
        raise NaturalCattleProfileError(
            "packet_hash_mismatch",
            "profile packet_hash does not match the Combined Packet under validation",
        )

    def require_support_ref(ref: str, *, context: str) -> None:
        obs = index.get(ref)
        if obs is None:
            raise NaturalCattleProfileError(
                "dangling_supporting_ref",
                f"{context} references missing evidence id {ref!r}",
            )
        if not _eligible_support_obs(obs):
            raise NaturalCattleProfileError(
                "ineligible_supporting_ref",
                f"{context} references non-supporting evidence {ref!r} "
                f"(status={obs.get('status')!r})",
            )

    for row in profile.get("domains") or []:
        domain = row.get("domain")
        for ref in row.get("supporting_refs") or []:
            require_support_ref(str(ref), context=f"domain {domain} supporting_refs")
        for ref in row.get("conflict_refs") or []:
            if str(ref) not in index:
                raise NaturalCattleProfileError(
                    "dangling_conflict_ref",
                    f"domain {domain} conflict_refs references missing evidence id {ref!r}",
                )

    for ref in overall.get("supporting_refs") or []:
        require_support_ref(str(ref), context="overall_natural_foundation.supporting_refs")

    controlling = overall.get("controlling_factor") or {}
    for ref in controlling.get("supporting_refs") or []:
        require_support_ref(
            str(ref),
            context="overall_natural_foundation.controlling_factor.supporting_refs",
        )
    if controlling.get("resolved") and not controlling.get("domain"):
        raise NaturalCattleProfileError(
            "controlling_factor_unresolved_shape",
            "resolved controlling_factor must name a domain",
        )
    if controlling.get("resolved") and controlling.get("domain"):
        domain_row = next(
            (
                row
                for row in (profile.get("domains") or [])
                if row.get("domain") == controlling.get("domain")
            ),
            None,
        )
        if domain_row is None:
            raise NaturalCattleProfileError(
                "controlling_factor_unknown_domain",
                f"controlling_factor domain {controlling.get('domain')!r} missing from profile",
            )
        expected = list(domain_row.get("supporting_refs") or [])
        actual = list(controlling.get("supporting_refs") or [])
        if actual != expected:
            raise NaturalCattleProfileError(
                "controlling_factor_refs_mismatch",
                "controlling_factor.supporting_refs must equal the controlling domain reading refs",
            )


def _validate_limitation_not_fact(profile: Mapping[str, Any]) -> None:
    """Limitations and unavailable coverage cannot author land facts or constrained status."""
    overall = profile.get("overall_natural_foundation") or {}
    forbidden_fact_phrases = (
        "no water on the parcel",
        "parcel has no water",
        "lacks forage",
        "no forage available",
        "soil is unsuitable",
        "terrain is unsuitable",
        "environmentally constrained because evidence is missing",
        "environmentally constrained because source_unavailable",
    )
    for row in profile.get("domains") or []:
        blob = " ".join(
            [str(row.get("reading") or "")]
            + [str(x) for x in (row.get("limitations") or [])]
        ).lower()
        for phrase in forbidden_fact_phrases:
            if phrase in blob:
                raise NaturalCattleProfileError(
                    "limitation_impersonating_fact",
                    f"domain {row.get('domain')} text asserts prohibited land fact: {phrase!r}",
                )
        # SOURCE_UNAVAILABLE / missing coverage cannot appear as supporting evidence.
        if row.get("confidence") == CONF_INSUFFICIENT and row.get("supporting_refs"):
            raise NaturalCattleProfileError(
                "insufficient_with_supporting_refs",
                f"domain {row.get('domain')} is INSUFFICIENT but still lists supporting_refs",
            )

    if overall.get("status") == STATUS_CONSTRAINED:
        # Extra belt: constrained must never be implied solely by limitations text.
        lim_blob = " ".join(str(x) for x in (overall.get("limitations") or [])).lower()
        if "missing" in lim_blob and "approved hard-constraint" not in lim_blob:
            # Soft: only fail if no rule id (already checked) — keep explicit.
            pass

    # Limitations must never be copied into supporting_refs.
    limitation_texts = set()
    for row in profile.get("domains") or []:
        limitation_texts.update(str(x) for x in (row.get("limitations") or []))
    limitation_texts.update(str(x) for x in (overall.get("limitations") or []))
    for ref in overall.get("supporting_refs") or []:
        if str(ref) in limitation_texts:
            raise NaturalCattleProfileError(
                "limitation_used_as_supporting_ref",
                "limitations cannot independently create supporting evidence refs",
            )


def compute_natural_cattle_profile_hash(profile: Mapping[str, Any]) -> str:
    """Hash semantic content only — exclude timestamps and the hash field itself."""
    payload = copy.deepcopy(dict(profile))
    payload.pop("profile_hash", None)
    provenance = payload.get("provenance")
    if isinstance(provenance, dict):
        payload["provenance"] = {
            key: value for key, value in provenance.items() if key != "built_at"
        }
    # Normalize list order so observation/packet ordering cannot drift the hash.
    for row in payload.get("domains") or []:
        if isinstance(row, dict):
            row["supporting_refs"] = sorted(row.get("supporting_refs") or [])
            row["conflict_refs"] = sorted(row.get("conflict_refs") or [])
            row["limitations"] = list(row.get("limitations") or [])
    overall = payload.get("overall_natural_foundation")
    if isinstance(overall, dict):
        overall["supporting_refs"] = sorted(overall.get("supporting_refs") or [])
        overall["evidence_needed"] = list(overall.get("evidence_needed") or [])
        controlling = overall.get("controlling_factor")
        if isinstance(controlling, dict):
            controlling["supporting_refs"] = sorted(
                controlling.get("supporting_refs") or []
            )
    return sha256_canonical(payload)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_infrastructure_observation(obs: Mapping[str, Any]) -> bool:
    domain = str(obs.get("domain") or "").upper()
    if domain and domain not in DOMAIN_ORDER:
        return True
    blob = " ".join(
        [
            str(obs.get("field_id") or ""),
            str(obs.get("observation_id") or ""),
            str(obs.get("factor_id") or ""),
            str(obs.get("supplement_tool_id") or ""),
            str(obs.get("notes") or ""),
        ]
    ).lower()
    return any(marker in blob for marker in _INFRA_MARKERS)


def _iter_packet_observations(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("mireye_observations", "core_observations", "supplement_observations"):
        for obs in packet.get(key) or []:
            if not isinstance(obs, Mapping):
                continue
            if _is_infrastructure_observation(obs):
                continue
            domain = str(obs.get("domain") or "")
            if domain not in DOMAIN_ORDER:
                continue
            rows.append(dict(obs))
    return rows


def _usable_status(status: str | None) -> bool:
    return status in {"RETRIEVED", "PARTIAL"}


def _obs_ref(obs: Mapping[str, Any]) -> str:
    return str(obs.get("observation_id") or obs.get("field_id") or "")


def _spatial(obs: Mapping[str, Any]) -> str:
    return str(obs.get("spatial_semantics") or "").upper()


def project_domain_reading(
    domain: str,
    observations: Sequence[Mapping[str, Any]],
    *,
    conflicts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    domain_obs = [obs for obs in observations if obs.get("domain") == domain]
    retrieved = [
        obs
        for obs in domain_obs
        if _usable_status(str(obs.get("status"))) and obs.get("value") is not None
    ]
    unavailable = [
        obs for obs in domain_obs if obs.get("status") == "SOURCE_UNAVAILABLE"
    ]
    parcel = [obs for obs in retrieved if _spatial(obs) == "PARCEL"]
    point = [obs for obs in retrieved if _spatial(obs) == "POINT"]
    context = [obs for obs in retrieved if _spatial(obs) == "CONTEXT"]

    domain_comparisons = [
        row for row in conflicts if str(row.get("domain") or "") == domain
    ]
    scale_differences = [
        row
        for row in domain_comparisons
        if str(row.get("kind") or "") == "SPATIAL_SCALE_DIFFERENCE"
        or row.get("affects_domain_confidence") is False
    ]
    domain_conflicts = [
        row for row in domain_comparisons if row not in scale_differences
    ]
    conflict_refs: list[str] = []
    for row in domain_conflicts:
        for key in ("mireye_ref", "supplement_ref"):
            ref = row.get(key)
            if ref:
                conflict_refs.append(str(ref))
    conflict_refs = sorted(set(conflict_refs))

    supporting_refs = sorted({_obs_ref(obs) for obs in retrieved if _obs_ref(obs)})
    limitations: list[str] = []

    if point or context:
        limitations.append(
            "POINT/CONTEXT evidence retained with original spatial semantics; "
            "not promoted to PARCEL facts"
        )
    if scale_differences:
        limitations.append(
            "POINT and PARCEL values describe different spatial scales; their "
            "difference is expected and is not treated as a land defect or source conflict"
        )
    if unavailable:
        limitations.append(
            "SOURCE_UNAVAILABLE lowers confidence only; it is not a negative natural fact"
        )
        if domain == DOMAIN_WATER:
            limitations.append(
                "Missing or unavailable water evidence is not evidence of no water"
            )
    if domain_conflicts:
        limitations.append(
            "Conflicting multi-provider or cross-semantics evidence kept side-by-side; "
            "projector does not pick a preferred value"
        )
    if domain == DOMAIN_FEED:
        limitations.append(
            "RAP/NDVI signals are not stocking rate, AUM, or available forage quantity"
        )
    if not retrieved:
        limitations.append("No retrieved natural evidence for this domain in the Combined Packet")

    if parcel and not domain_conflicts and not unavailable:
        confidence = CONF_HIGH if len(parcel) >= 2 else CONF_MEDIUM
    elif parcel and (domain_conflicts or unavailable):
        confidence = CONF_MEDIUM if len(parcel) >= 1 else CONF_LOW
    elif retrieved:
        confidence = CONF_LOW
    else:
        confidence = CONF_INSUFFICIENT

    reading = _domain_reading_text(
        domain=domain,
        parcel_count=len(parcel),
        point_count=len(point),
        context_count=len(context),
        unavailable_count=len(unavailable),
        conflict_count=len(domain_conflicts),
        confidence=confidence,
    )

    return {
        "domain": domain,
        "buyer_label": BUYER_LABELS[domain],
        "reading": reading,
        "supporting_refs": supporting_refs,
        "limitations": limitations,
        "confidence": confidence,
        "evidence_classes": {
            "parcel_count": len(parcel),
            "point_count": len(point),
            "context_count": len(context),
            "unavailable_count": len(unavailable),
            "conflict_count": len(domain_conflicts),
        },
        "conflict_refs": conflict_refs,
    }


def _domain_reading_text(
    *,
    domain: str,
    parcel_count: int,
    point_count: int,
    context_count: int,
    unavailable_count: int,
    conflict_count: int,
    confidence: str,
) -> str:
    label = BUYER_LABELS[domain]
    if confidence == CONF_INSUFFICIENT:
        if domain == DOMAIN_WATER:
            return (
                f"{label}: insufficient retrieved water evidence in the Combined Packet. "
                "This does not establish that the parcel lacks water."
            )
        return (
            f"{label}: insufficient retrieved natural evidence in the Combined Packet "
            "to support a domain foundation reading."
        )

    parts = [
        f"{label}: Combined Packet retains "
        f"{parcel_count} PARCEL, {point_count} POINT, and {context_count} CONTEXT "
        f"retrieved observation(s)"
    ]
    if unavailable_count:
        parts.append(
            f"{unavailable_count} SOURCE_UNAVAILABLE row(s) reduce confidence only"
        )
    if conflict_count:
        parts.append(
            f"{conflict_count} unresolved conflict(s) kept without value selection"
        )
    if parcel_count == 0 and (point_count or context_count):
        parts.append("no parcel-wide facts are claimed from POINT/CONTEXT alone")
    if domain == DOMAIN_FEED:
        parts.append("no stocking rate or available-forage quantity is inferred")
    return ". ".join(parts) + "."


def evaluate_hard_constraints(
    packet: Mapping[str, Any],
    domain_readings: Sequence[Mapping[str, Any]],
) -> str | None:
    """Return approved rule id when triggered. Registry is currently empty."""
    del packet, domain_readings
    for rule_id, rule in sorted(APPROVED_HARD_CONSTRAINT_RULES.items()):
        predicate = rule.get("predicate")
        if callable(predicate) and predicate():
            return rule_id
    return None


def _select_controlling_factor(
    domain_readings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    eligible = [
        row
        for row in domain_readings
        if row.get("supporting_refs")
        or int((row.get("evidence_classes") or {}).get("conflict_count") or 0) > 0
        or row.get("confidence") != CONF_INSUFFICIENT
    ]
    # Prefer factors that still have supporting evidence when resolving.
    with_refs = [row for row in domain_readings if row.get("supporting_refs")]
    if not with_refs and not any(
        int((row.get("evidence_classes") or {}).get("conflict_count") or 0) > 0
        for row in domain_readings
    ):
        return {
            "domain": None,
            "reason": "no eligible controlling factor remains after evidence withdrawal",
            "supporting_refs": [],
            "resolved": False,
        }

    by_domain = {row["domain"]: row for row in domain_readings}

    conflicted = [
        row
        for row in domain_readings
        if int(row["evidence_classes"]["conflict_count"]) > 0 and row.get("supporting_refs")
    ]
    if conflicted:
        conflicted.sort(
            key=lambda row: (
                0 if row["domain"] == DOMAIN_WATER else 1,
                CONF_RANK[row["confidence"]],
                DOMAIN_ORDER.index(row["domain"]),
            )
        )
        chosen = conflicted[0]
        return {
            "domain": chosen["domain"],
            "reason": "unresolved multi-source or cross-semantics conflict in Combined Packet",
            "supporting_refs": list(chosen.get("supporting_refs") or []),
            "resolved": True,
        }

    water = by_domain[DOMAIN_WATER]
    if water.get("supporting_refs") and water["confidence"] in {
        CONF_INSUFFICIENT,
        CONF_LOW,
    }:
        return {
            "domain": DOMAIN_WATER,
            "reason": "water evidence is incomplete or only weakly parcel-grounded",
            "supporting_refs": list(water.get("supporting_refs") or []),
            "resolved": True,
        }

    pool = with_refs or eligible
    ranked = sorted(
        pool,
        key=lambda row: (
            CONF_RANK[row["confidence"]],
            DOMAIN_ORDER.index(row["domain"]),
        ),
    )
    chosen = ranked[0]
    return {
        "domain": chosen["domain"],
        "reason": f"lowest domain confidence ({chosen['confidence']})",
        "supporting_refs": list(chosen.get("supporting_refs") or []),
        "resolved": True,
    }


def _overall_status(
    domain_readings: Sequence[Mapping[str, Any]],
    *,
    hard_constraint_rule_id: str | None,
) -> str:
    if hard_constraint_rule_id:
        return STATUS_CONSTRAINED

    usable = [
        row
        for row in domain_readings
        if row["confidence"] != CONF_INSUFFICIENT and row["supporting_refs"]
    ]
    parcel_backed = [
        row
        for row in domain_readings
        if int(row["evidence_classes"]["parcel_count"]) > 0
        and row["confidence"] in {CONF_HIGH, CONF_MEDIUM}
    ]
    conflicted = any(
        int(row["evidence_classes"]["conflict_count"]) > 0 for row in domain_readings
    )
    point_only_gaps = any(
        int(row["evidence_classes"]["parcel_count"]) == 0
        and (
            int(row["evidence_classes"]["point_count"])
            + int(row["evidence_classes"]["context_count"])
        )
        > 0
        for row in domain_readings
    )
    unavailable_pressure = any(
        int(row["evidence_classes"]["unavailable_count"]) > 0 for row in domain_readings
    )

    if len(usable) < 2:
        return STATUS_INSUFFICIENT
    if (
        len(parcel_backed) >= 3
        and not conflicted
        and not point_only_gaps
        and not unavailable_pressure
        and all(row["confidence"] != CONF_INSUFFICIENT for row in domain_readings)
    ):
        return STATUS_PROMISING
    return STATUS_CONDITIONAL


def _overall_texts(
    *,
    status: str,
    controlling: Mapping[str, Any],
    domain_readings: Sequence[Mapping[str, Any]],
) -> tuple[str, str, str, list[str], list[str]]:
    if controlling.get("resolved") and controlling.get("domain"):
        ctrl_label = BUYER_LABELS[str(controlling["domain"])]
        ctrl_phrase = f"Controlling factor: {ctrl_label} ({controlling['reason']})."
    else:
        ctrl_label = "unresolved"
        ctrl_phrase = (
            "Controlling factor is unresolved because required supporting evidence "
            "was withdrawn."
        )
    insufficient_domains = [
        BUYER_LABELS[row["domain"]]
        for row in domain_readings
        if row["confidence"] == CONF_INSUFFICIENT
    ]
    evidence_needed: list[str] = []
    for row in domain_readings:
        classes = row["evidence_classes"]
        if classes["parcel_count"] == 0:
            evidence_needed.append(
                f"parcel-wide {BUYER_LABELS[row['domain']].lower()} evidence"
            )
        if classes["unavailable_count"] > 0:
            evidence_needed.append(
                f"retry or alternate source for unavailable {BUYER_LABELS[row['domain']].lower()} rows"
            )
        if classes["conflict_count"] > 0:
            evidence_needed.append(
                f"field or source reconciliation for {BUYER_LABELS[row['domain']].lower()} conflicts"
            )

    limitations = [
        "Directional natural-foundation status only; not stocking, legal, access, or purchase advice",
        "POINT/CONTEXT observations are never promoted to PARCEL facts",
        "SOURCE_UNAVAILABLE and missing water evidence do not create negative natural facts",
    ]
    if insufficient_domains:
        limitations.append(
            "Insufficient domains: " + ", ".join(insufficient_domains)
        )

    if status == STATUS_PROMISING:
        headline = "Promising natural foundation with unverified local operating details"
        judgment = (
            "Multiple domains retain parcel-grounded natural evidence. " + ctrl_phrase
        )
        confidence = CONF_MEDIUM
    elif status == STATUS_CONDITIONAL:
        headline = "Conditional natural foundation pending stronger parcel evidence"
        judgment = (
            "Natural evidence is mixed across semantics, conflicts, or gaps. "
            + ctrl_phrase
        )
        confidence = CONF_LOW
    elif status == STATUS_CONSTRAINED:
        headline = "Environmentally constrained by approved natural hard-constraint evidence"
        judgment = (
            "An approved hard-constraint rule fired on complete applicable PARCEL evidence. "
            + ctrl_phrase
        )
        confidence = CONF_HIGH
    else:
        headline = "Insufficient environmental evidence for a natural-foundation view"
        judgment = (
            "Too little retrieved natural evidence remains after Combined Packet projection. "
            + ctrl_phrase
            + " Missing evidence is not a negative natural conclusion."
        )
        confidence = CONF_INSUFFICIENT

    # Stable unique order.
    evidence_needed = list(dict.fromkeys(evidence_needed))
    return headline, judgment, confidence, limitations, evidence_needed


def project_natural_cattle_profile(
    packet: Mapping[str, Any],
    *,
    built_at: str | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Project Combined Environmental Evidence Packet into Natural Cattle Profile."""
    if not isinstance(packet, Mapping):
        raise NaturalCattleProfileError("invalid_packet", "packet must be an object")
    parcel_ref = packet.get("parcel_ref")
    if not isinstance(parcel_ref, Mapping) or not parcel_ref.get("confirmed"):
        raise NaturalCattleProfileError(
            "parcel_not_confirmed",
            "Natural Cattle Profile requires confirmed parcel_ref",
        )

    observations = _iter_packet_observations(packet)
    conflicts = [
        dict(row) for row in (packet.get("conflicts") or []) if isinstance(row, Mapping)
    ]

    domain_readings = [
        project_domain_reading(domain, observations, conflicts=conflicts)
        for domain in DOMAIN_ORDER
    ]

    hard_rule = evaluate_hard_constraints(packet, domain_readings)
    status = _overall_status(domain_readings, hard_constraint_rule_id=hard_rule)
    controlling = _select_controlling_factor(domain_readings)
    headline, judgment, overall_conf, limitations, evidence_needed = _overall_texts(
        status=status,
        controlling=controlling,
        domain_readings=domain_readings,
    )

    supporting_refs: list[str] = []
    for row in domain_readings:
        supporting_refs.extend(row["supporting_refs"])
    supporting_refs = sorted(set(supporting_refs))

    profile: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "projector_id": PROJECTOR_ID,
        "run_id": str(packet.get("run_id") or ""),
        "parcel_ref": {
            "parcel_resolution_id": str(parcel_ref.get("parcel_resolution_id") or ""),
            "geometry_hash": str(parcel_ref.get("geometry_hash") or ""),
            "confirmed": True,
        },
        "packet_hash": str(packet.get("packet_hash") or ""),
        "plan_hash": packet.get("plan_hash"),
        "domains": domain_readings,
        "overall_natural_foundation": {
            "status": status,
            "headline": headline,
            "judgment": judgment,
            "controlling_factor": controlling,
            "supporting_refs": supporting_refs,
            "limitations": limitations,
            "evidence_needed": evidence_needed,
            "confidence": overall_conf,
            "approved_hard_constraint_rule_id": hard_rule,
        },
        "prohibited_inferences": list(PROHIBITED_INFERENCES),
        "provenance": {
            "built_at": built_at or _utc_now(),
            "llm_authored": False,
            "hard_constraint_registry_size": len(APPROVED_HARD_CONSTRAINT_RULES),
            "notes": [
                "Deterministic projector only; LLM may explain later but cannot author Profile",
                "Access/infrastructure observations excluded under HUMAN_ACCESS_INFRA_APPENDIX_ONLY",
            ],
        },
    }
    profile["profile_hash"] = compute_natural_cattle_profile_hash(profile)
    if validate:
        validate_natural_cattle_profile(profile, packet=packet)
    return profile


def withdraw_observation_and_reproject(
    packet: Mapping[str, Any],
    *,
    observation_id: str,
    validate: bool = True,
) -> dict[str, Any]:
    """Gate helper: remove one observation and reproject (evidence withdrawal)."""
    mutated = copy.deepcopy(dict(packet))
    for key in ("mireye_observations", "core_observations", "supplement_observations"):
        rows = mutated.get(key) or []
        mutated[key] = [
            row
            for row in rows
            if not (
                isinstance(row, Mapping)
                and str(row.get("observation_id") or "") == observation_id
            )
        ]
    # Drop conflict rows that referenced the withdrawn observation.
    mutated["conflicts"] = [
        row
        for row in (mutated.get("conflicts") or [])
        if observation_id
        not in {
            str(row.get("mireye_ref") or ""),
            str(row.get("supplement_ref") or ""),
        }
    ]
    return project_natural_cattle_profile(mutated, validate=validate)
