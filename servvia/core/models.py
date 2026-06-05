"""
ServVia Core Data Models
========================

Strict Pydantic BaseModel classes for type-checked data flow across the
ServVia Neurosymbolic AI Healthcare Platform. These models enforce runtime
validation on all pharmacovigilance-critical data structures.

Design Principles:
    - Immutability by default (frozen=True on safety-critical models)
    - Comprehensive field validation with clear error messages
    - ISO 8601 datetime handling with timezone awareness
    - Explicit Optional types — no implicit None

Author: ServVia Engineering
Version: 1.0.0
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# ENUMERATIONS
# =============================================================================

class SafetyVerdict(str, Enum):
    """Possible outcomes of a safety validation check."""
    SAFE = "safe"
    UNSAFE = "unsafe"
    CAUTION = "caution"  # Not blocked, but flagged for clinician review


class InteractionSeverity(str, Enum):
    """Severity levels for herb-drug interactions."""
    CRITICAL = "critical"   # Immediate danger — hard block
    HIGH = "high"           # Strong contraindication — block with override
    MODERATE = "moderate"   # Caution — warn but allow
    LOW = "low"             # Informational only


# =============================================================================
# MEDICATION & PROFILE MODELS
# =============================================================================

class MedicationRecord(BaseModel):
    """
    A single medication entry in a user's medical history.

    Attributes:
        drug_name: Canonical drug name (e.g., "warfarin", "sertraline").
                   Stored lowercase for deterministic matching.
        start_date: When the patient began taking this medication.
        end_date: When the patient stopped. None means currently active.

    Examples:
        >>> med = MedicationRecord(
        ...     drug_name="sertraline",
        ...     start_date=datetime(2025, 1, 15, tzinfo=timezone.utc),
        ...     end_date=datetime(2026, 2, 10, tzinfo=timezone.utc),
        ... )
        >>> med.is_active
        False
    """

    drug_name: str = Field(
        ...,
        min_length=1,
        description="Canonical drug name, stored lowercase for matching.",
    )
    start_date: datetime = Field(
        ...,
        description="ISO 8601 datetime when medication was started.",
    )
    end_date: Optional[datetime] = Field(
        default=None,
        description="ISO 8601 datetime when medication was stopped. "
                    "None indicates the medication is currently active.",
    )

    @field_validator("drug_name")
    @classmethod
    def normalize_drug_name(cls, v: str) -> str:
        """Lowercase and strip whitespace for deterministic matching."""
        return v.strip().lower()

    @property
    def is_active(self) -> bool:
        """True if the medication has no end_date (patient is still taking it)."""
        return self.end_date is None

    def days_since_last_dose(self, reference_time: Optional[datetime] = None) -> int:
        """
        Calculate days elapsed since the last dose.

        Args:
            reference_time: The point in time to measure from.
                            Defaults to datetime.now(timezone.utc).

        Returns:
            0 if the medication is currently active (no end_date).
            Otherwise, the integer number of days since end_date.
        """
        if self.is_active:
            return 0

        ref = reference_time or datetime.now(timezone.utc)

        # Ensure timezone awareness for comparison
        end = self.end_date
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)

        delta = ref - end
        return max(0, delta.days)


class UserMedicalProfile(BaseModel):
    """
    Complete medical context for a patient, used as input to every
    safety validation check.

    Attributes:
        user_id: Unique patient identifier (email, UUID, etc.)
        allergies: Known allergens, stored lowercase.
        current_medications: Full medication history including stopped meds.
        symptom_onset_hours: Hours since the patient's symptoms started.
                             Used for temporal reasoning about acute conditions.

    Examples:
        >>> profile = UserMedicalProfile(
        ...     user_id="patient@example.com",
        ...     allergies=["penicillin", "shellfish"],
        ...     current_medications=[],
        ...     symptom_onset_hours=6,
        ... )
    """

    user_id: str = Field(
        ...,
        min_length=1,
        description="Unique patient identifier.",
    )
    allergies: List[str] = Field(
        default_factory=list,
        description="Known allergens, stored lowercase for matching.",
    )
    current_medications: List[MedicationRecord] = Field(
        default_factory=list,
        description="Full medication history (active and stopped).",
    )
    symptom_onset_hours: int = Field(
        default=0,
        ge=0,
        description="Hours since symptom onset. 0 = chronic / unknown.",
    )

    @field_validator("allergies")
    @classmethod
    def normalize_allergies(cls, v: List[str]) -> List[str]:
        """Lowercase and strip all allergy entries for matching."""
        return [a.strip().lower() for a in v if a.strip()]

    @property
    def active_medications(self) -> List[MedicationRecord]:
        """Return only medications without an end_date."""
        return [m for m in self.current_medications if m.is_active]

    @property
    def stopped_medications(self) -> List[MedicationRecord]:
        """Return only medications that have been stopped."""
        return [m for m in self.current_medications if not m.is_active]


# =============================================================================
# REMEDY PROPOSAL MODEL
# =============================================================================

class RemedyProposal(BaseModel):
    """
    A proposed herbal or natural remedy to be validated against the
    patient's medical profile before recommendation.

    Attributes:
        herb_or_remedy_name: The herb/supplement being proposed (e.g., "turmeric").
        intended_effect: What the remedy is intended to treat (e.g., "anti-inflammatory").

    Examples:
        >>> proposal = RemedyProposal(
        ...     herb_or_remedy_name="St. John's Wort",
        ...     intended_effect="mood support",
        ... )
    """

    herb_or_remedy_name: str = Field(
        ...,
        min_length=1,
        description="Name of the proposed herb or natural remedy.",
    )
    intended_effect: str = Field(
        ...,
        min_length=1,
        description="Therapeutic goal of the proposed remedy.",
    )

    @field_validator("herb_or_remedy_name")
    @classmethod
    def normalize_remedy_name(cls, v: str) -> str:
        """Lowercase and strip for deterministic matching."""
        return v.strip().lower()


# =============================================================================
# VALIDATION RESULT MODEL
# =============================================================================

class ValidationResult(BaseModel):
    """
    The output of a deterministic safety validation check.

    This is a frozen (immutable) model — once a safety verdict is issued,
    it cannot be modified. This is critical for audit trails.

    Attributes:
        is_safe: Whether the remedy is safe to recommend.
        verdict: Categorical safety outcome (SAFE, UNSAFE, CAUTION).
        confidence_score: Deterministic confidence in the assessment (0.0–1.0).
                          For rule-based checks, this is typically 1.0.
        reason: Human-readable explanation of the safety assessment.
        contraindications: List of specific drug-herb interactions detected.
        washout_days_remaining: If blocked by washout, how many days remain.
    """

    model_config = {"frozen": True}  # Immutable after creation

    is_safe: bool = Field(
        ...,
        description="True if the remedy passes all safety checks.",
    )
    verdict: SafetyVerdict = Field(
        ...,
        description="Categorical safety outcome.",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the assessment (0.0–1.0).",
    )
    reason: str = Field(
        ...,
        description="Human-readable explanation of the safety verdict.",
    )
    contraindications: List[str] = Field(
        default_factory=list,
        description="Specific interactions or allergens detected.",
    )
    washout_days_remaining: Optional[int] = Field(
        default=None,
        ge=0,
        description="Days remaining in washout period, if applicable.",
    )


# =============================================================================
# CHRONOBIOLOGY ENUMERATIONS
# =============================================================================

class CircadianPhase(str, Enum):
    """
    Circadian rhythm phases mapped to physiological states.

    Based on the two-process model of sleep regulation (Borbély, 1982)
    and traditional Ayurvedic dinacharya (daily routine) divisions.
    """
    EARLY_MORNING = "early_morning"           # 04:00–06:59 — Vata (movement, awakening)
    MORNING_ACTIVATION = "morning_activation"  # 07:00–09:59 — Kapha→Pitta transition, cortisol peak
    LATE_MORNING = "late_morning"              # 10:00–11:59 — Peak Pitta, highest cognitive performance
    AFTERNOON_PEAK = "afternoon_peak"          # 12:00–13:59 — Agni (digestive fire) at maximum
    AFTERNOON_SLUMP = "afternoon_slump"        # 14:00–16:59 — Post-prandial dip, Vata rise
    EVENING_ACTIVE = "evening_active"          # 17:00–18:59 — Second wind, Kapha stabilization
    WIND_DOWN = "wind_down"                    # 19:00–21:59 — Kapha phase, melatonin onset
    DEEP_SLEEP = "deep_sleep"                  # 22:00–03:59 — Pitta (metabolic repair), SWS dominant


class SeasonalInfluence(str, Enum):
    """
    Seasonal physiological tendencies from Ayurvedic Ritucharya
    (seasonal regimen), mapped to modern chronobiology concepts.

    Each season influences metabolism, immunity, and dosha balance.
    """
    WINTER_ACCUMULATION = "winter_accumulation"  # Kapha builds; strong agni, heavier foods tolerated
    SPRING_RELEASE = "spring_release"            # Kapha liquefies; detox season, allergy risk
    SUMMER_HEAT = "summer_heat"                  # Pitta dominant; dehydration risk, cooling remedies
    MONSOON_DAMPNESS = "monsoon_dampness"        # Vata aggravation; weak digestion, infection risk
    AUTUMN_TRANSITION = "autumn_transition"       # Pitta residual; inflammatory conditions peak
    LATE_AUTUMN_DRY = "late_autumn_dry"           # Vata dominant; dry skin, joint pain, anxiety


class SleepPressure(str, Enum):
    """
    Estimated homeostatic sleep drive based on time of day.

    Sleep pressure (Process S in Borbély's model) accumulates
    during wakefulness via adenosine buildup.
    """
    LOW = "low"           # Recently woke or early day — alert
    MODERATE = "moderate"  # Mid-to-late day — building
    HIGH = "high"          # Late night or extended wakefulness — strong drive


# =============================================================================
# BIOLOGICAL STATE MODEL
# =============================================================================

class BiologicalState(BaseModel):
    """
    Passively inferred biological context for a user at query time.

    Computed from minimal inputs (local time + optional geolocation)
    without requiring wearable data. Used to contextualize health
    recommendations with circadian and seasonal awareness.

    Attributes:
        local_time: The user's local datetime when the query was made.
        circadian_phase: Current phase in the 24-hour rhythm.
        seasonal_influence: Seasonal physiological tendency.
        sleep_pressure_estimate: Estimated homeostatic sleep drive.
        is_misaligned: True if querying during expected sleep hours
                       (22:00–04:00), indicating insomnia or shift work.
        hemisphere: "northern", "southern", or "equatorial".
        advisory: Optional contextual note for downstream systems.

    Examples:
        >>> state = BiologicalState(
        ...     local_time=datetime(2026, 2, 26, 3, 0),
        ...     circadian_phase=CircadianPhase.DEEP_SLEEP,
        ...     seasonal_influence=SeasonalInfluence.WINTER_ACCUMULATION,
        ...     sleep_pressure_estimate=SleepPressure.HIGH,
        ...     is_misaligned=True,
        ...     hemisphere="northern",
        ...     advisory="User is active during deep sleep phase.",
        ... )
    """

    model_config = {"frozen": True}

    local_time: datetime = Field(
        ...,
        description="User's local datetime at query time.",
    )
    circadian_phase: CircadianPhase = Field(
        ...,
        description="Current circadian rhythm phase.",
    )
    seasonal_influence: SeasonalInfluence = Field(
        ...,
        description="Seasonal physiological tendency based on hemisphere.",
    )
    sleep_pressure_estimate: SleepPressure = Field(
        ...,
        description="Estimated homeostatic sleep drive.",
    )
    is_misaligned: bool = Field(
        ...,
        description="True if user is active during expected sleep hours.",
    )
    hemisphere: str = Field(
        default="northern",
        description="Detected hemisphere: 'northern', 'southern', 'equatorial'.",
    )
    advisory: Optional[str] = Field(
        default=None,
        description="Contextual note for downstream recommendation systems.",
    )
