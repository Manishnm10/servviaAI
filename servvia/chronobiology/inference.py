"""
ServVia Chronobiology Inference Engine
=======================================

Lightweight, deterministic module that estimates a user's biological state
from minimal contextual inputs — local time and optional geolocation.
Requires **NO wearable data** and makes **ZERO LLM calls**.

The engine produces a `BiologicalState` object that downstream systems
(RAG pipeline, response generator, dosing advisor) can use to temporally
contextualize health recommendations.

Theoretical Foundations:
    - **Two-Process Model** (Borbély, 1982): Process C (circadian) and
      Process S (homeostatic sleep pressure).
    - **Ayurvedic Dinacharya**: Traditional Indian daily routine mapped
      to dosha dominance periods (Vata/Pitta/Kapha).
    - **Ritucharya**: Ayurvedic seasonal regimen linking climate to
      physiological tendencies.

Author: ServVia Engineering
Version: 1.0.0
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

from core.models import (
    BiologicalState,
    CircadianPhase,
    SeasonalInfluence,
    SleepPressure,
)

logger = logging.getLogger("ServVia.ChronobiologyEngine")


# =============================================================================
# HEMISPHERE CLASSIFICATION
# =============================================================================

def _classify_hemisphere(latitude: float) -> str:
    """
    Classify hemisphere from latitude.

    Args:
        latitude: Decimal degrees. Positive = North, Negative = South.

    Returns:
        "northern", "southern", or "equatorial" (within ±10° of equator).
    """
    if abs(latitude) <= 10.0:
        return "equatorial"
    return "northern" if latitude > 0 else "southern"


# =============================================================================
# CHRONOBIOLOGY ENGINE
# =============================================================================

class ChronobiologyEngine:
    """
    Deterministic inference engine for passive biological state estimation.

    Computes circadian phase, seasonal influence, sleep pressure, and
    circadian misalignment from local time and optional coordinates.
    All logic is rule-based — no ML models or API calls.

    Usage:
        >>> from datetime import datetime
        >>> engine = ChronobiologyEngine()
        >>> state = engine.infer_state(datetime(2026, 7, 15, 8, 30))
        >>> state.circadian_phase
        <CircadianPhase.MORNING_ACTIVATION: 'morning_activation'>
        >>> state.is_misaligned
        False
    """

    # Default location: Hyderabad, India (17.38°N, 78.49°E)
    DEFAULT_LATITUDE = 17.38
    DEFAULT_LONGITUDE = 78.49

    def __init__(self) -> None:
        """Initialize the engine."""
        logger.info("ChronobiologyEngine initialized (deterministic, zero-LLM)")

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------

    def infer_state(
        self,
        local_time: datetime,
        coordinates: Optional[Tuple[float, float]] = None,
    ) -> BiologicalState:
        """
        Infer the user's biological state from local time and location.

        This is the primary entry point. It computes all four biological
        dimensions and returns a validated Pydantic object.

        Args:
            local_time: The user's local datetime (naive or aware).
                        The time component determines circadian phase.
                        The month determines seasonal influence.
            coordinates: Optional (latitude, longitude) tuple.
                         Used to determine hemisphere for season mapping.
                         Defaults to Hyderabad, India (17.38°N).

        Returns:
            BiologicalState: Frozen Pydantic model with all inferred fields.

        Examples:
            >>> engine = ChronobiologyEngine()
            >>> # Morning query in winter (Northern Hemisphere)
            >>> state = engine.infer_state(
            ...     datetime(2026, 1, 15, 8, 0),
            ...     coordinates=(40.71, -74.01),  # New York
            ... )
            >>> state.circadian_phase.value
            'morning_activation'
            >>> state.seasonal_influence.value
            'winter_accumulation'
        """
        lat, lon = coordinates or (self.DEFAULT_LATITUDE, self.DEFAULT_LONGITUDE)
        hemisphere = _classify_hemisphere(lat)
        hour = local_time.hour
        month = local_time.month

        # Compute each dimension
        phase = self._determine_circadian_phase(hour)
        season = self._determine_seasonal_influence(month, hemisphere)
        pressure = self._determine_sleep_pressure(hour)
        misaligned = self._detect_misalignment(hour)

        # Compose advisory string
        advisory = self._compose_advisory(phase, misaligned, season, hour)

        state = BiologicalState(
            local_time=local_time,
            circadian_phase=phase,
            seasonal_influence=season,
            sleep_pressure_estimate=pressure,
            is_misaligned=misaligned,
            hemisphere=hemisphere,
            advisory=advisory,
        )

        logger.info(
            f"🕐 Inferred state @ {hour:02d}:00 | "
            f"Phase: {phase.value} | Season: {season.value} | "
            f"Pressure: {pressure.value} | Misaligned: {misaligned}"
        )

        return state

    # -------------------------------------------------------------------------
    # PRIVATE: CIRCADIAN PHASE DETERMINATION
    # -------------------------------------------------------------------------

    @staticmethod
    def _determine_circadian_phase(hour: int) -> CircadianPhase:
        """
        Map the local hour to a circadian phase.

        Phase boundaries are based on the cortisol awakening response,
        core body temperature rhythm, and melatonin onset timing.

        Args:
            hour: Hour of day (0–23).

        Returns:
            CircadianPhase enum value.

        Phase Map:
            04–06: EARLY_MORNING    — Cortisol surge, parasympathetic→sympathetic
            07–09: MORNING_ACTIVATION — Peak cortisol, highest alertness
            10–11: LATE_MORNING     — Sustained focus, cognitive peak
            12–13: AFTERNOON_PEAK   — Digestive fire (agni) at maximum
            14–16: AFTERNOON_SLUMP  — Post-prandial dip, adenosine buildup
            17–18: EVENING_ACTIVE   — Second cortisol mini-peak
            19–21: WIND_DOWN        — Dim light melatonin onset (DLMO)
            22–03: DEEP_SLEEP       — Core body temp minimum, SWS dominant
        """
        if 4 <= hour <= 6:
            return CircadianPhase.EARLY_MORNING
        elif 7 <= hour <= 9:
            return CircadianPhase.MORNING_ACTIVATION
        elif 10 <= hour <= 11:
            return CircadianPhase.LATE_MORNING
        elif 12 <= hour <= 13:
            return CircadianPhase.AFTERNOON_PEAK
        elif 14 <= hour <= 16:
            return CircadianPhase.AFTERNOON_SLUMP
        elif 17 <= hour <= 18:
            return CircadianPhase.EVENING_ACTIVE
        elif 19 <= hour <= 21:
            return CircadianPhase.WIND_DOWN
        else:
            # 22–23 and 0–3
            return CircadianPhase.DEEP_SLEEP

    # -------------------------------------------------------------------------
    # PRIVATE: SEASONAL INFLUENCE DETERMINATION
    # -------------------------------------------------------------------------

    @staticmethod
    def _determine_seasonal_influence(
        month: int, hemisphere: str
    ) -> SeasonalInfluence:
        """
        Determine seasonal physiological influence from month and hemisphere.

        Uses Ayurvedic Ritucharya mapping with hemisphere inversion for
        the Southern Hemisphere:

            Northern Hemisphere:
                Dec–Feb: WINTER_ACCUMULATION (Hemanta/Shishira — Kapha builds)
                Mar–Apr: SPRING_RELEASE      (Vasanta — Kapha liquefies)
                May–Jun: SUMMER_HEAT         (Grishma — Pitta rises)
                Jul–Aug: MONSOON_DAMPNESS    (Varsha — Vata aggravation)
                Sep–Oct: AUTUMN_TRANSITION   (Sharad — residual Pitta)
                Nov:     LATE_AUTUMN_DRY     (Hemanta onset — Vata dominant)

            Equatorial regions use a simplified wet/dry model.

        Args:
            month: Month of year (1–12).
            hemisphere: "northern", "southern", or "equatorial".

        Returns:
            SeasonalInfluence enum value.
        """
        # Equatorial regions have minimal seasonal variation
        if hemisphere == "equatorial":
            # Simplified: wet season (Jun–Oct) vs dry season
            if 6 <= month <= 10:
                return SeasonalInfluence.MONSOON_DAMPNESS
            elif month in (11, 12, 1, 2):
                return SeasonalInfluence.WINTER_ACCUMULATION
            else:
                return SeasonalInfluence.SUMMER_HEAT

        # Northern Hemisphere mapping
        northern_map = {
            12: SeasonalInfluence.WINTER_ACCUMULATION,
            1:  SeasonalInfluence.WINTER_ACCUMULATION,
            2:  SeasonalInfluence.WINTER_ACCUMULATION,
            3:  SeasonalInfluence.SPRING_RELEASE,
            4:  SeasonalInfluence.SPRING_RELEASE,
            5:  SeasonalInfluence.SUMMER_HEAT,
            6:  SeasonalInfluence.SUMMER_HEAT,
            7:  SeasonalInfluence.MONSOON_DAMPNESS,
            8:  SeasonalInfluence.MONSOON_DAMPNESS,
            9:  SeasonalInfluence.AUTUMN_TRANSITION,
            10: SeasonalInfluence.AUTUMN_TRANSITION,
            11: SeasonalInfluence.LATE_AUTUMN_DRY,
        }

        if hemisphere == "northern":
            return northern_map[month]

        # Southern Hemisphere: shift 6 months
        # SH January = NH July (monsoon), SH July = NH January (winter)
        shifted_month = ((month - 1 + 6) % 12) + 1
        return northern_map[shifted_month]

    # -------------------------------------------------------------------------
    # PRIVATE: SLEEP PRESSURE ESTIMATION
    # -------------------------------------------------------------------------

    @staticmethod
    def _determine_sleep_pressure(hour: int) -> SleepPressure:
        """
        Estimate homeostatic sleep drive from time of day.

        Based on the Process S model — adenosine accumulates linearly
        during wakefulness. Assuming a conventional schedule with
        waking around 06:00–07:00:

            Morning (04–11):  LOW      — Recently cleared by sleep
            Afternoon (12–18): MODERATE — Building through the day
            Evening+ (19–03):  HIGH     — Strong drive, sleep imminent/overdue

        Args:
            hour: Hour of day (0–23).

        Returns:
            SleepPressure enum value.
        """
        if 4 <= hour <= 11:
            return SleepPressure.LOW
        elif 12 <= hour <= 18:
            return SleepPressure.MODERATE
        else:
            # 19–23 and 0–3
            return SleepPressure.HIGH

    # -------------------------------------------------------------------------
    # PRIVATE: MISALIGNMENT DETECTION
    # -------------------------------------------------------------------------

    @staticmethod
    def _detect_misalignment(hour: int) -> bool:
        """
        Detect circadian misalignment.

        A user querying during biological sleep hours (22:00–04:00)
        is potentially experiencing:
            - Insomnia or difficulty sleeping
            - Shift work / jet lag
            - Acute distress requiring immediate attention

        This flag is used downstream to:
            1. Adjust recommendation tone (more gentle, sleep-supportive)
            2. Suggest sleep hygiene alongside the primary remedy
            3. Flag potential chronic circadian disruption

        Args:
            hour: Hour of day (0–23).

        Returns:
            True if querying during expected deep sleep hours.
        """
        return hour >= 22 or hour <= 4

    # -------------------------------------------------------------------------
    # PRIVATE: ADVISORY COMPOSITION
    # -------------------------------------------------------------------------

    @staticmethod
    def _compose_advisory(
        phase: CircadianPhase,
        misaligned: bool,
        season: SeasonalInfluence,
        hour: int,
    ) -> str:
        """
        Compose a contextual advisory string for downstream systems.

        Provides actionable context that the response generator can weave
        into its recommendations naturally.

        Args:
            phase: Current circadian phase.
            misaligned: Whether circadian misalignment is detected.
            season: Current seasonal influence.
            hour: Hour of day.

        Returns:
            Human-readable advisory string.
        """
        parts: list[str] = []

        # Misalignment advisory (highest priority)
        if misaligned:
            parts.append(
                f"⚠️ User is active at {hour:02d}:00 during the "
                f"'{phase.value}' phase. This suggests possible insomnia, "
                f"shift work, or acute distress. Prioritize calming, "
                f"sleep-supportive recommendations."
            )

        # Phase-specific advisories
        phase_notes = {
            CircadianPhase.EARLY_MORNING: (
                "Early morning — cortisol is surging. Warm beverages and "
                "gentle movement are well-tolerated. Avoid heavy remedies."
            ),
            CircadianPhase.MORNING_ACTIVATION: (
                "Peak cortisol window — ideal time for stimulating herbs "
                "(e.g., ginger, tulsi). Cognitive function is at its best."
            ),
            CircadianPhase.LATE_MORNING: (
                "Sustained focus period — cognitive performance peaks. "
                "Adaptogenic herbs are most effective during this window."
            ),
            CircadianPhase.AFTERNOON_PEAK: (
                "Digestive fire (agni) is at maximum — optimal absorption "
                "for oral remedies and supplements."
            ),
            CircadianPhase.AFTERNOON_SLUMP: (
                "Post-prandial dip — adenosine building, alertness drops. "
                "Avoid sedating remedies; consider peppermint or light spices."
            ),
            CircadianPhase.EVENING_ACTIVE: (
                "Second wind period — gentle exercise well-tolerated. "
                "Begin transitioning to calming remedies."
            ),
            CircadianPhase.WIND_DOWN: (
                "Melatonin onset phase — favor calming herbs (chamomile, "
                "valerian, lavender). Avoid stimulants."
            ),
            CircadianPhase.DEEP_SLEEP: (
                "Biological repair phase — sleep-supportive remedies only. "
                "Avoid anything stimulating."
            ),
        }
        if not misaligned:
            parts.append(phase_notes.get(phase, ""))

        # Seasonal advisories
        season_notes = {
            SeasonalInfluence.WINTER_ACCUMULATION: (
                "Winter (Kapha season): warming spices favored. "
                "Immunity is naturally strong; heavier foods tolerated."
            ),
            SeasonalInfluence.SPRING_RELEASE: (
                "Spring (Kapha release): detox-supportive herbs favored. "
                "Watch for allergies and respiratory congestion."
            ),
            SeasonalInfluence.SUMMER_HEAT: (
                "Summer (Pitta season): cooling remedies preferred "
                "(mint, fennel, aloe). Hydration is critical."
            ),
            SeasonalInfluence.MONSOON_DAMPNESS: (
                "Monsoon (Vata aggravation): digestion weakened. "
                "Warm, light foods and digestive spices are ideal."
            ),
            SeasonalInfluence.AUTUMN_TRANSITION: (
                "Autumn (residual Pitta): anti-inflammatory herbs helpful. "
                "Skin and digestive issues may flare."
            ),
            SeasonalInfluence.LATE_AUTUMN_DRY: (
                "Late autumn (Vata dominant): moisturizing, grounding "
                "remedies favored. Joint pain and anxiety may increase."
            ),
        }
        parts.append(season_notes.get(season, ""))

        return " | ".join(p for p in parts if p)
