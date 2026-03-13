"""
ServVia 4.0 — Cloud Lab Intelligence Agent
============================================

Analyzes anonymized lab report text using the primary LLM (gpt-5o-mini)
with automatic Groq fallback (llama-3.3-70b-versatile) on rate limit.
Only receives PHI-redacted text — no patient-identifiable data
ever reaches the cloud.

Pipeline position:
    [Local OCR] -> [Local PHI Redaction] -> ** THIS AGENT ** -> JSON summary
"""

import json
import logging
from typing import AsyncGenerator, Dict, Tuple

from django_core.config import Config

logger = logging.getLogger("ServVia.Agents.LabSummarizer")

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT — Clinical Pathologist
# ─────────────────────────────────────────────────────────────────────────────

LAB_ANALYSIS_PROMPT = """You are a Clinical Pathologist AI assistant. You will receive anonymized lab report text where all patient-identifiable information has been replaced with placeholders like [PERSON_1], [DATE], [PHONE_1], etc.

=== YOUR TASK ===
1. Parse the anonymized lab report text.
2. Identify ALL parameters mentioned — these may be quantitative biomarkers (e.g., Hemoglobin: 14.2 g/dL) OR qualitative/histopathology findings (e.g., Histologic Type: Adenocarcinoma, Margins: Uninvolved, Perineural Invasion: Identified).
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

=== HANDLING QUANTITATIVE vs QUALITATIVE PARAMETERS ===

For QUANTITATIVE parameters (blood counts, metabolic panels, hormone levels, etc.):
- "value": the numeric value as a string (e.g., "14.2")
- "unit": the unit of measurement (e.g., "g/dL")
- "reference_range": the numeric normal range (e.g., "13.0-17.0 g/dL")
- "status": "normal", "low", "high", "critical_low", or "critical_high"

For QUALITATIVE parameters (histopathology, presence/absence tests, descriptive findings):
- "value": the actual reported finding (e.g., "Adenocarcinoma", "Identified", "3/16 positive")
- "unit": null
- "reference_range": the EXPECTED NORMAL finding (e.g., "No malignancy", "Not identified", "0/N positive"). This is what a healthy result would show — NOT "N/A" or null.
- "status": compare the reported finding against the expected normal. If the finding is clinically abnormal or pathological, use "abnormal". If the finding matches what a normal healthy result would show, use "normal".

=== OUTPUT FORMAT ===
Respond with ONLY valid JSON (no markdown fences, no explanation outside the JSON):
{{
    "report_type": "string — type of lab report (e.g., Complete Blood Count, Histopathology Report, Metabolic Panel, Thyroid Panel, Mixed)",
    "biomarkers": [
        {{
            "name": "Parameter Name",
            "value": "reported value as string",
            "unit": "unit of measurement, or null for qualitative",
            "reference_range": "normal range for quantitative (e.g., 13.0-17.0 g/dL) OR expected normal finding for qualitative (e.g., No malignancy, Not identified, Absent)",
            "status": "normal | low | high | critical_low | critical_high | abnormal",
            "clinical_note": "brief clinical significance if abnormal, null if normal"
        }}
    ],
    "abnormal_count": 0,
    "normal_count": 0,
    "summary": "2-3 sentence overall summary of findings, focusing on abnormal values and their clinical implications",
    "recommendation": "General recommendation (e.g., consult physician, repeat test, routine follow-up)",
    "pattern_analysis": "Describe connections between abnormal findings if any (e.g., tumor staging based on combined pathology findings)",
    "urgency_level": "routine | soon | urgent | emergency",
    "follow_up_needed": true
}}

CRITICAL RULES:
- NEVER use "N/A" for any field. For qualitative tests, reference_range must be the expected normal finding (e.g., "No malignancy", "Not identified", "Negative", "Absent", "0/N positive").
- NEVER mark a pathological finding (e.g., cancer, invasion, metastasis) as "normal". Use "abnormal" status.
- A finding like "Adenocarcinoma" with reference_range "No malignancy" must have status "abnormal", not "normal".
- A finding like "Uninvolved by carcinoma" with reference_range "Uninvolved" should have status "normal".

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

=== CURRENT LAB REPORT TEXT ===
{anonymized_text}

=== HISTORICAL BIOMARKER DATA (JSON) ===
{historical_payload}

Analyze the report and respond with JSON only:"""


# ─────────────────────────────────────────────────────────────────────────────
# LLM CALL — Primary OpenAI with Groq fallback
# ─────────────────────────────────────────────────────────────────────────────

async def _call_lab_llm(prompt: str) -> str:
    """
    Call LLM for lab analysis.  Groq is primary (fast, 3-5s) with
    OpenAI/GitHub Models as fallback for reliability.
    Returns raw response text.
    """
    groq_model = Config.GROQ_FALLBACK_MODELS.get("lab_summarizer")

    # ── Primary: Groq (fast) ──
    if groq_model and Config.GROQ_API_KEY:
        try:
            from groq import AsyncGroq

            client = AsyncGroq(api_key=Config.GROQ_API_KEY)
            response = await client.chat.completions.create(
                model=groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            if response and response.choices:
                content = response.choices[0].message.content
                if content:
                    logger.info(f"[GROQ] Lab analysis via {groq_model}")
                    return content.strip()
            logger.warning("Groq returned empty response, falling back to OpenAI")
        except Exception as e:
            logger.warning(f"Groq primary failed ({e}), falling back to OpenAI")

    # ── Fallback: OpenAI / GitHub Models ──
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
    Stream LLM response token-by-token.  Groq is primary (fast) with
    OpenAI streaming as fallback.
    Yields content delta strings.
    """
    groq_model = Config.GROQ_FALLBACK_MODELS.get("lab_summarizer")

    # ── Primary: Groq streaming (fast) ──
    if groq_model and Config.GROQ_API_KEY:
        try:
            from groq import AsyncGroq

            client = AsyncGroq(api_key=Config.GROQ_API_KEY)
            stream = await client.chat.completions.create(
                model=groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                stream=True,
            )
            token_count = 0
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token_count += 1
                    yield chunk.choices[0].delta.content
            if token_count > 0:
                logger.info(f"[GROQ] Streamed {token_count} tokens via {groq_model}")
                return
            logger.warning("Groq streaming returned 0 tokens, falling back to OpenAI")
        except Exception as e:
            logger.warning(f"Groq streaming failed ({e}), falling back to OpenAI")

    # ── Fallback: OpenAI / GitHub Models streaming ──
    from openai import AsyncOpenAI

    client_kwargs = {"api_key": Config.OPEN_AI_KEY}
    if Config.OPENAI_BASE_URL:
        client_kwargs["base_url"] = Config.OPENAI_BASE_URL
    client = AsyncOpenAI(**client_kwargs)

    stream = await client.chat.completions.create(
        model=Config.MODEL_CHAT,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        stream=True,
    )
    token_count = 0
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            token_count += 1
            yield chunk.choices[0].delta.content
    logger.info(f"Streamed {token_count} tokens via OpenAI ({Config.MODEL_CHAT})")


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — Non-streaming (backwards compatible)
# ─────────────────────────────────────────────────────────────────────────────

async def analyze_lab_report_copilot(
    anonymized_text: str,
    historical_snapshots: list = None,
) -> Dict:
    """
    Co-Pilot analysis: system-grouped, tiered triage, delta tracking.

    Args:
        anonymized_text: PHI-redacted lab report text.
        historical_snapshots: List of past biomarker arrays (newest first)
            from BiomarkerSnapshot.biomarkers_json.

    Returns:
        Dict with system_groups, triage, action_plan, delta_tracking, etc.

    Raises:
        ValueError: If text is empty or LLM response is unparseable.
    """
    if not anonymized_text or not anonymized_text.strip():
        raise ValueError("Empty anonymized text — nothing to analyze")

    # Build historical payload
    if historical_snapshots:
        historical_payload = json.dumps(historical_snapshots, indent=2)
    else:
        historical_payload = "No historical data available."

    prompt = COPILOT_ANALYSIS_PROMPT.format(
        anonymized_text=anonymized_text,
        historical_payload=historical_payload,
    )
    logger.info(
        f"Co-Pilot analysis: {len(anonymized_text)} chars, "
        f"{len(historical_snapshots or [])} historical snapshots"
    )

    raw_content = await _call_lab_llm(prompt)
    result = _parse_copilot_response(raw_content)
    return result


def _parse_copilot_response(raw_content: str) -> Dict:
    """Parse Co-Pilot LLM output with schema validation and graceful fallback."""
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"Co-Pilot JSON parse failed: {e}\nRaw: {cleaned[:500]}")
        raise ValueError(f"Co-Pilot LLM returned invalid JSON: {e}")

    # ── Schema validation with defaults ──
    if "system_groups" not in result:
        # If the LLM returned flat biomarkers, wrap them in a single group
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
        result["action_plan"] = {
            "clinical_followups": [],
            "nutrition": [],
            "lifestyle": [],
        }
    else:
        result["action_plan"].setdefault("clinical_followups", [])
        result["action_plan"].setdefault("nutrition", [])
        result["action_plan"].setdefault("lifestyle", [])

    result.setdefault("delta_tracking", [])
    result.setdefault("summary", "")
    result.setdefault("urgency_level", "routine")
    result.setdefault("report_type", "Lab Report")
    result.setdefault("report_date", None)

    # Recount from system_groups
    all_biomarkers = []
    for group in result["system_groups"]:
        all_biomarkers.extend(group.get("biomarkers", []))
    abnormal = [b for b in all_biomarkers if b.get("status") != "normal"]
    result["abnormal_count"] = len(abnormal)
    result["normal_count"] = len(all_biomarkers) - len(abnormal)

    # Flatten biomarkers for backward compat (used by BiomarkerSnapshot)
    result["biomarkers"] = all_biomarkers

    # Generate formatted markdown
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

    lines.append("## Clinical Co-Pilot Report")
    lines.append("")
    lines.append("### Report Overview")
    lines.append(f"- **Test Type:** {report_type}")
    if analysis.get("report_date"):
        lines.append(f"- **Report Date:** {analysis['report_date']}")
    lines.append(
        f"- **Total Parameters:** {total_biomarkers} tested | "
        f"{normal_count} normal | {abnormal_count} abnormal"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive summary
    lines.append("### Executive Summary")
    lines.append("")
    lines.append(analysis.get("summary", "No summary available."))
    lines.append("")
    lines.append("---")
    lines.append("")

    # Red flags
    red_flags = triage.get("red_flags", [])
    yellow_flags = triage.get("yellow_flags", [])

    if red_flags:
        lines.append("### Requires Doctor Consult (Red Flags)")
        lines.append("")
        for flag in red_flags:
            lines.append(f"**{flag.get('biomarker', 'Unknown')}**")
            lines.append(f"- Reason: {flag.get('reason', '')}")
            lines.append(f"- Action: {flag.get('action', '')}")
            lines.append("")

        lines.append("---")
        lines.append("")

    if yellow_flags:
        lines.append("### Lifestyle Adjustments (Yellow Flags)")
        lines.append("")
        for flag in yellow_flags:
            lines.append(f"**{flag.get('biomarker', 'Unknown')}**")
            lines.append(f"- Reason: {flag.get('reason', '')}")
            lines.append(f"- Action: {flag.get('action', '')}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # System-grouped biomarkers
    if system_groups:
        lines.append("### Detailed Results by System")
        lines.append("")
        for group in system_groups:
            system = group.get("system", "Other")
            biomarkers = group.get("biomarkers", [])
            if not biomarkers:
                continue
            lines.append(f"#### {system}")
            lines.append("")
            lines.append("| Parameter | Value | Reference | Status |")
            lines.append("|-----------|-------|-----------|--------|")
            for b in biomarkers:
                name = b.get("name", "")
                value = b.get("value", "")
                unit = b.get("unit") or ""
                display = f"{value} {unit}".strip() if unit else value
                ref = b.get("reference_range") or ""
                st = b.get("status", "")
                icon = {"normal": "Normal", "low": "Low", "high": "High",
                        "critical_low": "CRITICAL LOW", "critical_high": "CRITICAL HIGH",
                        "abnormal": "ABNORMAL"}.get(st, st)
                lines.append(f"| {name} | {display} | {ref} | {icon} |")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Action plan
    if action_plan:
        lines.append("### Action Plan")
        lines.append("")
        followups = action_plan.get("clinical_followups", [])
        nutrition = action_plan.get("nutrition", [])
        lifestyle = action_plan.get("lifestyle", [])
        if followups:
            lines.append("**Clinical Follow-ups:**")
            for item in followups:
                lines.append(f"- {item}")
            lines.append("")
        if nutrition:
            lines.append("**Nutrition:**")
            for item in nutrition:
                lines.append(f"- {item}")
            lines.append("")
        if lifestyle:
            lines.append("**Lifestyle:**")
            for item in lifestyle:
                lines.append(f"- {item}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Delta tracking
    if delta:
        lines.append("### Trend Analysis (vs Previous Reports)")
        lines.append("")
        lines.append("| Biomarker | Previous | Current | Trend | Note |")
        lines.append("|-----------|----------|---------|-------|------|")
        for d in delta:
            name = d.get("biomarker", "")
            prev = d.get("previous_value", "")
            curr = d.get("current_value", "")
            trend = d.get("trend", "")
            trend_icon = {"improving": "Improving", "declining": "Declining",
                          "stable": "Stable"}.get(trend, trend)
            note = d.get("note", "")
            lines.append(f"| {name} | {prev} | {curr} | {trend_icon} | {note} |")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Urgency
    urgency = analysis.get("urgency_level", "routine")
    lines.append("### Follow-Up")
    lines.append("")
    lines.append(f"- **Urgency:** {urgency.title()}")
    lines.append("")

    return "\n".join(lines)


async def analyze_lab_report(anonymized_text: str) -> Dict:
    """
    Send anonymized lab report text to LLM for structured analysis.

    Args:
        anonymized_text: PHI-redacted lab report text (placeholders only,
                         no real patient data).

    Returns:
        Dict with structured lab analysis: biomarkers, abnormal findings,
        summary, and recommendations.

    Raises:
        ValueError: If the text is empty or the LLM response is unparseable.
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
        ("chunk", {"text": "..."})  — a raw LLM token (JSON fragment)
        ("complete", {"result": dict})  — parsed structured result

    The caller accumulates chunks silently, then streams the
    formatted_summary word-by-word to the client.
    """
    if not anonymized_text or not anonymized_text.strip():
        raise ValueError("Empty anonymized text — nothing to analyze")

    prompt = LAB_ANALYSIS_PROMPT.format(anonymized_text=anonymized_text)
    logger.info(f"Streaming analysis for {len(anonymized_text)} chars")

    full_content = ""
    async for delta in _stream_lab_llm(prompt):
        full_content += delta
        yield ("chunk", {"text": delta})

    # Parse accumulated JSON
    result = _parse_lab_response(full_content)
    yield ("complete", {"result": result})


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL — Parse and format LLM response
# ─────────────────────────────────────────────────────────────────────────────

def _parse_lab_response(raw_content: str) -> Dict:
    """Parse raw LLM output into structured lab analysis dict."""
    # Strip markdown code fences if the model wraps output
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON: {e}\nRaw: {cleaned[:500]}")
        raise ValueError(f"LLM returned invalid JSON: {e}")

    abnormal = [b for b in result.get("biomarkers", []) if b.get("status") != "normal"]
    result["abnormal_count"] = len(abnormal)
    result["normal_count"] = len(result.get("biomarkers", [])) - len(abnormal)

    # Generate formatted markdown summary for frontend display
    result["formatted_summary"] = _format_markdown_summary(result)

    logger.info(
        f"Lab analysis complete: {len(result.get('biomarkers', []))} biomarkers, "
        f"{len(abnormal)} abnormal"
    )

    return result


def _format_markdown_summary(analysis: Dict) -> str:
    """Build a patient-friendly markdown summary from structured analysis JSON."""
    biomarkers = analysis.get("biomarkers", [])
    normal = [b for b in biomarkers if b.get("status") == "normal"]
    abnormal = [b for b in biomarkers if b.get("status") != "normal"]
    report_type = analysis.get("report_type", "Lab Report")
    total = len(biomarkers)

    lines = []
    lines.append(f"## 📋 Lab Report Analysis")
    lines.append("")
    lines.append("### 🏥 Report Overview")
    lines.append(f"- **Test Type:** {report_type}")
    lines.append(
        f"- **Total Parameters:** {total} tested | "
        f"{len(normal)} normal | {len(abnormal)} abnormal"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive summary
    lines.append("### 📊 Executive Summary")
    lines.append("")
    lines.append(analysis.get("summary", "No summary available."))
    lines.append("")
    lines.append("---")
    lines.append("")

    # Detailed parameter analysis
    lines.append("### 🔬 Detailed Parameter Analysis")
    lines.append("")

    # Normal results table
    if normal:
        lines.append("#### 🟢 NORMAL RESULTS (brief overview)")
        lines.append("")
        lines.append("| Parameter | Your Value | Normal Range | Status |")
        lines.append("|-----------|------------|--------------|--------|")
        for b in normal:
            name = b.get("name", "Unknown")
            value = b.get("value", "–")
            unit = b.get("unit") or ""
            display_value = f"{value} {unit}".strip() if unit else value
            ref = b.get("reference_range") or "–"
            lines.append(f"| {name} | {display_value} | {ref} | ✅ Normal |")
        lines.append("")

    # Abnormal results — detailed
    if abnormal:
        severity_icons = {
            "low": "🟡", "high": "🟠",
            "critical_low": "🔴", "critical_high": "🔴",
            "abnormal": "🔴",
        }
        lines.append("#### 🔴 ABNORMAL RESULTS (detailed analysis for each)")
        lines.append("")
        for i, b in enumerate(abnormal, 1):
            name = b.get("name", "Unknown")
            value = b.get("value", "–")
            unit = b.get("unit") or ""
            display_value = f"{value} {unit}".strip() if unit else value
            st = b.get("status", "abnormal")
            icon = severity_icons.get(st, "🟠")
            ref = b.get("reference_range")
            note = b.get("clinical_note")

            lines.append(f"**{i}. {name}: {display_value} — {icon} {st.replace('_', ' ').title()}**")
            lines.append("")
            lines.append(f"📈 **Your Result:**")
            lines.append(f"- Your value: {display_value}")
            if ref:
                lines.append(f"- Normal range: {ref}")
            lines.append("")
            if note:
                lines.append(f"🔍 **Clinical Significance:** {note}")
                lines.append("")
            lines.append("---")
            lines.append("")

    # Pattern analysis
    pattern = analysis.get("pattern_analysis")
    if pattern:
        lines.append("### 🔗 Pattern Analysis")
        lines.append("")
        lines.append(pattern)
        lines.append("")
        lines.append("---")
        lines.append("")

    # Recommendations
    rec = analysis.get("recommendation")
    if rec:
        lines.append("### 🎯 Recommendation")
        lines.append("")
        lines.append(rec)
        lines.append("")
        lines.append("---")
        lines.append("")

    # Follow-up
    urgency = analysis.get("urgency_level", "routine")
    lines.append("### 📅 Follow-Up")
    lines.append("")
    lines.append(f"- **Urgency:** {urgency.title()}")
    if analysis.get("follow_up_needed"):
        lines.append("- **Follow-up needed:** Yes")

    return "\n".join(lines)
