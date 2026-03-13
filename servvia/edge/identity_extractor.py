"""
Identity Fingerprinting — Lightweight Patient Demographics Extraction
=====================================================================

Extracts patient name, age, sex, and IDs from RAW OCR text (before PHI
redaction) using a fast regex-first approach with LLM fallback.

This runs BEFORE the heavy summarization pipeline to enable multi-patient
routing and human-in-the-loop profile confirmation.
"""

import json
import logging
import re
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger("ServVia.Edge.IdentityExtractor")


@dataclass
class IdentityFingerprint:
    patient_name: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None  # M / F / Other
    patient_id: Optional[str] = None
    srf_id: Optional[str] = None
    report_date: Optional[str] = None  # ISO date string

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def has_identifiers(self) -> bool:
        return bool(self.patient_name or self.patient_id or self.srf_id)


# ─────────────────────────────────────────────────────────────────────────────
# REGEX EXTRACTION — fast, no LLM cost
# ─────────────────────────────────────────────────────────────────────────────

_NAME_PATTERNS = [
    re.compile(r"(?:Patient\s*(?:Name)?|Name\s*of\s*(?:the\s*)?Patient)\s*[:\-]\s*(.+)", re.IGNORECASE),
    re.compile(r"(?:Mr\.|Mrs\.|Ms\.|Dr\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", re.IGNORECASE),
]

_AGE_PATTERNS = [
    re.compile(r"Age\s*[:\-/]\s*(\d{1,3})\s*(?:years?|yrs?|Y)?", re.IGNORECASE),
    re.compile(r"(\d{1,3})\s*(?:years?|yrs?)\s*(?:old)?", re.IGNORECASE),
    re.compile(r"Age/Sex\s*[:\-]\s*(\d{1,3})\s*/\s*([MFO])", re.IGNORECASE),
]

_SEX_PATTERNS = [
    re.compile(r"(?:Sex|Gender)\s*[:\-]\s*(Male|Female|M|F|Other)", re.IGNORECASE),
    re.compile(r"Age/Sex\s*[:\-]\s*\d{1,3}\s*/\s*([MFO])", re.IGNORECASE),
]

_ID_PATTERNS = [
    re.compile(r"(?:Patient\s*ID|PID|MRN|UHID|Reg\.?\s*No)\s*[:\-]\s*([A-Za-z0-9\-/]+)", re.IGNORECASE),
]

_SRF_PATTERNS = [
    re.compile(r"(?:SRF\s*(?:ID|No)?|Sample\s*(?:ID|No)|Lab\s*(?:ID|No)|Barcode)\s*[:\-]\s*([A-Za-z0-9\-/]+)", re.IGNORECASE),
]

_DATE_PATTERNS = [
    re.compile(r"(?:Report\s*Date|Date\s*of\s*Report|Collection\s*Date|Collected\s*on)\s*[:\-]\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"(?:Report\s*Date|Date\s*of\s*Report)\s*[:\-]\s*(\d{1,2}\s+\w+\s+\d{4})", re.IGNORECASE),
]


def _normalize_sex(raw: str) -> Optional[str]:
    raw = raw.strip().upper()
    if raw in ("M", "MALE"):
        return "M"
    if raw in ("F", "FEMALE"):
        return "F"
    if raw in ("O", "OTHER"):
        return "Other"
    return None


def _regex_extract(raw_text: str) -> IdentityFingerprint:
    """Fast regex-based extraction from raw OCR text."""
    fp = IdentityFingerprint()

    # Patient name
    for pat in _NAME_PATTERNS:
        m = pat.search(raw_text)
        if m:
            name = m.group(1).strip().rstrip(".,;:")
            # Filter out obvious non-names (lab headers, etc.)
            if len(name) > 2 and not any(kw in name.lower() for kw in ["laboratory", "hospital", "clinic", "diagnostic"]):
                fp.patient_name = name
                break

    # Age — try combined Age/Sex first
    for pat in _AGE_PATTERNS:
        m = pat.search(raw_text)
        if m:
            try:
                age = int(m.group(1))
                if 0 < age < 150:
                    fp.age = age
                    # If this pattern also captures sex
                    if m.lastindex and m.lastindex >= 2:
                        fp.sex = _normalize_sex(m.group(2))
                    break
            except (ValueError, IndexError):
                continue

    # Sex (if not already captured)
    if not fp.sex:
        for pat in _SEX_PATTERNS:
            m = pat.search(raw_text)
            if m:
                fp.sex = _normalize_sex(m.group(1))
                if fp.sex:
                    break

    # Patient ID
    for pat in _ID_PATTERNS:
        m = pat.search(raw_text)
        if m:
            fp.patient_id = m.group(1).strip()
            break

    # SRF ID
    for pat in _SRF_PATTERNS:
        m = pat.search(raw_text)
        if m:
            fp.srf_id = m.group(1).strip()
            break

    # Report date
    for pat in _DATE_PATTERNS:
        m = pat.search(raw_text)
        if m:
            fp.report_date = m.group(1).strip()
            break

    return fp


# ─────────────────────────────────────────────────────────────────────────────
# LLM FALLBACK — only called if regex misses critical fields
# ─────────────────────────────────────────────────────────────────────────────

_IDENTITY_PROMPT = """Extract patient demographics from this lab report header. Return ONLY valid JSON.

If a field is not found, use null.

{{
    "patient_name": "string or null",
    "age": integer or null,
    "sex": "M" or "F" or "Other" or null,
    "patient_id": "string or null",
    "srf_id": "string or null",
    "report_date": "DD/MM/YYYY or null"
}}

Report text (first 1500 chars):
{text}

JSON:"""


async def _llm_extract(raw_text: str) -> IdentityFingerprint:
    """LLM-based extraction — used as fallback when regex misses fields."""
    from django_core.config import Config

    # Only send the first 1500 chars (header area) to minimize cost
    header = raw_text[:1500]
    prompt = _IDENTITY_PROMPT.format(text=header)

    try:
        groq_model = Config.GROQ_FALLBACK_MODELS.get("lab_summarizer")
        if groq_model and Config.GROQ_API_KEY:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=Config.GROQ_API_KEY)
            response = await client.chat.completions.create(
                model=groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=200,
            )
            content = response.choices[0].message.content.strip()
        else:
            from openai import AsyncOpenAI
            client_kwargs = {"api_key": Config.OPEN_AI_KEY}
            if Config.OPENAI_BASE_URL:
                client_kwargs["base_url"] = Config.OPENAI_BASE_URL
            client = AsyncOpenAI(**client_kwargs)
            response = await client.chat.completions.create(
                model=Config.MODEL_CHAT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=200,
            )
            content = response.choices[0].message.content.strip()

        # Strip markdown fences
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines)

        data = json.loads(content)
        fp = IdentityFingerprint(
            patient_name=data.get("patient_name"),
            age=data.get("age"),
            sex=_normalize_sex(data["sex"]) if data.get("sex") else None,
            patient_id=data.get("patient_id"),
            srf_id=data.get("srf_id"),
            report_date=data.get("report_date"),
        )
        logger.info(f"[LLM] Identity extraction: {fp.patient_name}, age={fp.age}")
        return fp

    except Exception as e:
        logger.warning(f"LLM identity extraction failed: {e}")
        return IdentityFingerprint()


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

async def extract_identity(raw_text: str) -> IdentityFingerprint:
    """
    Extract patient identity from raw OCR text.
    Uses regex first; falls back to LLM only if name is missing.

    Args:
        raw_text: Raw OCR output (BEFORE PHI redaction).

    Returns:
        IdentityFingerprint with extracted demographics.
    """
    if not raw_text or not raw_text.strip():
        return IdentityFingerprint()

    fp = _regex_extract(raw_text)
    logger.info(
        f"Regex extraction: name={fp.patient_name}, age={fp.age}, "
        f"sex={fp.sex}, pid={fp.patient_id}"
    )

    # Fall back to LLM only if we missed the patient name
    if not fp.patient_name:
        logger.info("Name not found via regex — trying LLM extraction")
        llm_fp = await _llm_extract(raw_text)
        # Merge: LLM fills in blanks, regex values take priority
        if not fp.patient_name and llm_fp.patient_name:
            fp.patient_name = llm_fp.patient_name
        if fp.age is None and llm_fp.age is not None:
            fp.age = llm_fp.age
        if not fp.sex and llm_fp.sex:
            fp.sex = llm_fp.sex
        if not fp.patient_id and llm_fp.patient_id:
            fp.patient_id = llm_fp.patient_id
        if not fp.srf_id and llm_fp.srf_id:
            fp.srf_id = llm_fp.srf_id
        if not fp.report_date and llm_fp.report_date:
            fp.report_date = llm_fp.report_date

    return fp
