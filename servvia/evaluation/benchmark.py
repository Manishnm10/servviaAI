"""
ServVia Evaluation — Safety Validation Benchmark
=================================================

Loads the synthetic dataset (from dataset_generator.py) and passes every
scenario through the TemporalSafetyValidator. Prints a terminal report
with:
    - True Positive Rate  (unsafe correctly blocked)
    - False Positive Rate (safe incorrectly blocked)
    - Fatal Error Rate    (unsafe incorrectly allowed — MUST be 0%)

Usage:
    # First generate the dataset:
    python -m evaluation.dataset_generator

    # Then run the benchmark:
    python -m evaluation.benchmark
    python -m evaluation.benchmark --dataset evaluation/dataset.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from core.models import MedicationRecord, RemedyProposal, UserMedicalProfile
from neurosymbolic.temporal_validator import TemporalSafetyValidator

# Reference time matching the dataset generator
REFERENCE_TIME = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)


def _parse_datetime(value: Any) -> datetime:
    """Parse a datetime string, handling the trailing 'Z' for Python 3.10."""
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _rebuild_profile(data: Dict[str, Any]) -> UserMedicalProfile:
    """Reconstruct a UserMedicalProfile from its JSON dict."""
    meds = []
    for m in data.get("current_medications", []):
        start = _parse_datetime(m["start_date"])
        end = m.get("end_date")
        if end is not None:
            end = _parse_datetime(end)
        meds.append(
            MedicationRecord(drug_name=m["drug_name"], start_date=start, end_date=end)
        )
    return UserMedicalProfile(
        user_id=data["user_id"],
        allergies=data.get("allergies", []),
        current_medications=meds,
        symptom_onset_hours=data.get("symptom_onset_hours", 0),
    )


def _rebuild_proposal(data: Dict[str, Any]) -> RemedyProposal:
    return RemedyProposal(
        herb_or_remedy_name=data["herb_or_remedy_name"],
        intended_effect=data["intended_effect"],
    )


def run_benchmark(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run the full benchmark and return metrics."""
    validator = TemporalSafetyValidator()

    true_positives = 0   # unsafe correctly blocked (is_safe=False when expected_safe=False)
    false_positives = 0  # safe incorrectly blocked (is_safe=False when expected_safe=True)
    true_negatives = 0   # safe correctly allowed  (is_safe=True when expected_safe=True)
    false_negatives = 0  # unsafe incorrectly allowed (is_safe=True when expected_safe=False) — FATAL

    category_results: Dict[str, Dict[str, int]] = {}
    failures: List[Dict[str, Any]] = []

    start_time = time.perf_counter()

    for scenario in dataset:
        cat = scenario["category"]
        expected_safe = scenario["expected_safe"]

        profile = _rebuild_profile(scenario["profile"])
        proposal = _rebuild_proposal(scenario["proposal"])

        result = validator.validate_remedy(profile, proposal, REFERENCE_TIME)

        if cat not in category_results:
            category_results[cat] = {"correct": 0, "incorrect": 0}

        if result.is_safe == expected_safe:
            # Correct prediction
            if expected_safe:
                true_negatives += 1
            else:
                true_positives += 1
            category_results[cat]["correct"] += 1
        else:
            # Incorrect prediction
            if expected_safe:
                false_positives += 1
            else:
                false_negatives += 1  # FATAL
            category_results[cat]["incorrect"] += 1
            failures.append(
                {
                    "id": scenario["id"],
                    "category": cat,
                    "expected_safe": expected_safe,
                    "actual_safe": result.is_safe,
                    "reason": result.reason,
                }
            )

    elapsed = time.perf_counter() - start_time

    total = len(dataset)
    total_unsafe = true_positives + false_negatives
    total_safe = true_negatives + false_positives

    tpr = true_positives / total_unsafe if total_unsafe else 0.0
    fpr = false_positives / total_safe if total_safe else 0.0
    fatal_rate = false_negatives / total_unsafe if total_unsafe else 0.0

    return {
        "total": total,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "true_negatives": true_negatives,
        "false_negatives": false_negatives,
        "tpr": tpr,
        "fpr": fpr,
        "fatal_error_rate": fatal_rate,
        "category_results": category_results,
        "failures": failures,
        "elapsed_seconds": elapsed,
    }


def print_report(metrics: Dict[str, Any]) -> None:
    """Pretty-print the benchmark report to the terminal."""
    sep = "=" * 62
    print()
    print(sep)
    print("  ServVia Safety Validation Benchmark Report")
    print(sep)
    print(f"  Total scenarios:       {metrics['total']}")
    print(f"  Elapsed:               {metrics['elapsed_seconds']:.3f}s")
    print()
    print("  Confusion Matrix:")
    print(f"    True Positives  (unsafe blocked):    {metrics['true_positives']}")
    print(f"    True Negatives  (safe allowed):      {metrics['true_negatives']}")
    print(f"    False Positives (safe blocked):      {metrics['false_positives']}")
    print(f"    False Negatives (unsafe allowed):    {metrics['false_negatives']}")
    print()
    print(f"  True Positive Rate:    {metrics['tpr']:.2%}")
    print(f"  False Positive Rate:   {metrics['fpr']:.2%}")
    print(f"  Fatal Error Rate:      {metrics['fatal_error_rate']:.2%}", end="")
    if metrics["fatal_error_rate"] == 0.0:
        print("  [PASS]")
    else:
        print("  [FAIL !!!]")
    print()
    print("  Per-Category Breakdown:")
    for cat, counts in sorted(metrics["category_results"].items()):
        total_cat = counts["correct"] + counts["incorrect"]
        acc = counts["correct"] / total_cat if total_cat else 0.0
        print(f"    {cat:15s}  {counts['correct']}/{total_cat}  ({acc:.0%})")

    if metrics["failures"]:
        print()
        print("  FAILURES:")
        for f in metrics["failures"]:
            print(f"    [{f['category']}] {f['id']}: expected_safe={f['expected_safe']}, "
                  f"actual_safe={f['actual_safe']}")
            print(f"      reason: {f['reason'][:120]}...")

    print(sep)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the safety validation benchmark.")
    parser.add_argument(
        "--dataset",
        default=os.path.join(_HERE, "dataset.json"),
        help="Path to the dataset JSON file (default: evaluation/dataset.json)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.dataset):
        print(f"Dataset not found at {args.dataset}")
        print("Run `python -m evaluation.dataset_generator` first.")
        sys.exit(1)

    with open(args.dataset, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    metrics = run_benchmark(dataset)
    print_report(metrics)

    # Exit non-zero if Fatal Error Rate > 0
    if metrics["fatal_error_rate"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
