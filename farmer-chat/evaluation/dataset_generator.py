"""
ServVia Evaluation — Synthetic Dataset Generator
=================================================

Programmatically generates 100 synthetic (UserMedicalProfile, RemedyProposal)
JSON pairs for benchmarking the TemporalSafetyValidator.

Distribution:
    - 25 SAFE           — no interactions, no allergies, clean profile
    - 25 ACTIVE_DRUG    — herb conflicts with a currently active medication
    - 25 WASHOUT        — herb conflicts with a recently stopped medication
                          whose washout period has NOT elapsed
    - 25 ALLERGY        — patient is allergic to the proposed herb

The generator draws from the real INTERACTION_DATABASE and DRUG_CLASS_ALIASES
so that every unsafe scenario is clinically valid and will be caught by the
validator's deterministic rules.

Usage:
    python -m evaluation.dataset_generator          # writes evaluation/dataset.json
    python -m evaluation.dataset_generator --out /tmp/data.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from core.models import MedicationRecord, RemedyProposal, UserMedicalProfile
from neurosymbolic.temporal_validator import (
    DRUG_CLASS_ALIASES,
    INTERACTION_DATABASE,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REFERENCE_TIME = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
SCENARIOS_PER_CATEGORY = 25

# Herbs with NO entries in the interaction database → always safe
SAFE_HERBS = [
    ("chamomile", "sleep support"),
    ("peppermint", "digestive comfort"),
    ("lavender", "relaxation"),
    ("fennel", "bloating relief"),
    ("rosemary", "memory support"),
    ("holy basil", "stress relief"),
    ("cinnamon", "blood sugar support"),
    ("cardamom", "digestive aid"),
    ("lemon balm", "calming"),
    ("dandelion", "liver support"),
    ("hibiscus", "blood pressure support"),
    ("moringa", "nutritional boost"),
    ("neem", "skin health"),
    ("shatavari", "hormonal balance"),
    ("brahmi", "cognitive support"),
    ("aloe vera", "gut soothing"),
    ("fenugreek", "lactation support"),
    ("amla", "immunity boost"),
    ("triphala", "digestive cleanse"),
    ("oregano", "antimicrobial"),
    ("thyme", "respiratory support"),
    ("clove", "dental pain relief"),
    ("sage", "sore throat relief"),
    ("nettle", "allergy relief"),
    ("marshmallow root", "mucosal soothing"),
]

# Reverse map: drug_class → one example generic drug name
_CLASS_TO_DRUG: Dict[str, str] = {}
for _drug, _cls in DRUG_CLASS_ALIASES.items():
    if _cls not in _CLASS_TO_DRUG:
        _CLASS_TO_DRUG[_cls] = _drug


def _build_active_drug_scenarios() -> List[Dict[str, Any]]:
    """25 scenarios where the herb conflicts with an ACTIVE medication."""
    scenarios: List[Dict[str, Any]] = []
    idx = 0

    for herb, rules in INTERACTION_DATABASE.items():
        for rule in rules:
            if idx >= SCENARIOS_PER_CATEGORY:
                break

            drug_name = _CLASS_TO_DRUG.get(rule.drug_class, rule.drug_class)
            profile = UserMedicalProfile(
                user_id=f"active-drug-{idx:03d}",
                allergies=[],
                current_medications=[
                    MedicationRecord(
                        drug_name=drug_name,
                        start_date=REFERENCE_TIME - timedelta(days=90),
                        end_date=None,  # still active
                    )
                ],
            )
            proposal = RemedyProposal(
                herb_or_remedy_name=herb,
                intended_effect="general wellness",
            )
            scenarios.append(
                {
                    "id": f"active-drug-{idx:03d}",
                    "category": "ACTIVE_DRUG",
                    "expected_safe": False,
                    "profile": profile.model_dump(mode="json"),
                    "proposal": proposal.model_dump(mode="json"),
                }
            )
            idx += 1
        if idx >= SCENARIOS_PER_CATEGORY:
            break

    return scenarios


def _build_washout_scenarios() -> List[Dict[str, Any]]:
    """25 scenarios where a drug was recently stopped — washout NOT met."""
    scenarios: List[Dict[str, Any]] = []
    idx = 0

    for herb, rules in INTERACTION_DATABASE.items():
        for rule in rules:
            if idx >= SCENARIOS_PER_CATEGORY:
                break
            if rule.washout_days == 0:
                continue

            drug_name = _CLASS_TO_DRUG.get(rule.drug_class, rule.drug_class)
            # Stop the drug only 1 day ago — well inside the washout window
            profile = UserMedicalProfile(
                user_id=f"washout-{idx:03d}",
                allergies=[],
                current_medications=[
                    MedicationRecord(
                        drug_name=drug_name,
                        start_date=REFERENCE_TIME - timedelta(days=180),
                        end_date=REFERENCE_TIME - timedelta(days=1),
                    )
                ],
            )
            proposal = RemedyProposal(
                herb_or_remedy_name=herb,
                intended_effect="general wellness",
            )
            scenarios.append(
                {
                    "id": f"washout-{idx:03d}",
                    "category": "WASHOUT",
                    "expected_safe": False,
                    "profile": profile.model_dump(mode="json"),
                    "proposal": proposal.model_dump(mode="json"),
                }
            )
            idx += 1
        if idx >= SCENARIOS_PER_CATEGORY:
            break

    return scenarios


def _build_allergy_scenarios() -> List[Dict[str, Any]]:
    """25 scenarios where the patient is allergic to the proposed herb."""
    scenarios: List[Dict[str, Any]] = []
    herbs_in_db = list(INTERACTION_DATABASE.keys())
    # Pad with safe herbs if needed
    all_herbs = herbs_in_db + [h for h, _ in SAFE_HERBS]

    for idx in range(SCENARIOS_PER_CATEGORY):
        herb = all_herbs[idx % len(all_herbs)]
        profile = UserMedicalProfile(
            user_id=f"allergy-{idx:03d}",
            allergies=[herb],  # allergic to the exact herb
            current_medications=[],
        )
        proposal = RemedyProposal(
            herb_or_remedy_name=herb,
            intended_effect="general wellness",
        )
        scenarios.append(
            {
                "id": f"allergy-{idx:03d}",
                "category": "ALLERGY",
                "expected_safe": False,
                "profile": profile.model_dump(mode="json"),
                "proposal": proposal.model_dump(mode="json"),
            }
        )

    return scenarios


def _build_safe_scenarios() -> List[Dict[str, Any]]:
    """25 scenarios that should pass all checks — completely safe."""
    scenarios: List[Dict[str, Any]] = []

    for idx in range(SCENARIOS_PER_CATEGORY):
        herb, effect = SAFE_HERBS[idx % len(SAFE_HERBS)]
        # Give the patient a medication that does NOT conflict with the herb
        profile = UserMedicalProfile(
            user_id=f"safe-{idx:03d}",
            allergies=[],
            current_medications=[
                MedicationRecord(
                    drug_name="acetaminophen",
                    start_date=REFERENCE_TIME - timedelta(days=30),
                    end_date=None,
                )
            ],
        )
        proposal = RemedyProposal(
            herb_or_remedy_name=herb,
            intended_effect=effect,
        )
        scenarios.append(
            {
                "id": f"safe-{idx:03d}",
                "category": "SAFE",
                "expected_safe": True,
                "profile": profile.model_dump(mode="json"),
                "proposal": proposal.model_dump(mode="json"),
            }
        )

    return scenarios


def generate_dataset() -> List[Dict[str, Any]]:
    """Generate the full 100-scenario dataset."""
    dataset: List[Dict[str, Any]] = []
    dataset.extend(_build_safe_scenarios())
    dataset.extend(_build_active_drug_scenarios())
    dataset.extend(_build_washout_scenarios())
    dataset.extend(_build_allergy_scenarios())
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate 100 synthetic safety-validation scenarios."
    )
    parser.add_argument(
        "--out",
        default=os.path.join(_HERE, "dataset.json"),
        help="Output JSON file path (default: evaluation/dataset.json)",
    )
    args = parser.parse_args()

    dataset = generate_dataset()

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, default=str)

    # Summary
    from collections import Counter

    counts = Counter(s["category"] for s in dataset)
    print(f"Generated {len(dataset)} scenarios -> {args.out}")
    for cat, n in sorted(counts.items()):
        print(f"  {cat}: {n}")


if __name__ == "__main__":
    main()
