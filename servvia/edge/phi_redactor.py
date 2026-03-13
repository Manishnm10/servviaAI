"""
ServVia Edge — PHI De-identification
======================================

Local-only Protected Health Information (PHI) redaction using
Microsoft Presidio. All processing runs on-device — no PHI
ever leaves the user's machine.

Masked entities (identity-linked only):
    PERSON, PHONE_NUMBER, EMAIL_ADDRESS

Intentionally NOT masked (clinically relevant):
    DATE_TIME  — age/DOB needed for reference-range interpretation
    LOCATION   — country/region may affect normal ranges

Replacement format:
    "Dr. Ramesh Kumar" -> "[PERSON_1]"
    "ramesh@email.com" -> "[EMAIL_1]"
    "+91 98765 43210"  -> "[PHONE_1]"
"""

import logging
import re
from typing import Dict, List, Optional

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

logger = logging.getLogger("ServVia.Edge.PHI")

# Entity types to detect and redact — identity-linked only.
# DATE_TIME and LOCATION are intentionally excluded so the LLM
# can use age/DOB and regional context when interpreting results.
_TARGET_ENTITIES = [
    "PERSON",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
]

# Lab units that commonly follow numeric values in reports.
# If a "phone number" is followed by one of these, it's a lab value.
_LAB_UNIT_PATTERN = re.compile(
    r"^\s*(mg/d[Ll]|g/d[Ll]|g/[Ll]|mmol/[Ll]|mEq/[Ll]|[UIu]/[Ll]|IU/[Ll]|"
    r"ng/m[Ll]|pg/m[Ll]|µg/d[Ll]|ug/d[Ll]|cells/[µu][Ll]|"
    r"%|mm/hr|seconds?|f[Ll]|pg|x\s*10|mill(?:ion)?/[cmu]|"
    r"thou(?:sand)?/[cmu]|lakhs?/[cmu]|mg/dl|gm/dl|gm%)",
    re.IGNORECASE,
)


class PHIRedactor:
    """De-identify Protected Health Information from lab report text."""

    def __init__(self, language: str = "en"):
        """
        Initialize Presidio engines with spaCy NLP backend.

        Args:
            language: Language code for the NLP engine (default: "en").
                      Requires spaCy model en_core_web_lg to be installed.
        """
        self._language = language
        self._analyzer = AnalyzerEngine()
        self._anonymizer = AnonymizerEngine()

        # Counters for sequential placeholder naming per entity type
        self._entity_counters: Dict[str, int] = {}

        logger.info("PHIRedactor initialized with Presidio + spaCy NLP engine")

    def _filter_false_positive_phones(
        self, text: str, results: List[RecognizerResult]
    ) -> List[RecognizerResult]:
        """
        Remove PHONE_NUMBER detections that are actually lab values.

        Lab reports are full of short digit sequences (e.g., "168", "4.5",
        "14500") that Presidio's PhoneRecognizer flags as phone numbers.
        Real phone numbers in report headers have 7+ digits and high
        confidence scores.
        """
        filtered = []
        for r in results:
            if r.entity_type == "PHONE_NUMBER":
                matched_text = text[r.start : r.end].strip()
                digit_count = sum(c.isdigit() for c in matched_text)

                # Real phone numbers have at least 7 digits
                if digit_count < 7:
                    logger.debug(
                        f"Filtered false-positive PHONE: '{matched_text}' "
                        f"({digit_count} digits, score={r.score:.2f})"
                    )
                    continue

                # Low-confidence detections in a lab report context
                if r.score < 0.5:
                    continue

                # Check if followed by lab measurement units
                after_text = text[r.end : r.end + 25]
                if _LAB_UNIT_PATTERN.match(after_text):
                    logger.debug(
                        f"Filtered false-positive PHONE near unit: '{matched_text}'"
                    )
                    continue

            filtered.append(r)
        return filtered

    def anonymize_text(self, raw_text: str) -> str:
        """
        Detect and mask PHI entities in the input text.

        Args:
            raw_text: Raw lab report text (may contain patient names,
                      phone numbers, emails, addresses, dates).

        Returns:
            Anonymized text with identity PHI replaced by placeholders like
            [PERSON_1], [PHONE_1], [EMAIL_1].
            Dates and locations are preserved for clinical context.
        """
        if not raw_text or not raw_text.strip():
            return raw_text

        # Reset counters for each anonymization call
        self._entity_counters = {}

        # Step 1: Detect PHI entities
        results: List[RecognizerResult] = self._analyzer.analyze(
            text=raw_text,
            entities=_TARGET_ENTITIES,
            language=self._language,
        )

        # Step 2: Filter false-positive phone numbers (lab values)
        results = self._filter_false_positive_phones(raw_text, results)

        if not results:
            logger.info("No PHI entities detected in text")
            return raw_text

        logger.info(
            f"Detected {len(results)} PHI entities: "
            f"{[r.entity_type for r in results]}"
        )

        # Step 3: Build operator config with sequential placeholders
        operators = self._build_operators(results)

        # Step 4: Anonymize
        anonymized = self._anonymizer.anonymize(
            text=raw_text,
            analyzer_results=results,
            operators=operators,
        )

        logger.info(
            f"Anonymized {len(results)} PHI entities "
            f"({len(raw_text)} -> {len(anonymized.text)} chars)"
        )
        return anonymized.text

    def _build_operators(
        self, results: List[RecognizerResult]
    ) -> Dict[str, OperatorConfig]:
        """Build Presidio operator configs for placeholder replacement."""
        # Map entity types to short placeholder labels
        label_map = {
            "PERSON": "PERSON",
            "PHONE_NUMBER": "PHONE",
            "EMAIL_ADDRESS": "EMAIL",
        }

        operators = {}
        for entity_type in set(r.entity_type for r in results):
            label = label_map.get(entity_type, entity_type)
            count = self._entity_counters.get(entity_type, 0) + 1
            self._entity_counters[entity_type] = count
            placeholder = f"[{label}_{count}]"

            operators[entity_type] = OperatorConfig(
                "replace", {"new_value": placeholder}
            )

        return operators
