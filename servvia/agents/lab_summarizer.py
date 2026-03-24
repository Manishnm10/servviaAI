"""
ServVia 4.0 — Cloud Lab Intelligence Agent
============================================

Single-call pipeline (gpt-4.1-mini):
  One LLM call parses biomarkers, triages abnormalities, AND generates
  a patient-friendly summary with lifestyle, dietary, and home-remedy
  recommendations to bring abnormal values back to normal range.

Groq (llama-3.3-70b-versatile) is the fallback on Azure failure.
Only receives PHI-redacted text — no patient-identifiable data ever reaches the cloud.

Pipeline position:
    [Local OCR] -> [Local PHI Redaction] -> ** THIS AGENT ** -> JSON summary
"""

import json
import logging
from typing import AsyncGenerator, Dict, Tuple

from django_core.config import Config

logger = logging.getLogger("ServVia.Agents.LabSummarizer")


# ─────────────────────────────────────────────────────────────────────────────
# UNIFIED PROMPT — Standard lab analysis (single LLM call)
# ─────────────────────────────────────────────────────────────────────────────

LAB_ANALYSIS_PROMPT = """You are a Clinical Pathologist AI and Wellness Advisor. You will receive anonymized lab report text where all patient-identifiable information has been replaced with placeholders like [PERSON_1], [DATE], [PHONE_1], etc.

=== YOUR TASK ===
1. Parse ALL parameters — quantitative biomarkers (e.g., Hemoglobin: 14.2 g/dL) AND qualitative/histopathology findings (e.g., Histologic Type: Adenocarcinoma).
2. For QUANTITATIVE: extract value, unit, compare against standard clinical reference ranges.
3. For QUALITATIVE: extract the reported finding and compare against the expected normal finding.
4. Flag every clinically abnormal parameter with a brief clinical_note.
5. Determine urgency and whether follow-up is needed.
6. If multiple abnormal findings are connected, describe the pattern.
7. Write a 2-3 sentence patient-friendly summary focusing on abnormal values and clinical implications.
8. Write a clear recommendation (e.g., consult physician for X, repeat test in Y weeks).
9. For EACH abnormal biomarker, provide specific actionable guidance to bring it back to normal:
   - Nutrition: specific foods, dietary changes
   - Lifestyle: exercise, sleep, habits
   - Home remedies: safe, evidence-based natural approaches

=== ABSOLUTE RULES ===
- Do NOT re-identify redacted information.
- Do NOT fabricate values. Mark unclear values as "unreadable".
- Do NOT provide a diagnosis. Flag abnormalities and explain clinical significance only.
- If the text is not a lab report, return {{"error": "Not a lab report"}}.

=== QUANTITATIVE vs QUALITATIVE ===
Quantitative: "value" = numeric string, "unit" = unit, "reference_range" = numeric range, "status" = normal|low|high|critical_low|critical_high
Qualitative: "value" = reported finding, "unit" = null, "reference_range" = expected normal finding, "status" = normal|abnormal

=== OUTPUT FORMAT ===
Respond with ONLY valid JSON (no markdown fences):
{{
    "report_type": "string (e.g., Complete Blood Count, Histopathology Report, Metabolic Panel)",
    "biomarkers": [
        {{
            "name": "Parameter Name",
            "value": "reported value as string",
            "unit": "unit or null for qualitative",
            "reference_range": "normal range or expected normal finding",
            "status": "normal | low | high | critical_low | critical_high | abnormal",
            "clinical_note": "brief clinical significance if abnormal, null if normal"
        }}
    ],
    "pattern_analysis": "Connections between abnormal findings if any, or null",
    "urgency_level": "routine | soon | urgent | emergency",
    "follow_up_needed": true,
    "summary": "2-3 sentence patient-friendly summary of findings",
    "recommendation": "General recommendation (consult physician, repeat test, routine follow-up)",
    "corrective_guidance": [
        {{
            "biomarker": "Name of abnormal parameter",
            "status": "low | high | critical_low | critical_high | abnormal",
            "nutrition": ["Specific foods and dietary changes to help normalize this value"],
            "lifestyle": ["Exercise, sleep, habit changes"],
            "home_remedies": ["Safe, evidence-based natural approaches"]
        }}
    ]
}}

CRITICAL RULES:
- NEVER use "N/A" for reference_range. Qualitative reference_range must be the expected normal.
- NEVER mark a pathological finding (cancer, invasion, metastasis) as "normal".
- corrective_guidance: ONLY for abnormal biomarkers. Each entry must have all three arrays (nutrition, lifestyle, home_remedies), even if some are empty.
- Recommendations must be safe, evidence-based, and clearly state when professional medical care is needed.

=== LAB REPORT TEXT ===
{anonymized_text}

Respond with JSON only:"""


# ─────────────────────────────────────────────────────────────────────────────
# UNIFIED COPILOT PROMPT — System-grouped + triage + delta + guidance
# ─────────────────────────────────────────────────────────────────────────────

COPILOT_PROMPT = """You are a Clinical Pathologist AI and Wellness Advisor. You will receive anonymized lab report text and optionally historical biomarker data.

=== YOUR TASK ===
1. Parse ALL parameters (quantitative + qualitative).
2. Group biomarkers by bodily system (e.g., Hematological, Hepatic, Renal, Metabolic, Thyroid, Cardiac).
3. Triage abnormalities: Red Flags (requires physician) vs Yellow Flags (lifestyle adjustments).
4. If historical data is provided, compute delta tracking (trend per biomarker).
5. Determine urgency level.
6. Write a 2-3 sentence patient-friendly summary.
7. Create a concrete action plan with clinical follow-ups, nutrition, and lifestyle changes.
8. For EACH abnormal biomarker, provide specific corrective guidance (nutrition, lifestyle, home remedies).

=== ABSOLUTE RULES ===
- Do NOT re-identify redacted information.
- Do NOT fabricate values. Mark unclear values as "unreadable".
- Do NOT diagnose. Flag abnormalities and explain clinical significance.
- If historical data is empty, delta_tracking must be [].

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
                    "reference_range": "normal range or expected normal finding",
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
                "action": "Specific clinical action"
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
    "delta_tracking": [
        {{
            "biomarker": "Parameter Name",
            "previous_value": "value from most recent historical snapshot",
            "current_value": "value from current report",
            "trend": "improving | declining | stable",
            "note": "Brief explanation of the change"
        }}
    ],
    "urgency_level": "routine | soon | urgent | emergency",
    "summary": "2-3 sentence patient-friendly summary of findings",
    "action_plan": {{
        "clinical_followups": ["Recommended tests or specialist consults"],
        "nutrition": ["Dietary recommendations based on abnormal findings"],
        "lifestyle": ["Exercise, sleep, habit recommendations"]
    }},
    "corrective_guidance": [
        {{
            "biomarker": "Name of abnormal parameter",
            "status": "low | high | critical_low | critical_high | abnormal",
            "nutrition": ["Specific foods and dietary changes to help normalize this value"],
            "lifestyle": ["Exercise, sleep, habit changes"],
            "home_remedies": ["Safe, evidence-based natural approaches"]
        }}
    ]
}}

CRITICAL RULES:
- Each biomarker appears in exactly ONE system_group.
- Red flags: critical_low, critical_high, or clinically dangerous abnormal findings.
- Yellow flags: low, high, or mildly abnormal findings manageable with lifestyle.
- Normal biomarkers go into system_groups but NOT into triage.
- delta_tracking: only biomarkers present in BOTH current and historical data.
- action_plan must always have all three keys, even if arrays are empty.
- corrective_guidance: ONLY for abnormal biomarkers with all three arrays.

=== CURRENT LAB REPORT TEXT ===
{anonymized_text}

=== HISTORICAL BIOMARKER DATA (JSON) ===
{historical_payload}

Respond with JSON only:"""


# ─────────────────────────────────────────────────────────────────────────────
# LLM CALL — Single unified call (gpt-4.1-mini)
# ─────────────────────────────────────────────────────────────────────────────

def _make_azure_client():
    from openai import AsyncAzureOpenAI
    return AsyncAzureOpenAI(
        api_key=Config.AZURE_OPENAI_API_KEY,
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        api_version=Config.AZURE_OPENAI_API_VERSION,
    )


_SYSTEM_MSG = (
    "You are a Clinical Pathologist AI assistant performing structured medical lab report analysis. "
    "The report text you receive contains anonymized placeholders (e.g., [PERSON_1], [DATE]) "
    "where patient-identifiable information has been redacted for privacy. "
    "Analyze the clinical values and respond with structured JSON only."
)


async def _call_llm(prompt: str, temperature: float = 0) -> str:
    """
    Single LLM call via Azure gpt-4.1-mini with Groq fallback.
    Uses system+user message split to avoid Azure content-filter false positives.
    """
    messages = [
        {"role": "system", "content": _SYSTEM_MSG},
        {"role": "user", "content": prompt},
    ]

    # ── Primary: Azure gpt-4.1-mini ──
    try:
        client = _make_azure_client()
        response = await client.chat.completions.create(
            model=Config.MODEL_CHAT,
            messages=messages,
            temperature=temperature,
        )
        content = response.choices[0].message.content
        if content:
            logger.info(f"[LAB][Azure] Analysis via {Config.MODEL_CHAT}")
            return content.strip()
        logger.warning("[LAB] Azure gpt-4.1-mini returned empty, falling back to Groq")
    except Exception as e:
        logger.warning(f"[LAB] Azure gpt-4.1-mini failed ({e}), falling back to Groq")

    # ── Fallback: Groq ──
    groq_model = Config.GROQ_FALLBACK_MODELS.get("lab_summarizer")
    if not groq_model or not Config.GROQ_API_KEY:
        raise ValueError("Azure failed and no Groq fallback configured")
    from groq import AsyncGroq
    client = AsyncGroq(api_key=Config.GROQ_API_KEY)
    response = await client.chat.completions.create(
        model=groq_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Both Azure and Groq returned empty")
    logger.info(f"[LAB][GROQ] Analysis via {groq_model}")
    return content.strip()


async def _stream_llm(prompt: str) -> AsyncGenerator[str, None]:
    """
    Stream gpt-4.1-mini response token-by-token with Groq fallback.
    """
    messages = [
        {"role": "system", "content": _SYSTEM_MSG},
        {"role": "user", "content": prompt},
    ]

    # ── Primary: Azure streaming ──
    try:
        client = _make_azure_client()
        stream = await client.chat.completions.create(
            model=Config.MODEL_CHAT,
            messages=messages,
            temperature=0,
            stream=True,
        )
        token_count = 0
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                token_count += 1
                yield chunk.choices[0].delta.content
        if token_count > 0:
            logger.info(f"[LAB][Azure] Streamed {token_count} tokens via {Config.MODEL_CHAT}")
            return
        logger.warning("[LAB] Azure streaming returned 0 tokens, falling back to Groq")
    except Exception as e:
        logger.warning(f"[LAB] Azure streaming failed ({e}), falling back to Groq")

    # ── Fallback: Groq streaming ──
    groq_model = Config.GROQ_FALLBACK_MODELS.get("lab_summarizer")
    if not groq_model or not Config.GROQ_API_KEY:
        return
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
    logger.info(f"[LAB][GROQ] Streamed {token_count} tokens via {groq_model}")


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — Co-Pilot (primary entry point)
# ─────────────────────────────────────────────────────────────────────────────

async def analyze_lab_report_copilot(
    anonymized_text: str,
    historical_snapshots: list = None,
) -> Dict:
    """
    Co-Pilot analysis: system-grouped, tiered triage, delta tracking,
    and corrective guidance — all in a single LLM call.

    Args:
        anonymized_text: PHI-redacted lab report text.
        historical_snapshots: List of past biomarker arrays (newest first).

    Returns:
        Dict with system_groups, triage, action_plan, delta_tracking, summary,
        corrective_guidance, etc.
    """
    if not anonymized_text or not anonymized_text.strip():
        raise ValueError("Empty anonymized text — nothing to analyze")

    historical_payload = (
        json.dumps(historical_snapshots, indent=2)
        if historical_snapshots
        else "No historical data available."
    )

    logger.info(
        f"Co-Pilot start: {len(anonymized_text)} chars, "
        f"{len(historical_snapshots or [])} historical snapshots"
    )

    prompt = COPILOT_PROMPT.format(
        anonymized_text=anonymized_text,
        historical_payload=historical_payload,
    )
    raw = await _call_llm(prompt)
    data = _parse_json(raw, stage="Co-Pilot")

    return _build_copilot_result(data)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — Standard analysis (non-streaming)
# ─────────────────────────────────────────────────────────────────────────────

async def analyze_lab_report(anonymized_text: str) -> Dict:
    """
    Standard lab analysis — single LLM call with corrective guidance.

    Args:
        anonymized_text: PHI-redacted lab report text.

    Returns:
        Dict with structured lab analysis: biomarkers, abnormal findings,
        summary, recommendations, and corrective guidance.
    """
    if not anonymized_text or not anonymized_text.strip():
        raise ValueError("Empty anonymized text — nothing to analyze")

    logger.info(f"Lab analysis start: {len(anonymized_text)} chars")

    prompt = LAB_ANALYSIS_PROMPT.format(anonymized_text=anonymized_text)
    raw = await _call_llm(prompt)
    data = _parse_json(raw, stage="Lab")

    return _build_lab_result(data)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — Streaming
# ─────────────────────────────────────────────────────────────────────────────

async def stream_lab_report_analysis(
    anonymized_text: str,
) -> AsyncGenerator[Tuple[str, dict], None]:
    """
    Stream lab report analysis — single LLM call, streamed token-by-token.

    Yields (event_type, data) tuples:
        ("chunk", {"text": "..."})     — token stream
        ("complete", {"result": dict}) — fully parsed result
    """
    if not anonymized_text or not anonymized_text.strip():
        raise ValueError("Empty anonymized text — nothing to analyze")

    logger.info(f"Streaming: start for {len(anonymized_text)} chars")

    prompt = LAB_ANALYSIS_PROMPT.format(anonymized_text=anonymized_text)
    full_response = ""
    async for delta in _stream_llm(prompt):
        full_response += delta
        yield ("chunk", {"text": delta})

    data = _parse_json(full_response, stage="Stream")
    result = _build_lab_result(data)
    yield ("complete", {"result": result})


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL — Build result dicts
# ─────────────────────────────────────────────────────────────────────────────

def _parse_json(raw: str, stage: str = "") -> Dict:
    """Strip markdown fences and parse JSON. Raises ValueError on failure."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"{stage} JSON parse failed: {e}\nRaw: {cleaned[:500]}")
        raise ValueError(f"{stage} LLM returned invalid JSON: {e}")


def _build_lab_result(data: Dict) -> Dict:
    """Finalize unified lab analysis result."""
    result = dict(data)

    biomarkers = result.get("biomarkers", [])
    abnormal = [b for b in biomarkers if b.get("status") != "normal"]
    result["abnormal_count"] = len(abnormal)
    result["normal_count"] = len(biomarkers) - len(abnormal)
    result.setdefault("follow_up_needed", bool(abnormal))
    result.setdefault("summary", "")
    result.setdefault("recommendation", "")
    result.setdefault("corrective_guidance", [])

    result["formatted_summary"] = _format_markdown_summary(result)

    logger.info(
        f"Lab analysis complete: {len(biomarkers)} biomarkers, "
        f"{len(abnormal)} abnormal | urgency={result.get('urgency_level')}"
    )
    return result


def _build_copilot_result(data: Dict) -> Dict:
    """Finalize unified Co-Pilot result."""
    result = dict(data)

    # Ensure triage structure
    if "triage" not in result:
        result["triage"] = {"red_flags": [], "yellow_flags": []}
    else:
        result["triage"].setdefault("red_flags", [])
        result["triage"].setdefault("yellow_flags", [])

    # Ensure action_plan structure
    action_plan = result.get("action_plan", {})
    result["action_plan"] = {
        "clinical_followups": action_plan.get("clinical_followups", []),
        "nutrition": action_plan.get("nutrition", []),
        "lifestyle": action_plan.get("lifestyle", []),
    }

    result.setdefault("delta_tracking", [])
    result.setdefault("report_type", "Lab Report")
    result.setdefault("report_date", None)
    result.setdefault("summary", "")
    result.setdefault("corrective_guidance", [])

    # Flatten biomarkers for backward compat (BiomarkerSnapshot)
    all_biomarkers = []
    for group in result.get("system_groups", []):
        all_biomarkers.extend(group.get("biomarkers", []))
    abnormal = [b for b in all_biomarkers if b.get("status") != "normal"]
    result["abnormal_count"] = len(abnormal)
    result["normal_count"] = len(all_biomarkers) - len(abnormal)
    result["biomarkers"] = all_biomarkers

    result["formatted_summary"] = _format_copilot_markdown(result)

    logger.info(
        f"Co-Pilot complete: {len(all_biomarkers)} biomarkers, "
        f"{len(abnormal)} abnormal, "
        f"{len(result['triage']['red_flags'])} red flags, "
        f"{len(result['triage']['yellow_flags'])} yellow flags"
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# FORMATTERS — Pure Python markdown generation
# ─────────────────────────────────────────────────────────────────────────────

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

    lines.append("### 📊 Executive Summary")
    lines.append("")
    lines.append(analysis.get("summary", "No summary available."))
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("### 🔬 Detailed Parameter Analysis")
    lines.append("")

    if normal:
        lines.append("#### 🟢 NORMAL RESULTS (brief overview)")
        lines.append("")
        lines.append("| Parameter | Value | Reference | Status |")
        lines.append("|-----------|-------|-----------|--------|")
        for b in normal:
            name = b.get("name", "Unknown")
            value = b.get("value", "–")
            unit = b.get("unit") or ""
            display_value = f"{value} {unit}".strip() if unit else value
            ref = b.get("reference_range") or "–"
            lines.append(f"| {name} | {display_value} | {ref} | ✅ Normal |")
        lines.append("")

    if abnormal:
        severity_icons = {
            "low": "🟡", "high": "🟠",
            "critical_low": "🔴", "critical_high": "🔴",
            "abnormal": "🔴",
        }
        lines.append("#### 🔴 ABNORMAL RESULTS (detailed analysis)")
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

    pattern = analysis.get("pattern_analysis")
    if pattern:
        lines.append("### 🔗 Pattern Analysis")
        lines.append("")
        lines.append(pattern)
        lines.append("")
        lines.append("---")
        lines.append("")

    rec = analysis.get("recommendation")
    if rec:
        lines.append("### 🎯 Recommendation")
        lines.append("")
        lines.append(rec)
        lines.append("")
        lines.append("---")
        lines.append("")

    # Corrective guidance for abnormal values
    guidance = analysis.get("corrective_guidance", [])
    if guidance:
        lines.append("### 🌿 How to Bring Abnormal Values Back to Normal")
        lines.append("")
        for g in guidance:
            name = g.get("biomarker", "Unknown")
            st = g.get("status", "abnormal")
            lines.append(f"#### {name} ({st.replace('_', ' ').title()})")
            lines.append("")
            nutrition = g.get("nutrition", [])
            if nutrition:
                lines.append("**🥗 Nutrition:**")
                for item in nutrition:
                    lines.append(f"- {item}")
                lines.append("")
            lifestyle = g.get("lifestyle", [])
            if lifestyle:
                lines.append("**🏃 Lifestyle:**")
                for item in lifestyle:
                    lines.append(f"- {item}")
                lines.append("")
            remedies = g.get("home_remedies", [])
            if remedies:
                lines.append("**🏠 Home Remedies:**")
                for item in remedies:
                    lines.append(f"- {item}")
                lines.append("")
            lines.append("---")
            lines.append("")

    urgency = analysis.get("urgency_level", "routine")
    lines.append("### 📅 Follow-Up")
    lines.append("")
    lines.append(f"- **Urgency:** {urgency.title()}")
    if analysis.get("follow_up_needed"):
        lines.append("- **Follow-up needed:** Yes")

    return "\n".join(lines)


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

    lines.append("### Executive Summary")
    lines.append("")
    lines.append(analysis.get("summary", "No summary available."))
    lines.append("")
    lines.append("---")
    lines.append("")

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

    # Corrective guidance for abnormal values
    guidance = analysis.get("corrective_guidance", [])
    if guidance:
        lines.append("### How to Bring Abnormal Values Back to Normal")
        lines.append("")
        for g in guidance:
            name = g.get("biomarker", "Unknown")
            st = g.get("status", "abnormal")
            lines.append(f"#### {name} ({st.replace('_', ' ').title()})")
            lines.append("")
            nutrition = g.get("nutrition", [])
            if nutrition:
                lines.append("**Nutrition:**")
                for item in nutrition:
                    lines.append(f"- {item}")
                lines.append("")
            lifestyle = g.get("lifestyle", [])
            if lifestyle:
                lines.append("**Lifestyle:**")
                for item in lifestyle:
                    lines.append(f"- {item}")
                lines.append("")
            remedies = g.get("home_remedies", [])
            if remedies:
                lines.append("**Home Remedies:**")
                for item in remedies:
                    lines.append(f"- {item}")
                lines.append("")
            lines.append("---")
            lines.append("")

    urgency = analysis.get("urgency_level", "routine")
    lines.append("### Follow-Up")
    lines.append("")
    lines.append(f"- **Urgency:** {urgency.title()}")
    lines.append("")

    return "\n".join(lines)
