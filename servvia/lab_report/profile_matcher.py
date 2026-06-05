"""
Patient Profile Matcher — Fuzzy Identity Resolution
====================================================

Compares an IdentityFingerprint (extracted from a new lab report) against
existing PatientProfiles to determine routing.

Matching tiers:
    1. Exact external ID match (SRF/UHID/MRN)     → confidence 1.0
    2. Fuzzy name + age match                       → confidence 0.9
    3. Fuzzy name only                              → confidence 0.6
    4. No match                                     → confidence 0.0

Threshold:
    >= 0.8  → auto-assign
    <  0.8  → human-in-the-loop
"""

import logging
from typing import List, Optional, Tuple

from thefuzz import fuzz

from edge.identity_extractor import IdentityFingerprint
from lab_report.models import PatientProfile

logger = logging.getLogger("ServVia.LabReport.ProfileMatcher")

AUTO_ASSIGN_THRESHOLD = 0.8


def match_profile(
    fingerprint: IdentityFingerprint,
    profiles: List[PatientProfile],
) -> Tuple[Optional[PatientProfile], float, List[dict]]:
    """
    Match an identity fingerprint against a list of patient profiles.

    Returns:
        (best_match_profile, confidence, candidates_list)

        candidates_list contains all profiles with confidence > 0,
        sorted descending by confidence, for human-in-the-loop display.
    """
    if not profiles:
        return None, 0.0, []

    candidates = []

    for profile in profiles:
        score = _score_match(fingerprint, profile)
        if score > 0.0:
            candidates.append({
                "profile_id": profile.id,
                "label": profile.label,
                "patient_name": profile.patient_name,
                "age": profile.age,
                "sex": profile.sex,
                "confidence": round(score, 2),
            })

    candidates.sort(key=lambda c: c["confidence"], reverse=True)

    if not candidates:
        return None, 0.0, []

    best = candidates[0]
    best_profile = next(p for p in profiles if p.id == best["profile_id"])

    logger.info(
        f"Best match: '{best['label']}' (confidence={best['confidence']}) "
        f"for fingerprint name='{fingerprint.patient_name}'"
    )

    return best_profile, best["confidence"], candidates


def _score_match(fp: IdentityFingerprint, profile: PatientProfile) -> float:
    """Score how well a fingerprint matches a profile (0.0 to 1.0)."""

    # ── Tier 1: Exact ID match ──
    if fp.patient_id and profile.external_ids:
        for key, stored_id in profile.external_ids.items():
            if stored_id and fp.patient_id.strip().upper() == str(stored_id).strip().upper():
                return 1.0

    if fp.srf_id and profile.external_ids:
        stored_srf = profile.external_ids.get("SRF_ID", "")
        if stored_srf and fp.srf_id.strip().upper() == str(stored_srf).strip().upper():
            return 1.0

    # ── Tier 2/3: Name matching ──
    if not fp.patient_name or not profile.patient_name:
        return 0.0

    name_ratio = fuzz.token_sort_ratio(
        fp.patient_name.lower(),
        profile.patient_name.lower(),
    ) / 100.0  # thefuzz returns 0-100

    if name_ratio < 0.6:
        return 0.0

    # Name matches — check if age corroborates
    if fp.age is not None and profile.age is not None:
        age_diff = abs(fp.age - profile.age)
        if age_diff <= 2:
            # Strong match: name + age
            return min(0.9, name_ratio + 0.2)
        elif age_diff <= 5:
            # Moderate: name matches but age is off
            return max(0.5, name_ratio - 0.1)
        else:
            # Age mismatch — could be a different person with same name
            return max(0.3, name_ratio - 0.3)

    # Name-only match (no age to verify)
    return min(0.6, name_ratio)


def update_profile_from_fingerprint(
    profile: PatientProfile,
    fingerprint: IdentityFingerprint,
) -> None:
    """
    Enrich a PatientProfile with newly extracted identity data.
    Only fills in blank fields — never overwrites existing data.
    """
    changed = False

    if not profile.patient_name and fingerprint.patient_name:
        profile.patient_name = fingerprint.patient_name
        changed = True

    if profile.age is None and fingerprint.age is not None:
        profile.age = fingerprint.age
        changed = True

    if not profile.sex and fingerprint.sex:
        profile.sex = fingerprint.sex
        changed = True

    if fingerprint.patient_id:
        ids = profile.external_ids or {}
        if "patient_id" not in ids:
            ids["patient_id"] = fingerprint.patient_id
            profile.external_ids = ids
            changed = True

    if fingerprint.srf_id:
        ids = profile.external_ids or {}
        if "SRF_ID" not in ids:
            ids["SRF_ID"] = fingerprint.srf_id
            profile.external_ids = ids
            changed = True

    if changed:
        profile.save()
        logger.info(f"Updated profile '{profile.label}' with new identity data")
