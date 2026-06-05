"""
ServVia 4.0 — Cloud Lab Intelligence Agent
============================================

Analyzes anonymized lab report text using the primary LLM (Groq)
with automatic Azure OpenAI fallback on rate limit.
Only receives PHI-redacted text — no patient-identifiable data
ever reaches the cloud.

Pipeline position:
    [Local OCR] -> [Local PHI Redaction] -> ** THIS AGENT ** -> JSON summary
"""

import json
import logging
import re
from typing import AsyncGenerator, Dict, Optional, Tuple

from django_core.config import Config

logger = logging.getLogger("ServVia.Agents.LabSummarizer")

# ─────────────────────────────────────────────────────────────────────────────
# Protective biomarkers: HIGH values are beneficial, not abnormal.
# The LLM is instructed not to flag these, but we validate in post-processing
# as a safety net.
# ─────────────────────────────────────────────────────────────────────────────

_PROTECTIVE_HIGH_MARKERS = frozenset({
    "hdl", "hdl cholesterol", "hdl-c", "hdl-cholesterol",
    "high density lipoprotein", "high-density lipoprotein",
    "hdl chol", "hdl-chol",
})

# Severity ranking (lower = more severe) used for ordering in markdown output.
_SEVERITY_RANK = {
    "critical_low": 0, "critical_high": 0,
    "high": 1, "low": 1,
    "abnormal": 2,
    "normal": 3,
}

_STATUS_TO_ICON = {
    "critical_low": "🔴", "critical_high": "🔴",
    "high": "🟠", "low": "🟡",
    "abnormal": "🟠",
    "normal": "✅",
}

# Tolerance for numeric boundary comparison — floating point safety + real-world
# lab imprecision. A value within 1% of a boundary is treated as at-boundary.
_BOUNDARY_TOLERANCE = 0.01


def _parse_numeric(value) -> Optional[float]:
    """Extract a single float from a value like '14.5', '< 148', '100.39'."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    m = re.search(r"-?\d+\.?\d*", s)
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def _parse_reference_range(ref: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse a reference range string into (low, high). Either can be None.

    Handles:
      "13.0 - 16.5 g/dL"     -> (13.0, 16.5)
      "13.0 - 16.5"          -> (13.0, 16.5)
      "< 100 mg/dL"          -> (None, 100)
      "Optimal: <100 mg/dL"  -> (None, 100)
      "> 60 mg/dL"           -> (60, None)
      "Up to 5.0"            -> (None, 5.0)
      "3.5 to 8.5"           -> (3.5, 8.5)
      "Normal: <150 mg/dL"   -> (None, 150)
      "187 - 833 pg/mL"      -> (187, 833)

    Returns (None, None) if nothing parseable.
    """
    if not ref or not isinstance(ref, str):
        return (None, None)

    s = ref.strip()
    s_low = s.lower()

    # Skip obviously-qualitative references.
    if any(tok in s_low for tok in ("absent", "present", "positive", "negative",
                                    "non reactive", "reactive", "nil",
                                    "normochromic", "adequate", "clear",
                                    "pale yellow", "detected", "identified")):
        return (None, None)

    # Range: "a - b" or "a to b"
    m = re.search(
        r"(-?\d+\.?\d*)\s*(?:-|–|—|to)\s*(-?\d+\.?\d*)", s
    )
    if m:
        try:
            return (float(m.group(1)), float(m.group(2)))
        except ValueError:
            pass

    # Less-than: "<100", "< 100", "up to 5", "optimal: <100", "desirable: <200"
    m = re.search(r"(?:<|≤|up\s*to|less\s*than|desirable\s*:?|optimal\s*:?|normal\s*:?)\s*(-?\d+\.?\d*)", s_low)
    if m:
        try:
            return (None, float(m.group(1)))
        except ValueError:
            pass

    # Greater-than: ">60", "> 60", "at least 60"
    m = re.search(r"(?:>|≥|at\s*least|greater\s*than|minimum\s*:?)\s*(-?\d+\.?\d*)", s_low)
    if m:
        try:
            return (float(m.group(1)), None)
        except ValueError:
            pass

    return (None, None)


def _classify_by_range(
    value: float, low: Optional[float], high: Optional[float]
) -> str:
    """Return 'low', 'normal', or 'high' based on numeric comparison with tolerance."""
    if low is not None:
        threshold = low * (1 - _BOUNDARY_TOLERANCE) if low > 0 else low - abs(low) * _BOUNDARY_TOLERANCE
        if value < threshold:
            return "low"
    if high is not None:
        threshold = high * (1 + _BOUNDARY_TOLERANCE) if high > 0 else high + abs(high) * _BOUNDARY_TOLERANCE
        if value > threshold:
            return "high"
    return "normal"


def _validate_biomarkers(biomarkers: list) -> list:
    """
    Post-process LLM biomarker output to fix known clinical classification errors.

    Fixes applied:
    1. Protective biomarkers (HDL): elevated HDL is cardiovascular-protective —
       force status to 'normal' if LLM flagged 'high'/'critical_high'.
    2. Status normalisation: unknown status values default to 'normal'.
    3. Numeric range re-check: if LLM said 'normal' but the numeric value is
       clearly outside the parsed reference range, flip to 'low'/'high'.
    4. Missing reference range: if LLM said 'normal' but no range was extracted
       and no clinical note was provided, the classification is un-verifiable —
       leave as normal but mark with a verification flag for display.
    """
    allowed_statuses = {"normal", "low", "high", "critical_low", "critical_high", "abnormal"}

    for b in biomarkers:
        name = b.get("name", "")
        name_lower = name.lower().strip()
        status = b.get("status", "normal")

        # 1. Normalise unknown status values
        if status not in allowed_statuses:
            b["status"] = "normal"
            status = "normal"

        # 2. HDL: elevated is protective — never flag as high/critical_high
        if any(marker in name_lower for marker in _PROTECTIVE_HIGH_MARKERS):
            if status in ("high", "critical_high"):
                b["status"] = "normal"
                b["clinical_note"] = None
                for fld in ("possible_causes", "symptoms_to_watch",
                            "dietary_recommendations", "lifestyle_changes"):
                    b[fld] = None
                logger.info(
                    "[Validator] '%s': status %r → 'normal' (protective biomarker)",
                    name, status,
                )
                status = "normal"

        # 3. Numeric cross-check against reference range
        value_num = _parse_numeric(b.get("value"))
        low, high = _parse_reference_range(b.get("reference_range", ""))

        if value_num is not None and (low is not None or high is not None):
            computed = _classify_by_range(value_num, low, high)

            # Respect protective-biomarker rule: HDL never goes 'high'
            is_protective = any(m in name_lower for m in _PROTECTIVE_HIGH_MARKERS)
            if is_protective and computed == "high":
                computed = "normal"

            # If LLM said normal but the number says otherwise, correct it.
            if status == "normal" and computed != "normal":
                b["status"] = computed
                if not b.get("clinical_note"):
                    direction = "above" if computed == "high" else "below"
                    b["clinical_note"] = (
                        f"Value {value_num} is {direction} the reference range "
                        f"({b.get('reference_range', 'n/a')}); clinical correlation advised."
                    )
                logger.info(
                    "[Validator] '%s': status 'normal' → %r "
                    "(numeric %s vs range low=%s high=%s)",
                    name, computed, value_num, low, high,
                )
                status = computed

            # If LLM said low/high but the number is actually within range,
            # do NOT silently flip — LLM may know a clinical threshold we don't.
            # Log for observability only.
            elif status in ("low", "high") and computed == "normal":
                logger.debug(
                    "[Validator] '%s' status=%s but numeric within parsed range "
                    "(value=%s, low=%s, high=%s). Trusting LLM.",
                    name, status, value_num, low, high,
                )

        # 4. Verification flag: normal status with no parseable range AND no note
        b["_range_verifiable"] = bool(low is not None or high is not None)

    return biomarkers


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT — Clinical Pathologist
# ─────────────────────────────────────────────────────────────────────────────

LAB_ANALYSIS_PROMPT = """You are a Clinical Pathologist AI assistant. You will receive anonymized lab report text where all patient-identifiable information has been replaced with placeholders like [PERSON_1], [DATE], [PHONE_1], etc.

=== YOUR TASK ===
1. Parse the anonymized lab report text.
2. Identify ALL parameters mentioned — quantitative biomarkers (e.g., Hemoglobin: 14.2 g/dL) OR qualitative findings (e.g., Histologic Type: Adenocarcinoma).
3. For QUANTITATIVE parameters: extract value, unit, and compare against standard clinical reference ranges.
4. For QUALITATIVE parameters: extract the reported finding and compare against the expected normal finding.
5. Flag any parameter that is clinically abnormal.
6. Provide a brief clinical significance note for each abnormal finding.

=== ABSOLUTE RULES ===
- Do NOT attempt to re-identify any redacted information.
- Do NOT fabricate values. If a value is unclear or unreadable, mark it as "unreadable".
- Do NOT provide a diagnosis. Only flag abnormal values and explain their clinical significance.
- Do NOT speculate about the patient's identity, age, or gender from the redacted text.
- If the text does not appear to be a lab report, return an error response.

=== PROTECTIVE BIOMARKERS — CRITICAL ===
Some biomarkers are beneficial when elevated. You must NEVER classify these as "high" status when elevated:

- HDL Cholesterol (any label containing "HDL"): High HDL is cardiovascular-protective.
  * Values ≥ 60 mg/dL = OPTIMAL. Status must be "normal".
  * Only flag HDL as "low" if below 40 mg/dL (men) or 50 mg/dL (women).
  * NEVER use status "high" or "critical_high" for HDL. Elevated HDL is NOT abnormal.

=== REFERENCE RANGE BOUNDARY RULE ===
If a numeric value is exactly at a boundary of the reference range (e.g., value = 60.0, range = "> 60 mg/dL"), classify it as "normal", not as "high" or "low". A value at the exact boundary is within the acceptable range.

=== SEVERITY CLASSIFICATION ===
Use these status values precisely:
- "normal"        — Within reference range (including exact boundary values)
- "low"           — Below reference range, not life-threatening
- "high"          — Above reference range, not life-threatening
- "critical_low"  — Dangerously low (requires urgent attention)
- "critical_high" — Dangerously high (requires urgent attention)
- "abnormal"      — Qualitative finding that is pathological (use only when no numeric range applies)

Critical thresholds (examples):
- Hemoglobin: critical_low < 7 g/dL, critical_high > 20 g/dL
- Glucose: critical_high > 400 mg/dL
- Potassium: critical_low < 2.5, critical_high > 6.5 mmol/L
- For most routine labs: use "low" or "high", not "critical"

=== DERIVED / COMPUTED VALUES ===
If a parameter has no printed reference range, use standard clinical ranges:
- Mean Blood Glucose (derived from HbA1c): normal < 117 mg/dL; high ≥ 140 mg/dL
- eAG (estimated average glucose): same thresholds as Mean Blood Glucose
- Anion Gap: 3 - 11 mmol/L
- Osmolality: 275 - 295 mOsm/kg
Never leave "reference_range" as "–" or empty if a standard clinical range exists — supply it.

=== STRICT NUMERIC COMPARISON ===
Compare the numeric value strictly against the range. Do NOT call a value "normal"
just because it is close to a threshold:
- "Optimal: <100 mg/dL" with value 100.39 → status = "high" (100.39 > 100).
- "74 - 106 mg/dL" with value 141 → status = "high".
- Qualitative tests (e.g., Urine Glucose "Present" with reference "Absent") → status = "abnormal".

=== HANDLING QUANTITATIVE vs QUALITATIVE PARAMETERS ===

For QUANTITATIVE parameters (blood counts, metabolic panels, hormone levels, etc.):
- "value": the numeric value as a string (e.g., "14.2")
- "unit": the unit of measurement (e.g., "g/dL")
- "reference_range": the normal range as reported (e.g., "13.0-17.0 g/dL")
- "status": "normal", "low", "high", "critical_low", or "critical_high"

For QUALITATIVE parameters (histopathology, presence/absence tests, descriptive findings):
- "value": the actual reported finding (e.g., "Adenocarcinoma", "Identified", "Present")
- "unit": null
- "reference_range": the EXPECTED NORMAL finding (e.g., "No malignancy", "Not identified", "Absent")
- "status": "normal" if finding is benign/expected, "abnormal" if pathological

=== PATIENT GUIDANCE (ABNORMAL BIOMARKERS ONLY) ===
For every biomarker whose status is NOT "normal", provide personalised recovery guidance.
For biomarkers with status "normal", these fields MUST be null (not empty arrays, null).

Guidance fields:
- "possible_causes": list of 2-4 likely contributing factors specific to the abnormality
  (e.g., for elevated HbA1c: ["Chronic carbohydrate excess", "Insulin resistance",
  "Sedentary lifestyle", "Obesity"]).
- "symptoms_to_watch": list of 2-4 symptoms the patient should monitor at home
  (e.g., for low Vitamin B12: ["Fatigue and weakness", "Tingling in hands/feet",
  "Memory issues", "Pale skin"]).
- "dietary_recommendations": list of 2-4 specific foods to add OR avoid, with the
  reason in-line (e.g., "Fatty fish (salmon, sardines) — rich in omega-3 to lower
  triglycerides"). Be concrete; avoid vague advice like "eat healthy".
- "lifestyle_changes": list of 2-4 actionable habits (e.g., "30 min brisk walk,
  5 days/week — improves insulin sensitivity"). Each item should state the habit
  AND the benefit.

All four arrays must be clinically specific to the biomarker and its direction of
abnormality (low vs high). Do NOT reuse the same generic advice across biomarkers.

=== OUTPUT FORMAT ===
Respond with ONLY valid JSON (no markdown fences, no explanation outside the JSON):
{{
    "report_type": "string — type of lab report (e.g., Complete Blood Count, Histopathology Report, Metabolic Panel, Thyroid Panel, Mixed)",
    "biomarkers": [
        {{
            "name": "Parameter Name",
            "value": "reported value as string",
            "unit": "unit of measurement, or null for qualitative",
            "reference_range": "normal range for quantitative OR expected normal finding for qualitative",
            "status": "normal | low | high | critical_low | critical_high | abnormal",
            "clinical_note": "brief clinical significance if abnormal, null if normal",
            "possible_causes": ["..."] or null,
            "symptoms_to_watch": ["..."] or null,
            "dietary_recommendations": ["..."] or null,
            "lifestyle_changes": ["..."] or null
        }}
    ],
    "abnormal_count": 0,
    "normal_count": 0,
    "summary": "2-3 sentence overall summary of findings, focusing on abnormal values and their clinical implications",
    "recommendation": "General recommendation (e.g., consult physician, repeat test, routine follow-up)",
    "pattern_analysis": "Describe connections between abnormal findings if any",
    "action_plan": {{
        "immediate": ["Actions for THIS WEEK — 2-4 bullets"],
        "short_term": ["Goals for 1-3 MONTHS — 2-4 bullets"],
        "long_term": ["Sustainable lifestyle changes — 2-4 bullets"],
        "retest_timeline": "When to re-test key abnormal biomarkers (e.g., 'HbA1c in 3 months')",
        "specialist_referral": "Specialist(s) to consult, or null if primary care is sufficient"
    }},
    "urgency_level": "routine | soon | urgent | emergency",
    "follow_up_needed": true
}}

CRITICAL RULES:
- NEVER use "N/A" for any field. For qualitative tests, reference_range must be the expected normal finding.
- NEVER mark a pathological finding (e.g., cancer, invasion, metastasis) as "normal".
- NEVER mark elevated HDL as "high" — use "normal" for HDL values at or above minimum thresholds.
- A value at the exact boundary of the reference range = "normal".
- For normal biomarkers: possible_causes, symptoms_to_watch, dietary_recommendations, lifestyle_changes MUST be null.
- For abnormal biomarkers: all four guidance arrays MUST be populated with specific, non-generic content.

=== LAB REPORT TEXT ===
{anonymized_text}

Analyze the report and respond with JSON only:"""


# ─────────────────────────────────────────────────────────────────────────────
# CO-PILOT PROMPT — System-grouped, tiered triage, delta tracking
# ─────────────────────────────────────────────────────────────────────────────

COPILOT_ANALYSIS_PROMPT = """You are a Clinical Co-Pilot AI. You will receive:
1. Anonymized lab report text (PHI-redacted with placeholders like [PERSON_1]).
2. Optionally, a HISTORICAL PAYLOAD of past biomarker snapshots for this patient.

=== YOUR TASK ===
1. Parse the lab report and extract ALL parameters (quantitative + qualitative).
2. Group biomarkers by bodily system (e.g., Hematological, Hepatic, Renal, Metabolic, Thyroid, Cardiac, etc.).
3. Triage abnormalities into Red Flags (requires doctor consult) vs Yellow Flags (lifestyle adjustments).
4. Generate a 3-step action plan: clinical follow-ups, nutrition, and lifestyle.
5. If historical data is provided, compute delta tracking (improvements vs declines).

=== ABSOLUTE RULES ===
- Do NOT re-identify redacted information.
- Do NOT fabricate values. Mark unclear values as "unreadable".
- Do NOT diagnose. Flag abnormalities and explain clinical significance.
- Do NOT speculate about patient identity from redacted text.
- If historical data is empty or not provided, omit the delta_tracking array (use []).

=== PROTECTIVE BIOMARKERS — CRITICAL ===
- HDL Cholesterol (any label containing "HDL"): Elevated HDL is PROTECTIVE.
  * Values ≥ 60 mg/dL are OPTIMAL. Status = "normal". Do NOT triage as a red or yellow flag.
  * Only flag HDL as "low" if below minimum thresholds.
  * NEVER use status "high" for HDL.

=== REFERENCE RANGE BOUNDARY RULE ===
If a value is exactly at the boundary of a reference range, classify it as "normal".

=== SEVERITY CLASSIFICATION ===
- Red Flags: critical_low, critical_high, or clearly dangerous abnormal findings
- Yellow Flags: low, high, or mildly abnormal findings manageable with lifestyle
- Normal biomarkers: appear in system_groups only, NOT in triage

=== OUTPUT FORMAT ===
Respond with ONLY valid JSON (no markdown fences):
{{
    "report_type": "string (e.g., Complete Blood Count, Metabolic Panel, Mixed)",
    "report_date": "string date if detectable, or null",

    "system_groups": [
        {{
            "system": "Hematological",
            "biomarkers": [
                {{
                    "name": "Parameter Name",
                    "value": "reported value as string",
                    "unit": "unit or null for qualitative",
                    "reference_range": "normal range OR expected normal finding",
                    "status": "normal | low | high | critical_low | critical_high | abnormal",
                    "clinical_note": "brief clinical significance if abnormal, null if normal"
                }}
            ]
        }}
    ],

    "triage": {{
        "red_flags": [
            {{
                "biomarker": "Parameter Name",
                "reason": "Why this requires physician attention",
                "action": "Specific clinical action (e.g., schedule recheck within 1 week)"
            }}
        ],
        "yellow_flags": [
            {{
                "biomarker": "Parameter Name",
                "reason": "Why this is a concern but manageable",
                "action": "Lifestyle or supplement recommendation"
            }}
        ]
    }},

    "action_plan": {{
        "clinical_followups": ["List of recommended tests or specialist consults"],
        "nutrition": ["Dietary recommendations based on findings"],
        "lifestyle": ["Exercise, sleep, habit recommendations"]
    }},

    "delta_tracking": [
        {{
            "biomarker": "Parameter Name",
            "previous_value": "value from most recent historical snapshot",
            "current_value": "value from current report",
            "trend": "improving | declining | stable",
            "note": "Brief explanation of the change"
        }}
    ],

    "summary": "2-3 sentence overall summary of findings",
    "urgency_level": "routine | soon | urgent | emergency",
    "abnormal_count": 0,
    "normal_count": 0
}}

CRITICAL RULES:
- Every biomarker must appear in exactly ONE system_group.
- Red flags: critical_low, critical_high, or clinically dangerous abnormal findings.
- Yellow flags: low, high, or mildly abnormal findings manageable with lifestyle changes.
- Normal biomarkers go into system_groups but NOT into triage.
- delta_tracking: only include biomarkers that appear in BOTH current and historical data.
- If no historical data is provided, delta_tracking must be an empty array [].
- action_plan must always have all three keys, even if arrays are empty.
- NEVER flag elevated HDL as a red or yellow flag.

=== CURRENT LAB REPORT TEXT ===
{anonymized_text}

=== HISTORICAL BIOMARKER DATA (JSON) ===
{historical_payload}

Analyze the report and respond with JSON only:"""


# ─────────────────────────────────────────────────────────────────────────────
# LLM CALL — Groq primary, Azure OpenAI fallback
# ─────────────────────────────────────────────────────────────────────────────

async def _call_lab_llm(prompt: str) -> str:
    """
    Call LLM for lab analysis. Groq is primary (fast, 3-5s) with
    Azure OpenAI as fallback for reliability.
    Returns raw response text.
    """
    groq_model = Config.GROQ_FALLBACK_MODELS.get("lab_summarizer")

    # ── Primary: Groq ──
    if groq_model and Config.GROQ_API_KEY:
        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=Config.GROQ_API_KEY)
            response = await client.chat.completions.create(
                model=groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=32000,
                response_format={"type": "json_object"},
            )
            if response and response.choices:
                content = response.choices[0].message.content
                if content:
                    logger.info(f"[GROQ] Lab analysis via {groq_model}")
                    return content.strip()
            logger.warning("Groq returned empty response, falling back to OpenAI")
        except Exception as e:
            logger.warning(f"Groq primary failed ({e}), falling back to OpenAI")

    # ── Fallback: Azure OpenAI ──
    from legacy_healthcare.rag_service.openai_service import make_openai_request
    try:
        response, exception, retries = await make_openai_request(
            prompt, model=Config.MODEL_CHAT, temperature=0, max_retries=2
        )
        if response and response.choices:
            content = response.choices[0].message.content
            if content:
                logger.info(f"Lab analysis via OpenAI ({Config.MODEL_CHAT})")
                return content.strip()
        raise ValueError(f"OpenAI returned empty after {retries} retries: {exception}")
    except Exception as e:
        raise ValueError(f"All LLM providers failed: {e}")


async def _stream_lab_llm(prompt: str) -> AsyncGenerator[str, None]:
    """
    Stream LLM response token-by-token. Groq is primary with Azure OpenAI fallback.
    Yields content delta strings.
    """
    groq_model = Config.GROQ_FALLBACK_MODELS.get("lab_summarizer")

    # ── Primary: Groq streaming ──
    if groq_model and Config.GROQ_API_KEY:
        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=Config.GROQ_API_KEY)
            stream = await client.chat.completions.create(
                model=groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=32000,
                response_format={"type": "json_object"},
                stream=True,
            )
            token_count = 0
            try:
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        token_count += 1
                        yield chunk.choices[0].delta.content
            finally:
                await _safe_close_stream(stream)
            if token_count > 0:
                logger.info(f"[GROQ] Streamed {token_count} tokens via {groq_model}")
                return
            logger.warning("Groq streaming returned 0 tokens, falling back to OpenAI")
        except Exception as e:
            logger.warning(f"Groq streaming failed ({e}), falling back to OpenAI")

    # ── Fallback: Azure OpenAI streaming ──
    from openai import AsyncAzureOpenAI
    client = AsyncAzureOpenAI(
        api_key=Config.AZURE_OPENAI_API_KEY,
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        api_version=Config.AZURE_OPENAI_API_VERSION,
    )
    stream = await client.chat.completions.create(
        model=Config.MODEL_CHAT,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=16000,
        response_format={"type": "json_object"},
        stream=True,
    )
    token_count = 0
    try:
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                token_count += 1
                yield chunk.choices[0].delta.content
    finally:
        await _safe_close_stream(stream)
    logger.info(f"Streamed {token_count} tokens via OpenAI ({Config.MODEL_CHAT})")


async def _safe_close_stream(stream) -> None:
    """
    Close an LLM async stream robustly. Both Groq and OpenAI SDKs expose
    `close()` that may be sync or async depending on version. Swallow errors —
    this runs in a finally block and must not mask the real exception.
    """
    closer = getattr(stream, "close", None) or getattr(stream, "aclose", None)
    if closer is None:
        return
    try:
        result = closer()
        if hasattr(result, "__await__"):
            await result
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — Non-streaming
# ─────────────────────────────────────────────────────────────────────────────

async def analyze_lab_report_copilot(
    anonymized_text: str,
    historical_snapshots: list = None,
) -> Dict:
    """
    Co-Pilot analysis: system-grouped, tiered triage, delta tracking.

    Args:
        anonymized_text: PHI-redacted lab report text.
        historical_snapshots: List of past biomarker arrays (newest first).

    Returns:
        Dict with system_groups, triage, action_plan, delta_tracking, etc.
    """
    if not anonymized_text or not anonymized_text.strip():
        raise ValueError("Empty anonymized text — nothing to analyze")

    historical_payload = (
        json.dumps(historical_snapshots, indent=2)
        if historical_snapshots
        else "No historical data available."
    )

    prompt = COPILOT_ANALYSIS_PROMPT.format(
        anonymized_text=anonymized_text,
        historical_payload=historical_payload,
    )
    logger.info(
        f"Co-Pilot analysis: {len(anonymized_text)} chars, "
        f"{len(historical_snapshots or [])} historical snapshots"
    )

    raw_content = await _call_lab_llm(prompt)
    return _parse_copilot_response(raw_content)


def _parse_copilot_response(raw_content: str) -> Dict:
    """Parse Co-Pilot LLM output with schema validation and graceful fallback."""
    cleaned = _strip_markdown_fences(raw_content)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        repaired = _repair_truncated_json(cleaned)
        if repaired:
            try:
                result = json.loads(repaired)
                logger.warning(
                    "Co-Pilot JSON was truncated (%d chars); recovered via repair",
                    len(cleaned),
                )
            except json.JSONDecodeError as e2:
                logger.error(f"Co-Pilot JSON parse failed after repair: {e2}\nRaw: {cleaned[:500]}")
                raise ValueError(f"Co-Pilot LLM returned invalid JSON: {e2}")
        else:
            logger.error(f"Co-Pilot JSON parse failed: {e}\nRaw: {cleaned[:500]}")
            raise ValueError(f"Co-Pilot LLM returned invalid JSON: {e}")

    # ── Schema validation with defaults ──
    if "system_groups" not in result:
        if "biomarkers" in result:
            result["system_groups"] = [{
                "system": "General",
                "biomarkers": result.pop("biomarkers"),
            }]
        else:
            result["system_groups"] = []

    if "triage" not in result:
        result["triage"] = {"red_flags": [], "yellow_flags": []}
    else:
        result["triage"].setdefault("red_flags", [])
        result["triage"].setdefault("yellow_flags", [])

    if "action_plan" not in result:
        result["action_plan"] = {"clinical_followups": [], "nutrition": [], "lifestyle": []}
    else:
        result["action_plan"].setdefault("clinical_followups", [])
        result["action_plan"].setdefault("nutrition", [])
        result["action_plan"].setdefault("lifestyle", [])

    result.setdefault("delta_tracking", [])
    result.setdefault("summary", "")
    result.setdefault("urgency_level", "routine")
    result.setdefault("report_type", "Lab Report")
    result.setdefault("report_date", None)

    # Validate and fix biomarkers in all system groups
    for group in result["system_groups"]:
        group["biomarkers"] = _validate_biomarkers(group.get("biomarkers", []))

    # Remove triage flags for biomarkers that were corrected to "normal"
    all_biomarkers = []
    for group in result["system_groups"]:
        all_biomarkers.extend(group.get("biomarkers", []))

    normal_names = {
        b.get("name", "").lower()
        for b in all_biomarkers
        if b.get("status") == "normal"
    }
    result["triage"]["red_flags"] = [
        f for f in result["triage"]["red_flags"]
        if f.get("biomarker", "").lower() not in normal_names
    ]
    result["triage"]["yellow_flags"] = [
        f for f in result["triage"]["yellow_flags"]
        if f.get("biomarker", "").lower() not in normal_names
    ]

    # Recount from system_groups (authoritative)
    abnormal = [b for b in all_biomarkers if b.get("status") != "normal"]
    result["abnormal_count"] = len(abnormal)
    result["normal_count"] = len(all_biomarkers) - len(abnormal)

    # Flatten biomarkers for backward compat (BiomarkerSnapshot)
    result["biomarkers"] = all_biomarkers
    result["formatted_summary"] = _format_copilot_markdown(result)

    logger.info(
        f"Co-Pilot analysis complete: {len(all_biomarkers)} biomarkers, "
        f"{len(abnormal)} abnormal, "
        f"{len(result['triage']['red_flags'])} red flags, "
        f"{len(result['triage']['yellow_flags'])} yellow flags"
    )
    return result


def _format_copilot_markdown(analysis: Dict) -> str:
    """Build a rich Co-Pilot markdown summary with triage + action plan."""
    lines = []
    report_type = analysis.get("report_type", "Lab Report")
    system_groups = analysis.get("system_groups", [])
    triage = analysis.get("triage", {})
    action_plan = analysis.get("action_plan", {})
    delta = analysis.get("delta_tracking", [])
    total_biomarkers = sum(len(g.get("biomarkers", [])) for g in system_groups)
    abnormal_count = analysis.get("abnormal_count", 0)
    normal_count = analysis.get("normal_count", 0)

    lines += [
        "## Clinical Co-Pilot Report", "",
        "### Report Overview",
        f"- **Test Type:** {report_type}",
    ]
    if analysis.get("report_date"):
        lines.append(f"- **Report Date:** {analysis['report_date']}")
    lines += [
        f"- **Total Parameters:** {total_biomarkers} tested | "
        f"{normal_count} normal | {abnormal_count} abnormal",
        "", "---", "",
        "### Executive Summary", "",
        analysis.get("summary", "No summary available."),
        "", "---", "",
    ]

    red_flags = triage.get("red_flags", [])
    yellow_flags = triage.get("yellow_flags", [])

    if red_flags:
        lines += ["### 🔴 Requires Doctor Consult", ""]
        for flag in red_flags:
            lines += [
                f"**{flag.get('biomarker', 'Unknown')}**",
                f"- Reason: {flag.get('reason', '')}",
                f"- Action: {flag.get('action', '')}",
                "",
            ]
        lines += ["---", ""]

    if yellow_flags:
        lines += ["### 🟡 Lifestyle Adjustments", ""]
        for flag in yellow_flags:
            lines += [
                f"**{flag.get('biomarker', 'Unknown')}**",
                f"- Reason: {flag.get('reason', '')}",
                f"- Action: {flag.get('action', '')}",
                "",
            ]
        lines += ["---", ""]

    if system_groups:
        lines += ["### Detailed Results by System", ""]
        for group in system_groups:
            system = group.get("system", "Other")
            biomarkers = group.get("biomarkers", [])
            if not biomarkers:
                continue
            lines += [f"#### {system}", ""]
            lines += [
                "| Parameter | Value | Reference | Status |",
                "|-----------|-------|-----------|--------|",
            ]
            for b in biomarkers:
                name = b.get("name", "")
                value = b.get("value", "")
                unit = b.get("unit") or ""
                display = f"{value} {unit}".strip() if unit else value
                ref = b.get("reference_range") or ""
                st = b.get("status", "")
                status_label = {
                    "normal": "✅ Normal",
                    "low": "🟡 Low",
                    "high": "🟠 High",
                    "critical_low": "🔴 Critical Low",
                    "critical_high": "🔴 Critical High",
                    "abnormal": "🟠 Abnormal",
                }.get(st, st.title())
                lines.append(f"| {name} | {display} | {ref} | {status_label} |")
            lines.append("")
        lines += ["---", ""]

    if action_plan:
        lines += ["### Action Plan", ""]
        followups = action_plan.get("clinical_followups", [])
        nutrition = action_plan.get("nutrition", [])
        lifestyle = action_plan.get("lifestyle", [])
        if followups:
            lines.append("**Clinical Follow-ups:**")
            lines += [f"- {item}" for item in followups]
            lines.append("")
        if nutrition:
            lines.append("**Nutrition:**")
            lines += [f"- {item}" for item in nutrition]
            lines.append("")
        if lifestyle:
            lines.append("**Lifestyle:**")
            lines += [f"- {item}" for item in lifestyle]
            lines.append("")
        lines += ["---", ""]

    if delta:
        lines += [
            "### Trend Analysis (vs Previous Reports)", "",
            "| Biomarker | Previous | Current | Trend | Note |",
            "|-----------|----------|---------|-------|------|",
        ]
        for d in delta:
            trend = d.get("trend", "")
            trend_label = {"improving": "Improving", "declining": "Declining",
                           "stable": "Stable"}.get(trend, trend)
            lines.append(
                f"| {d.get('biomarker', '')} | {d.get('previous_value', '')} | "
                f"{d.get('current_value', '')} | {trend_label} | {d.get('note', '')} |"
            )
        lines += ["", "---", ""]

    urgency = analysis.get("urgency_level", "routine")
    lines += ["### Follow-Up", "", f"- **Urgency:** {urgency.title()}", ""]

    return "\n".join(lines)


async def analyze_lab_report(anonymized_text: str) -> Dict:
    """
    Send anonymized lab report text to LLM for structured analysis.
    Returns dict with biomarkers, abnormal findings, summary, and recommendations.
    """
    if not anonymized_text or not anonymized_text.strip():
        raise ValueError("Empty anonymized text — nothing to analyze")

    prompt = LAB_ANALYSIS_PROMPT.format(anonymized_text=anonymized_text)
    logger.info(f"Sending {len(anonymized_text)} chars for lab analysis")

    raw_content = await _call_lab_llm(prompt)
    return _parse_lab_response(raw_content)


async def stream_lab_report_analysis(
    anonymized_text: str,
) -> AsyncGenerator[Tuple[str, dict], None]:
    """
    Stream lab report analysis token-by-token.

    Yields (event_type, data) tuples:
        ("chunk", {"text": "..."})     — raw LLM token (JSON fragment)
        ("complete", {"result": dict}) — parsed structured result

    The caller accumulates chunks silently, then streams formatted_summary
    word-by-word to the client.
    """
    if not anonymized_text or not anonymized_text.strip():
        raise ValueError("Empty anonymized text — nothing to analyze")

    prompt = LAB_ANALYSIS_PROMPT.format(anonymized_text=anonymized_text)
    logger.info(f"Streaming analysis for {len(anonymized_text)} chars")

    from contextlib import aclosing
    full_content = ""
    async with aclosing(_stream_lab_llm(prompt)) as delta_stream:
        async for delta in delta_stream:
            full_content += delta
            yield ("chunk", {"text": delta})

    result = _parse_lab_response(full_content)
    yield ("complete", {"result": result})


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL — Parse, validate, and format LLM response
# ─────────────────────────────────────────────────────────────────────────────

def _strip_markdown_fences(raw: str) -> str:
    """Remove markdown code fences if the model wraps output in them."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _repair_truncated_json(text: str) -> Optional[str]:
    """
    Best-effort repair of JSON truncated mid-stream (LLM hit max_tokens).

    Strategy: find the last complete top-level field before truncation by
    walking characters and tracking string/escape/brace/bracket depth,
    then close any still-open containers.
    """
    if not text:
        return None

    in_str = False
    escape = False
    stack = []          # open brackets: '{' or '['
    last_safe = -1      # index (exclusive) of last known-good cut point

    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
            if not stack:
                last_safe = i + 1
        elif ch == "," and len(stack) == 1:
            # complete top-level field boundary
            last_safe = i

    if last_safe <= 0:
        return None

    truncated = text[:last_safe].rstrip().rstrip(",")
    # Close any still-open containers based on original stack state at last_safe
    in_str = False
    escape = False
    stack = []
    for ch in truncated:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()

    closers = "".join("}" if c == "{" else "]" for c in reversed(stack))
    return truncated + closers


def _parse_lab_response(raw_content: str) -> Dict:
    """Parse raw LLM output into structured lab analysis dict."""
    cleaned = _strip_markdown_fences(raw_content)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        repaired = _repair_truncated_json(cleaned)
        if repaired:
            try:
                result = json.loads(repaired)
                logger.warning(
                    "LLM JSON was truncated (%d chars); recovered via repair",
                    len(cleaned),
                )
            except json.JSONDecodeError as e2:
                logger.error(
                    "Failed to parse LLM JSON even after repair: %s\nRaw: %s",
                    e2, cleaned[:500],
                )
                raise ValueError(f"LLM returned invalid JSON: {e2}")
        else:
            logger.error(f"Failed to parse LLM JSON: {e}\nRaw: {cleaned[:500]}")
            raise ValueError(f"LLM returned invalid JSON: {e}")

    # Validate and fix biomarker classifications
    result["biomarkers"] = _validate_biomarkers(result.get("biomarkers", []))

    # Recount after validation (LLM-provided counts may be stale)
    biomarkers = result["biomarkers"]
    abnormal = [b for b in biomarkers if b.get("status") != "normal"]
    result["abnormal_count"] = len(abnormal)
    result["normal_count"] = len(biomarkers) - len(abnormal)

    result["formatted_summary"] = _format_markdown_summary(result)

    logger.info(
        f"Lab analysis complete: {len(biomarkers)} biomarkers, "
        f"{len(abnormal)} abnormal"
    )
    return result


def _format_markdown_summary(analysis: Dict) -> str:
    """Build a patient-friendly markdown summary from structured analysis JSON."""
    biomarkers = analysis.get("biomarkers", [])
    normal = [b for b in biomarkers if b.get("status") == "normal"]
    critical = [b for b in biomarkers if b.get("status") in ("critical_low", "critical_high")]
    moderate = [b for b in biomarkers if b.get("status") in ("high", "low", "abnormal")]
    # Sort each bucket: high/low before qualitative 'abnormal' (range-backed findings first).
    moderate.sort(key=lambda x: (_SEVERITY_RANK.get(x.get("status"), 99), x.get("name", "")))
    critical.sort(key=lambda x: x.get("name", ""))
    abnormal = critical + moderate
    report_type = analysis.get("report_type", "Lab Report")
    total = len(biomarkers)

    lines = [
        "## Lab Report Analysis", "",
        "### Report Overview",
        f"- **Test Type:** {report_type}",
        f"- **Total Parameters:** {total} tested | "
        f"{len(normal)} normal | {len(abnormal)} abnormal",
        "", "---", "",
        "### Executive Summary", "",
        analysis.get("summary", "No summary available."),
        "", "---", "",
        "### Detailed Parameter Analysis", "",
    ]

    # Normal results — compact table
    if normal:
        lines += [
            "#### 🟢 Normal Results", "",
            "| Parameter | Your Value | Normal Range | Status |",
            "|-----------|------------|--------------|--------|",
        ]
        for b in normal:
            name = b.get("name", "Unknown")
            value = b.get("value", "–")
            unit = b.get("unit") or ""
            display_value = f"{value} {unit}".strip() if unit else value
            ref = b.get("reference_range") or "–"
            lines.append(f"| {name} | {display_value} | {ref} | ✅ Normal |")
        lines.append("")

    # Critical findings first
    if critical:
        lines += ["#### 🔴 Critical Findings — Seek Medical Attention", ""]
        for i, b in enumerate(critical, 1):
            lines += _format_abnormal_entry(i, b, "🔴")
        lines.append("")

    # Moderate abnormal findings
    if moderate:
        lines += ["#### 🟠 Abnormal Results", ""]
        for i, b in enumerate(moderate, 1):
            lines += _format_abnormal_entry(len(critical) + i, b, _status_icon(b.get("status")))
        lines.append("")

    if not abnormal:
        lines += ["#### ✅ All Results Within Normal Range", ""]

    # Pattern analysis
    pattern = analysis.get("pattern_analysis")
    if pattern:
        lines += ["---", "", "### Pattern Analysis", "", pattern, "", "---", ""]

    # Recommendation
    rec = analysis.get("recommendation")
    if rec:
        lines += ["### Recommendation", "", rec, "", "---", ""]

    # Action Plan
    action = analysis.get("action_plan") or {}
    if any(action.get(k) for k in ("immediate", "short_term", "long_term",
                                   "retest_timeline", "specialist_referral")):
        lines += ["### Action Plan", ""]
        if action.get("immediate"):
            lines += ["**Immediate Actions (This Week):**"]
            lines += [f"- {x}" for x in action["immediate"] if x]
            lines.append("")
        if action.get("short_term"):
            lines += ["**Short-Term Goals (1–3 Months):**"]
            lines += [f"- {x}" for x in action["short_term"] if x]
            lines.append("")
        if action.get("long_term"):
            lines += ["**Long-Term Lifestyle:**"]
            lines += [f"- {x}" for x in action["long_term"] if x]
            lines.append("")
        if action.get("retest_timeline"):
            lines += [f"**Retest Timeline:** {action['retest_timeline']}", ""]
        if action.get("specialist_referral"):
            lines += [f"**Specialist Referral:** {action['specialist_referral']}", ""]
        lines += ["---", ""]

    # Follow-up
    urgency = analysis.get("urgency_level", "routine")
    urgency_icon = {"routine": "🟢", "soon": "🟡", "urgent": "🟠", "emergency": "🔴"}.get(
        urgency, "🟢"
    )
    lines += [
        "### Follow-Up", "",
        f"- **Urgency:** {urgency_icon} {urgency.title()}",
    ]
    if analysis.get("follow_up_needed"):
        lines.append("- **Follow-up needed:** Yes")

    lines += [
        "", "---", "",
        "_This AI-generated analysis is for educational purposes only. "
        "Always consult a qualified healthcare provider for diagnosis and treatment._",
    ]

    return "\n".join(lines)


def _status_icon(status: str) -> str:
    """🔴 reserved for critical findings only; 🟠 for high/abnormal; 🟡 for low."""
    return _STATUS_TO_ICON.get(status or "", "🟠")


def _format_abnormal_entry(index: int, b: dict, icon: str) -> list:
    """Format a single abnormal biomarker entry with full recovery guidance."""
    name = b.get("name", "Unknown")
    value = b.get("value", "–")
    unit = b.get("unit") or ""
    display_value = f"{value} {unit}".strip() if unit else value
    status_raw = b.get("status", "abnormal")
    st_label = status_raw.replace("_", " ").title()
    ref = b.get("reference_range")
    note = b.get("clinical_note")

    lines = [
        f"**{index}. {name}: {display_value} — {icon} {st_label}**", "",
        f"- Your value: **{display_value}**",
    ]
    if ref:
        lines.append(f"- Reference: {ref}")
    if note:
        significance_label = (
            "**Urgent — Clinical Significance:**"
            if status_raw in ("critical_low", "critical_high")
            else "**Clinical Significance:**"
        )
        lines += ["", f"{significance_label} {note}"]

    def _bullets(title: str, items) -> list:
        if not items or not isinstance(items, list):
            return []
        cleaned = [str(x).strip() for x in items if x and str(x).strip()]
        if not cleaned:
            return []
        block = ["", f"**{title}:**"]
        block += [f"- {item}" for item in cleaned]
        return block

    lines += _bullets("Possible Causes", b.get("possible_causes"))
    lines += _bullets("Symptoms to Watch For", b.get("symptoms_to_watch"))
    lines += _bullets("Dietary Recommendations", b.get("dietary_recommendations"))
    lines += _bullets("Lifestyle Changes", b.get("lifestyle_changes"))

    lines += ["", "---", ""]
    return lines
