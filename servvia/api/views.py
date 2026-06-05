"""
ServVia 4.0 — Unified Healthcare Pipeline View
================================================

Strict neurosymbolic pipeline with guaranteed safe output:

    Step A: Emergency Detection (hardcoded safety layer — no LLM)
    Step B: Chronobiology Context (passive biological state inference)
    Step C: Async Orchestrator (single event loop):
            - Translation (skip if English)
            - RAG Retrieval + Diagnostician (parallel for serious queries)
            - Proposer → Critic (multi-agent verification)
            - Trust Engine (evidence scoring)
            - Back-translation (skip if English)
    Step D: Safety Validation (temporal neurosymbolic drug-herb check)
    Step E: Final Output (verified response or hardcoded fallback — NEVER raw chunks)

Author: ServVia Engineering
Version: 4.0.0
"""

import asyncio
import json
import logging
import os
import queue
import re
import sys
import threading
import time as _time
from datetime import datetime, timezone, timedelta

from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

# ─── Legacy infrastructure (auth, translate, RAG) ───────────────────────
from legacy_healthcare.api.utils import (
    authenticate_user_based_on_email,
    handle_input_query,
    mask_email,
    preprocess_user_data,
)
from legacy_healthcare.common.utils import (
    get_user_chat_history,
    save_message_obj,
    postprocess_and_translate_query_response,
)
from legacy_healthcare.language_service.translation import (
    detect_language_and_translate_to_english,
)
from legacy_healthcare.rag_service.execute_rag import execute_rag_pipeline

# ─── New ServVia modules ────────────────────────────────────────────────
from core.models import (
    MedicationRecord,
    RemedyProposal,
    UserMedicalProfile,
    ValidationResult,
)
from chronobiology.inference import ChronobiologyEngine
from neurosymbolic.temporal_validator import (
    TemporalSafetyValidator,
    HERB_ALIASES,
    INTERACTION_DATABASE,
)
from legacy_healthcare.rag_service.execute_rag import EmergencySystem

# Trust Engine for scientific validation
try:
    from core_temporal.trust_engine.engine import get_trust_engine
    TRUST_ENGINE_AVAILABLE = True
except ImportError:
    TRUST_ENGINE_AVAILABLE = False

# Graph RAG for outcome-adaptive remedy ranking
try:
    from graph_rag.client import get_graph_client
    GRAPH_RAG_AVAILABLE = True
except ImportError:
    GRAPH_RAG_AVAILABLE = False

# Multi-Agent verification (serious queries: Diagnostician → Proposer → Critic)
try:
    from agents.graph import run_verification_pipeline, run_diagnostician_standalone
    from agents.prompts import FALLBACK_RESPONSE as _AGENT_FALLBACK
    MULTI_AGENT_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Multi-Agent graph not available: {e}")
    MULTI_AGENT_AVAILABLE = False
    _AGENT_FALLBACK = (
        "I'm sorry, our system encountered a temporary issue. "
        "Please try your query again in a moment."
    )

logger = logging.getLogger("ServVia.PipelineView")

# ─── Singleton instances (initialized once at import time) ──────────────
_chrono_engine = ChronobiologyEngine()
_safety_validator = TemporalSafetyValidator()


# ═══════════════════════════════════════════════════════════════════════════
# TRACE — Guaranteed terminal output using original stdout
# ═══════════════════════════════════════════════════════════════════════════

_TRACE_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pipeline.log"
)


def _trace(msg: str):
    """Write timestamped trace to file AND stdout."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    # Safe ASCII version for Windows console (cp1252 can't handle Unicode)
    safe_line = line.encode("ascii", errors="replace").decode("ascii")
    # File trace (UTF-8, guaranteed on all platforms)
    try:
        with open(_TRACE_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass
    # Console trace (sys.__stdout__ bypasses all monkey-patching)
    try:
        sys.__stdout__.write(safe_line + "\n")
        sys.__stdout__.flush()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# HELPER: BUILD MEDICAL PROFILE FROM USER PROFILE DATA
# ═══════════════════════════════════════════════════════════════════════════

def _build_medical_profile(email_id: str, profile_data: dict = None) -> UserMedicalProfile:
    if not profile_data:
        return UserMedicalProfile(
            user_id=email_id,
            allergies=[],
            current_medications=[],
            symptom_onset_hours=0,
        )

    med_records = []
    raw_meds = profile_data.get("current_medications", []) or []
    for med_name in raw_meds:
        if isinstance(med_name, str) and med_name.strip():
            med_records.append(
                MedicationRecord(
                    drug_name=med_name.strip(),
                    start_date=datetime.now(timezone.utc) - timedelta(days=90),
                    end_date=None,
                )
            )

    return UserMedicalProfile(
        user_id=email_id,
        allergies=profile_data.get("allergies", []) or [],
        current_medications=med_records,
        symptom_onset_hours=0,
    )


# ═══════════════════════════════════════════════════════════════════════════
# HELPER: EXTRACT HERBS FROM LLM RESPONSE FOR SAFETY VALIDATION
# ═══════════════════════════════════════════════════════════════════════════
#
# Defense-in-depth extraction:
#   PRIMARY  — Parse structured <!-- HERBS_USED: ... --> tag from LLM output
#              (the Proposer prompt mandates this declaration).
#   FALLBACK — Regex scan with full synonym resolution via HERB_ALIASES
#              from the temporal validator (same source of truth).
#   FINAL    — Union of both methods. A herb caught by *either* path
#              proceeds to the deterministic safety engine.
#
# All returned names are CANONICAL (e.g. "curcumin" → "turmeric"), so the
# INTERACTION_DATABASE always matches.
# ═══════════════════════════════════════════════════════════════════════════

# ── Build unified scan table at import time ──────────────────────────────
# Maps every known surface form (alias or canonical name) → canonical name.
# Sources: HERB_ALIASES from temporal_validator + canonical names from
#          INTERACTION_DATABASE + additional common herbs.

_ADDITIONAL_CANONICAL_HERBS = [
    # Herbs in the old scan list that have no INTERACTION_DATABASE entry
    # and no alias mapping — we still want to detect them.
    "ginseng", "peppermint", "tulsi", "neem", "amla",
    "fennel", "cumin", "grapefruit", "honey",
    "aloe vera", "moringa", "triphala", "brahmi", "shatavari",
    "eucalyptus", "lavender", "clove", "cardamom", "black pepper",
    "oregano", "thyme", "rosemary", "saffron",
    "black cohosh", "evening primrose",
    "goldenseal", "marshmallow root", "slippery elm", "dandelion",
    "nettle", "elderberry", "astragalus", "cat's claw", "devil's claw",
    "goji berry", "maca", "rhodiola", "passionflower",
    "lemon balm", "jaggery", "coconut oil", "sesame oil", "mustard oil",
    "camphor", "menthol", "ajwain", "carom seeds", "asafoetida",
    "feverfew", "cranberry", "dong quai",
]

def _build_synonym_table() -> dict[str, str]:
    """Build surface-form → canonical-name mapping (once, at import)."""
    table: dict[str, str] = {}

    # 1. All canonical herb names from the interaction database
    for canonical in INTERACTION_DATABASE:
        table[canonical.lower()] = canonical.lower()

    # 2. All aliases from the temporal validator
    for alias, canonical in HERB_ALIASES.items():
        table[alias.lower()] = canonical.lower()

    # 3. Additional canonical herbs (identity mapping)
    for herb in _ADDITIONAL_CANONICAL_HERBS:
        h = herb.lower()
        if h not in table:
            table[h] = h

    return table

# Surface form → canonical name (e.g. "curcumin" → "turmeric")
_SYNONYM_TABLE: dict[str, str] = _build_synonym_table()

# Pre-compiled regex patterns keyed by surface form, longest-first so
# "ginkgo biloba" matches before "ginkgo".
_SCAN_PATTERNS: list[tuple[re.Pattern, str]] = sorted(
    [
        (re.compile(r'\b' + re.escape(surface) + r'\b', re.IGNORECASE), canonical)
        for surface, canonical in _SYNONYM_TABLE.items()
    ],
    key=lambda pair: len(pair[0].pattern),
    reverse=True,  # longest surface forms first
)

# Primary substitute: the single best swap used for in-text replacement.
_PRIMARY_SUBSTITUTE = {
    "honey":        "jaggery",
    "ginger":       "cinnamon",
    "turmeric":     "saffron",
    "garlic":       "asafoetida (hing)",
    "cinnamon":     "cardamom",
    "chamomile":    "peppermint",
    "peppermint":   "spearmint",
    "aloe vera":    "cucumber gel",
    "neem":         "tea tree oil (diluted)",
    "fennel":       "anise",
    "cumin":        "coriander",
    "fenugreek":    "fennel",
    "licorice":     "fennel",
    "amla":         "lemon",
    "ashwagandha":  "holy basil (tulsi)",
    "tulsi":        "peppermint",
    "eucalyptus":   "peppermint",
    "lavender":     "lemon balm",
    "clove":        "cardamom",
    "black pepper": "white pepper",
    "green tea":    "rooibos",
    "elderberry":   "rose hip",
    "camphor":      "menthol",
    "mustard oil":  "sesame oil",
    "ajwain":       "cumin",
    "asafoetida":   "garlic",
    "milk thistle": "dandelion root",
    "passionflower":"lemon balm",
    "feverfew":     "peppermint oil",
    "dong quai":    "shatavari",
    "cranberry":    "blueberry",
    "saw palmetto": "pumpkin seed oil",
    "ginkgo":       "brahmi",
    "st. john's wort": "lemon balm",
    "kava":         "valerian",
}

# Full alternatives list shown in the Ingredient Alert summary.
_ALLERGEN_SUBSTITUTE_MAP = {
    "honey":       "jaggery, maple syrup, agave nectar, or date syrup",
    "ginger":      "cinnamon, licorice root, warm lemon water with black pepper, or cardamom",
    "turmeric":    "saffron (small amounts), cinnamon, black pepper in warm milk, or rosemary",
    "garlic":      "asafoetida (hing), onion, leek, or chives",
    "cinnamon":    "cardamom, star anise, nutmeg (small amounts), or vanilla",
    "chamomile":   "peppermint, lemon balm, lavender tea, or rooibos",
    "peppermint":  "spearmint, fennel tea, lemon balm, or holy basil (tulsi)",
    "aloe vera":   "cucumber gel, calendula, or coconut oil (topical)",
    "neem":        "tea tree oil (diluted), eucalyptus steam, or turmeric paste",
    "fennel":      "anise seeds, dill seeds, or caraway",
    "cumin":       "coriander, caraway, or fennel seeds",
    "fenugreek":   "fennel seeds, mustard seeds, or cumin",
    "licorice":    "fennel tea, anise root tea, or marshmallow root",
    "amla":        "lemon juice, hibiscus tea, or vitamin C-rich fruits",
    "ashwagandha": "holy basil (tulsi), shatavari, or brahmi",
    "tulsi":       "peppermint, lemon balm, or oregano",
    "eucalyptus":  "peppermint steam, camphor steam (diluted), or menthol balm",
    "lavender":    "lemon balm, chamomile, or valerian",
    "clove":       "cardamom, cinnamon, or nutmeg (small amounts)",
    "black pepper":"white pepper, long pepper (pippali), or cayenne (small amounts)",
    "green tea":   "rooibos, white tea, or hibiscus tea",
    "elderberry":  "rose hip tea, vitamin C-rich fruits (amla, citrus), or echinacea",
    "camphor":     "menthol balm, eucalyptus oil (diluted), or peppermint oil",
    "mustard oil": "sesame oil, coconut oil, or olive oil",
    "ajwain":      "cumin seeds, fennel seeds, or caraway seeds",
    "asafoetida":  "garlic, onion powder, or leek",
    "milk thistle": "dandelion root tea, artichoke extract, or burdock root",
    "passionflower":"lemon balm, valerian (if no interaction), or chamomile",
    "feverfew":    "peppermint oil (topical), butterbur (PA-free), or magnesium supplement",
    "dong quai":   "shatavari, red raspberry leaf, or vitex (chasteberry)",
    "cranberry":   "blueberry, pomegranate juice, or vitamin C supplement",
    "saw palmetto":"pumpkin seed oil, pygeum, or stinging nettle root",
    "ginkgo":      "brahmi (bacopa), rosemary, or lion's mane mushroom",
    "st. john's wort": "lemon balm, saffron, or SAMe (under medical supervision)",
    "kava":        "valerian, passionflower, or lemon balm",
}

# Lines that are allergy disclaimers — herbs mentioned here should not
# trigger a safety flag (the LLM is *warning* about them, not prescribing).
_DISCLAIMER_KW = (
    'avoid', 'allergic', 'allergy', 'allergen',
    'contraindicated', 'do not use', 'do not consume',
)


def _extract_herbs_structured(response_text: str) -> set[str]:
    """PRIMARY: parse the machine-readable herb declaration tag.

    The Proposer LLM is instructed to append:
        <!-- HERBS_USED: ginger, turmeric, honey -->
    Returns a set of canonical names, or empty set if tag is absent.
    """
    match = re.search(
        r'<!--\s*HERBS_USED:\s*(.+?)\s*-->',
        response_text,
        re.IGNORECASE,
    )
    if not match:
        return set()
    raw_herbs = [h.strip().lower() for h in match.group(1).split(',') if h.strip()]
    canonical = set()
    for h in raw_herbs:
        canonical.add(_SYNONYM_TABLE.get(h, h))
    return canonical


def _extract_herbs_regex(response_text: str) -> set[str]:
    """FALLBACK: regex scan with full synonym resolution.

    Filters out disclaimer/warning lines before scanning so herbs
    mentioned only in "avoid X due to allergy" context are not
    false-flagged.
    """
    lines = response_text.split('\n')
    filtered = '\n'.join(
        ln for ln in lines
        if not any(kw in ln.lower() for kw in _DISCLAIMER_KW)
    )
    found: set[str] = set()
    for pattern, canonical in _SCAN_PATTERNS:
        if pattern.search(filtered):
            found.add(canonical)
    return found


def _extract_herbs_from_response(response_text: str) -> list[str]:
    """Extract herbs via structured tag + regex fallback, return canonical names."""
    if not response_text:
        return []
    structured = _extract_herbs_structured(response_text)
    regex = _extract_herbs_regex(response_text)
    # Union of both — a herb caught by *either* method is validated
    return list(structured | regex)


# ═══════════════════════════════════════════════════════════════════════════
# HELPER: FORMAT SAFETY BLOCK RESPONSE
# ═══════════════════════════════════════════════════════════════════════════

def _humanize_safety_reason(herb_name: str, result) -> str:
    """Convert the raw validator reason into plain-language explanation."""
    herb = herb_name.title()
    # Pull the drug name from the result's contraindications or reason
    reason_raw = result.reason or ""

    # Extract the interacting drug from the reason string
    # Pattern: 'herb' is contraindicated with 'drug' (class: class_name)
    drug_match = re.search(
        r"contraindicated with '([^']+)'", reason_raw, re.IGNORECASE,
    )
    drug_name = drug_match.group(1).title() if drug_match else "your medication"

    # Determine the type of interaction for plain-language phrasing
    reason_lower = reason_raw.lower()
    if "allergy" in reason_lower or "allergen" in reason_lower:
        return (
            f"You have a declared allergy to {herb}. Even small amounts "
            f"could trigger an allergic reaction, so it has been replaced "
            f"with a safe alternative."
        )
    elif "platelet" in reason_lower or "bleeding" in reason_lower or "anticoagulant" in reason_lower:
        return (
            f"{herb} can thin the blood naturally. Since you are taking "
            f"{drug_name}, which also thins the blood, combining them "
            f"could increase the risk of bleeding. To keep you safe, "
            f"we have replaced it with a gentle alternative."
        )
    elif "serotonin" in reason_lower:
        return (
            f"{herb} affects serotonin levels in the brain. Since you are "
            f"taking {drug_name}, which also affects serotonin, combining "
            f"them could cause a dangerous condition called Serotonin "
            f"Syndrome (symptoms include agitation, rapid heartbeat, and "
            f"high temperature). We have replaced it with a safe alternative."
        )
    elif "liver" in reason_lower or "hepat" in reason_lower:
        return (
            f"{herb} is processed by the liver. Since you are taking "
            f"{drug_name}, which is also processed by the liver, combining "
            f"them could put extra strain on your liver. We have replaced "
            f"it with a gentler alternative."
        )
    elif "blood sugar" in reason_lower or "hypoglyc" in reason_lower or "glucose" in reason_lower:
        return (
            f"{herb} can lower blood sugar naturally. Since you are taking "
            f"{drug_name}, which also lowers blood sugar, combining them "
            f"could cause your blood sugar to drop too low. We have replaced "
            f"it with a safe alternative."
        )
    elif "blood pressure" in reason_lower:
        return (
            f"{herb} can affect blood pressure. Since you are taking "
            f"{drug_name}, combining them could cause your blood pressure "
            f"to fluctuate. We have replaced it with a safe alternative."
        )
    elif "immunosuppressant" in reason_lower or "immune" in reason_lower:
        return (
            f"{herb} stimulates the immune system. Since you are taking "
            f"{drug_name} to suppress your immune system (for example, "
            f"after a transplant or for an autoimmune condition), "
            f"{herb.lower()} could work against your medication. "
            f"We have replaced it with a safe alternative."
        )
    elif "seizure" in reason_lower:
        return (
            f"{herb} may lower the seizure threshold. Since you are taking "
            f"{drug_name} to prevent seizures, combining them could reduce "
            f"the effectiveness of your medication. We have replaced it "
            f"with a safe alternative."
        )
    elif "cyp" in reason_lower:
        # CYP enzyme interactions — explain simply
        return (
            f"{herb} can interfere with how your body processes "
            f"{drug_name}. This could cause {drug_name.lower()} to build "
            f"up to unsafe levels in your body or become less effective. "
            f"We have replaced it with a safe alternative."
        )
    else:
        # Generic fallback — still human-readable
        return (
            f"{herb} may interact with {drug_name} that you are currently "
            f"taking. To keep you safe, we have replaced it with a "
            f"gentle alternative."
        )


def _format_safety_inline_warning(flagged_herbs: list) -> str:
    """Format the Ingredient Alert summary placed after remedies.

    States which herb was substituted, why (in plain language), and
    lists alternatives.
    """
    lines = ["\n---\n", "## \u26a0\ufe0f Ingredient Alert \u2014 Safety Flag\n"]
    for herb_name, result in flagged_herbs:
        primary = _PRIMARY_SUBSTITUTE.get(herb_name.lower(), "a safe alternative")
        alternatives = _ALLERGEN_SUBSTITUTE_MAP.get(herb_name.lower(), "")
        human_reason = _humanize_safety_reason(herb_name, result)

        lines.append(
            f"\u26d4 **{primary.title()}** was substituted in place of "
            f"**{herb_name.title()}** \u2014 {human_reason}"
        )
        if result.washout_days_remaining:
            lines.append(
                f"  \u23f3 *Washout period: "
                f"{result.washout_days_remaining} days remaining*"
            )
        if alternatives:
            lines.append(
                f"  \U0001f4a1 **Other safe alternatives:** {alternatives}"
            )
        lines.append("")  # blank line between entries

    lines.append(
        "\U0001f512 *Safety check by ServVia\u2019s "
        "Neurosymbolic Pharmacovigilance Engine.*"
    )
    return "\n".join(lines) + "\n"


def _substitute_flagged_remedies(response: str, flagged_herbs: list) -> str:
    """Replace flagged herb names with safe substitutes across the entire response.

    Preserves original case of the first letter.
    """
    for herb_name, _result in flagged_herbs:
        primary = _PRIMARY_SUBSTITUTE.get(herb_name.lower())
        if not primary:
            continue

        herb_pattern = re.compile(
            r'\b' + re.escape(herb_name) + r'\b', re.IGNORECASE,
        )

        def _case_preserving_replace(match, _sub=primary):
            original = match.group(0)
            if original[0].isupper():
                return _sub[0].upper() + _sub[1:]
            return _sub.lower()

        response = herb_pattern.sub(_case_preserving_replace, response)

    return response


# ═══════════════════════════════════════════════════════════════════════════
# HELPER: INSERT BLOCK AFTER REMEDIES (before ER / "See a Doctor" section)
# ═══════════════════════════════════════════════════════════════════════════

_POST_REMEDY_HEADERS = [
    "When to Go to the Emergency Room Immediately",
    "When to Go to the Emergency Room",
    "When to See a Doctor",
]

def _insert_after_remedies(response: str, block: str) -> str:
    """Insert *block* right before the ER / 'See a Doctor' section.

    Falls back to appending at the end if no matching header is found.
    """
    for header in _POST_REMEDY_HEADERS:
        match = re.search(
            r'(?m)^#{1,3}\s*' + re.escape(header),
            response,
            re.IGNORECASE,
        )
        if match:
            pos = match.start()
            return response[:pos].rstrip() + "\n\n" + block.strip() + "\n\n" + response[pos:]
    # Fallback: append at end
    return response + "\n\n" + block


# ═══════════════════════════════════════════════════════════════════════════
# SEVERITY CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════

_MINOR_SOLO = {
    "headache", "cold", "cough", "sore throat", "runny nose",
    "sneezing", "congestion", "acidity", "bloating", "insomnia",
    "toothache", "nausea", "muscle soreness", "skin rash",
    "itching", "stress", "anxiety", "upset stomach", "fatigue",
}
_SERIOUS_MARKERS = {
    # Cardiac / respiratory
    "fever", "chest pain", "shortness of breath", "breathing",
    # Neurological
    "confusion", "vision", "seizure", "stiff neck", "one side", "slurred",
    # Bleeding / systemic
    "blood", "swelling", "rash", "yellowing",
    # Hepatobiliary — jaundice, cholestasis, hepatitis
    "dark urine", "tea-colored", "tea colored", "cola-colored", "cola colored",
    "pale stool", "clay-colored", "clay colored", "pale stool",
    "jaundice", "jaundiced", "pruritus", "bilirubin",
    "liver", "hepatitis", "cholestasis", "biliary",
    # Gastrointestinal serious
    "vomiting blood", "black stool", "tarry stool",
}


def _needs_diagnosis(query_lower: str) -> bool:
    """Determine if the query needs GPT-4.1 diagnosis (serious/multi-symptom)."""
    has_serious_marker = any(m in query_lower for m in _SERIOUS_MARKERS)
    word_count = len(query_lower.split())
    return has_serious_marker or word_count >= 12


def _is_conversational_followup(query_lower: str) -> bool:
    """Detect casual follow-ups that don't need Trust Engine or Safety validation.
    E.g., 'ok thank you', 'how long will it take', 'yes', 'can I travel'.
    These are conversational questions, not new symptom reports needing remedy verification."""
    word_count = len(query_lower.split())
    # Very short messages (1-3 words) without symptoms are almost always follow-ups
    _SHORT_AFFIRM = {
        "yes", "no", "yeah", "yep", "nah", "nope", "ya", "yea",
        "please", "yes please", "no thanks", "not really",
        "hmm", "hm", "ah", "oh",
    }
    _CASUAL_PATTERNS = [
        "thank", "thanks", "ok", "okay", "got it", "sure", "alright",
        "bye", "good", "great", "nice", "cool", "noted", "understood",
    ]
    _FOLLOWUP_PATTERNS = [
        "how long", "how much", "how often", "when should", "when will",
        "can i", "should i", "is it", "what about", "what if",
        "will it", "does it", "why", "which one", "tell me more",
    ]
    has_symptom = any(m in query_lower for m in _MINOR_SOLO | _SERIOUS_MARKERS)
    if has_symptom:
        return False
    # Short affirmatives are always follow-ups
    if query_lower.strip().rstrip("!., ") in _SHORT_AFFIRM:
        return True
    # Very short messages (1-3 words) are almost always conversational
    if word_count <= 3 and not has_symptom:
        return True
    if any(p in query_lower for p in _CASUAL_PATTERNS) and word_count <= 8:
        return True
    if any(p in query_lower for p in _FOLLOWUP_PATTERNS):
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════════
# ASYNC PIPELINE ORCHESTRATOR — Single event loop for entire request
# ═══════════════════════════════════════════════════════════════════════════

async def _run_pipeline(
    query_in_english: str,
    input_language_detected: str,
    is_english: bool,
    email_id: str,
    user_name: str,
    message_id: str,
    chat_history: list,
    user_profile_data: dict,
    bio_context_str: str,
    progress_fn=None,
) -> dict:
    """
    Single async function that runs the ENTIRE pipeline in one event loop:
      1. RAG retrieval (+ Diagnostician in parallel for serious queries)
      2. Multi-Agent verification (Proposer → Critic)
      3. Trust Engine evidence scoring
      4. Back-translation (if non-English)

    Returns dict with: response, trust_data, agent_pipeline_used, follow_up_questions
    """
    _profile = user_profile_data or {}
    query_lower = query_in_english.lower()
    needs_diag = _needs_diagnosis(query_lower)
    is_followup = _is_conversational_followup(query_lower)

    # ── Step 0: Conversation context — history + recent lab results ──────
    conversation_context = ""
    try:
        from core_temporal.conversation.manager import conversation_manager
        conv_history = conversation_manager.get_formatted_history(email_id, max_messages=8)
        if conv_history:
            conversation_context = f"RECENT CONVERSATION:\n{conv_history}\n"
    except Exception as e:
        logger.warning(f"Failed to load conversation history: {e}")

    lab_context = ""
    try:
        from lab_report.models import LabReport as LR
        recent_lab = LR.objects.filter(email_id=email_id).order_by('-created_at').first()
        if recent_lab and recent_lab.summary:
            # Only include if recent (within last 24 hours of conversation)
            from django.utils import timezone as _tz
            from datetime import timedelta as _td
            if (_tz.now() - recent_lab.created_at) < _td(hours=24):
                # Build concise lab summary for LLM context
                analysis = recent_lab.analysis or {}
                biomarkers = analysis.get("biomarkers", [])
                abnormal = [
                    f"{b.get('name', '?')}: {b.get('value', '?')} ({b.get('status', '?')})"
                    for b in biomarkers
                    if isinstance(b, dict) and b.get("status", "").lower() != "normal"
                ]
                lab_context = "RECENT LAB REPORT RESULTS:\n"
                lab_context += f"Report type: {analysis.get('report_type', 'Lab Report')}\n"
                if abnormal:
                    lab_context += "Abnormal values:\n" + "\n".join(f"  - {a}" for a in abnormal) + "\n"
                lab_context += f"Recommendation: {analysis.get('recommendation', 'N/A')}\n"
    except Exception as e:
        logger.warning(f"Failed to load lab context: {e}")

    # ── Step 1: RAG + Graph RAG in parallel ──────────────────────────────
    rag_context = ""

    async def _graph_rag() -> str:
        """Query Neo4j for outcome-ranked remedies. Returns context string."""
        if not GRAPH_RAG_AVAILABLE:
            return ""
        try:
            from legacy_healthcare.rag_service.execute_rag import ContextManager
            entities = ContextManager.extract_entities(query_in_english)
            symptoms = entities.get("conditions", [])
            if not symptoms:
                return ""

            _PHASE_MAP = {
                "early_morning": "morning",
                "morning_activation": "morning",
                "late_morning": "morning",
                "afternoon_peak": "afternoon",
                "afternoon_slump": "afternoon",
                "evening_active": "evening",
                "wind_down": "evening",
                "deep_sleep": "night",
            }
            if bio_context_str:
                raw_phase = (
                    bio_context_str.split(",")[0]
                    .replace("Circadian Phase:", "")
                    .strip()
                    .lower()
                )
                bio_phase = _PHASE_MAP.get(raw_phase, raw_phase) or "default"
            else:
                bio_phase = "default"

            graph_client = get_graph_client()
            loop = asyncio.get_event_loop()
            ranked = await loop.run_in_executor(
                None, graph_client.retrieve_ranked_remedies, symptoms, bio_phase
            )
            if ranked:
                graph_lines = [
                    f"- {r['remedy']} (score: {r['base_score']:.2f}, "
                    f"bio-enhancement: ×{r['enhancement']:.2f}, rank: {r['rank']:.2f})"
                    for r in ranked[:5]
                ]
                return "\n\n=== OUTCOME-RANKED REMEDIES (Graph RAG) ===\n" + "\n".join(graph_lines)
            return ""
        except Exception:
            return ""

    async def _rag():
        try:
            response_pair = await execute_rag_pipeline(
                query_in_english, input_language_detected, email_id,
                user_name=user_name, message_id=message_id,
                chat_history=chat_history, user_profile=user_profile_data,
            )
            if isinstance(response_pair, tuple) and len(response_pair) == 2:
                response_map, _ = response_pair
                return response_map.get("rag_context") or response_map.get("generated_final_response", "")
        except Exception as e:
            _trace(f"  [C] RAG FAILED: {e}")
        return ""

    diag_result = {"diagnosis_output": "", "primary_condition": ""}

    # Step 1a: RAG + Graph RAG in parallel (both paths need this)
    _trace(f"  [C] RAG + Graph RAG in parallel ({'SERIOUS' if needs_diag else 'MINOR'})")
    results = await asyncio.gather(_rag(), _graph_rag(), return_exceptions=True)
    rag_result_raw, graph_rag_ctx = results

    if isinstance(rag_result_raw, str):
        rag_context = rag_result_raw
    elif isinstance(rag_result_raw, Exception):
        _trace(f"  [C] RAG FAILED: {rag_result_raw}")

    if isinstance(graph_rag_ctx, str) and graph_rag_ctx:
        rag_context += graph_rag_ctx

    # Step 1b: Diagnostician (serious only, uses RAG context for accurate diagnosis)
    if needs_diag and MULTI_AGENT_AVAILABLE:
        _trace("  [C] Diagnostician (with RAG context)...")
        try:
            # Build enriched symptom context with conversation + lab history
            _symptom_ctx = query_in_english
            if conversation_context:
                _symptom_ctx = conversation_context + "\nCURRENT QUERY: " + query_in_english
            if lab_context:
                _symptom_ctx = lab_context + "\n" + _symptom_ctx

            diag_result_raw = await run_diagnostician_standalone(
                user_symptoms=_symptom_ctx,
                user_allergies=_profile.get("allergies") or [],
                user_medications=_profile.get("current_medications") or [],
                user_conditions=_profile.get("medical_conditions") or [],
                rag_context=rag_context[:2000],
            )
            if isinstance(diag_result_raw, dict):
                diag_result = diag_result_raw
        except Exception as e:
            _trace(f"  [C] Diagnostician FAILED: {e}")

    _trace(f"  [C] RAG={len(rag_context)} chars | Diag={diag_result.get('primary_condition') or 'skipped'}")

    # ── Step 1c: Pre-filter RAG context — strip allergen mentions ───────
    user_allergies_lower = [a.lower().strip() for a in (_profile.get("allergies") or []) if a]
    if user_allergies_lower and rag_context:
        for allergen in user_allergies_lower:
            # Remove lines that mention the allergen to reduce LLM exposure
            filtered_lines = []
            for line in rag_context.split("\n"):
                if allergen not in line.lower():
                    filtered_lines.append(line)
            rag_context = "\n".join(filtered_lines)
        _trace(f"  [C-1c] Pre-filtered RAG context for {len(user_allergies_lower)} allergens")

    # ── Step 2: Generate response ───────────────────────────────────────
    llm_response = ""
    agent_pipeline_used = False

    if not needs_diag:
        # ── MINOR: Single LLM call — fast path ──
        if progress_fn:
            progress_fn('generating', 'Generating personalized remedies...', 'fa-leaf')
        try:
            from agents.prompts import PROPOSER_PROMPT
            from legacy_healthcare.rag_service.openai_service import make_openai_request
            from django_core.config import Config

            allergies = _profile.get("allergies") or []
            medications = _profile.get("current_medications") or []
            conditions = _profile.get("medical_conditions") or []

            # Build enriched symptom field with conversation + lab context
            _enriched_symptoms = query_in_english
            if conversation_context or lab_context:
                _parts = []
                if lab_context:
                    _parts.append(lab_context)
                if conversation_context:
                    _parts.append(conversation_context)
                _parts.append(f"CURRENT QUERY: {query_in_english}")
                _enriched_symptoms = "\n".join(_parts)

            from api.language_support import build_language_directive
            prompt = PROPOSER_PROMPT.format(
                user_name=user_name or "",
                user_allergies=", ".join(str(a) for a in allergies) if allergies else "None declared",
                user_medications=", ".join(str(m) for m in medications) if medications else "None declared",
                user_conditions=", ".join(str(c) for c in conditions) if conditions else "None declared",
                user_symptoms=_enriched_symptoms,
                rag_context=rag_context[:2000],
                bio_context=bio_context_str,
                critic_feedback="",
                diagnosis_context="No diagnosis needed for minor ailments. Use PATH A.",
                language_directive=build_language_directive(input_language_detected),
            )

            _trace("  [C-2] MINOR — single LLM call...")
            response, exception, retries = await make_openai_request(
                prompt, model=Config.MODEL_CHAT, temperature=0.3, max_retries=2,
            )
            if response and response.choices:
                content = response.choices[0].message.content
                if content and content.strip():
                    llm_response = content.strip()
                    agent_pipeline_used = True

            if not llm_response:
                llm_response = _AGENT_FALLBACK
        except Exception as e:
            _trace(f"  [C-2] ERROR: {e}")
            logger.error(f"LLM call error: {e}", exc_info=True)
            llm_response = _AGENT_FALLBACK
    elif MULTI_AGENT_AVAILABLE:
        # ── SERIOUS: Proposer → Critic (safety-verified) ──
        if progress_fn:
            progress_fn('generating', 'AI diagnosing and verifying...', 'fa-robot')
        try:
            _trace(f"  [C-2] SERIOUS — Proposer -> Critic (diagnosis: {diag_result.get('primary_condition') or 'none'})...")
            # Build enriched symptom field for serious path too
            _enriched_serious = query_in_english
            if conversation_context or lab_context:
                _parts = []
                if lab_context:
                    _parts.append(lab_context)
                if conversation_context:
                    _parts.append(conversation_context)
                _parts.append(f"CURRENT QUERY: {query_in_english}")
                _enriched_serious = "\n".join(_parts)

            verified_response = await run_verification_pipeline(
                user_symptoms=_enriched_serious,
                rag_context=rag_context,
                bio_context=bio_context_str,
                user_name=user_name or "",
                user_allergies=_profile.get("allergies") or [],
                user_medications=_profile.get("current_medications") or [],
                user_conditions=_profile.get("medical_conditions") or [],
                diagnosis_output=diag_result.get("diagnosis_output", ""),
                primary_condition=diag_result.get("primary_condition", ""),
                target_language=input_language_detected,
            )
            if verified_response and verified_response != _AGENT_FALLBACK:
                llm_response = verified_response
                agent_pipeline_used = True
            else:
                llm_response = _AGENT_FALLBACK
        except Exception as e:
            _trace(f"  [C-2] ERROR: {e}")
            logger.error(f"Multi-Agent pipeline error: {e}", exc_info=True)
            llm_response = _AGENT_FALLBACK
    else:
        llm_response = _AGENT_FALLBACK

    # ── Step 3: Trust Engine (skip for conversational follow-ups) ────────
    trust_data = None

    if is_followup:
        _trace("  [D-1] Trust Engine SKIPPED (conversational follow-up)")
    elif TRUST_ENGINE_AVAILABLE and llm_response and llm_response != _AGENT_FALLBACK:
        if progress_fn:
            progress_fn('trust', 'Verifying evidence base...', 'fa-check-double')
        _trace("  [D-1] Trust Engine verification...")
        try:
            trust_engine = get_trust_engine()
            user_conditions = _profile.get("medical_conditions", []) or []
            user_medications = _profile.get("current_medications", []) or []
            user_allergies = _profile.get("allergies", []) or []

            trust_result = await trust_engine.verify_response(
                llm_response=llm_response,
                query=query_in_english,
                user_id=email_id,
                user_conditions=user_conditions,
                user_medications=user_medications,
                user_allergies=user_allergies,
            )

            if trust_result.formatted_output:
                llm_response = _insert_after_remedies(
                    llm_response, trust_result.formatted_output
                )

            trust_data = {
                "verified_herbs": trust_result.verified_herbs,
                "unverified_herbs": trust_result.unverified_herbs,
                "verified_count": len(trust_result.verified_herbs),
                "unverified_count": len(trust_result.unverified_herbs),
                "warnings": trust_result.warnings,
                "interaction_warnings": trust_result.interaction_warnings,
                "is_safe": trust_result.is_safe,
            }
            _trace(
                f"  [D-1] Trust: {len(trust_result.verified_herbs)} verified, "
                f"{len(trust_result.unverified_herbs)} unverified"
            )
        except Exception as e:
            logger.error(f"Trust Engine error: {e}", exc_info=True)
            _trace(f"  [D-1] Trust Engine error: {e}")

    # ── Step 4: Language handling ────────────────────────────────────────
    # The reply is GENERATED directly in the user's language by the Proposer
    # (see build_language_directive), so we do NOT Google-translate it here.
    # This is what preserves the word-by-word SSE streaming for non-English
    # replies — there is no full-text translation barrier. Indian-language
    # scripts are space-delimited, so the typing animation works unchanged.
    follow_up_questions = []
    if is_english:
        _trace("  [E] English — no language post-processing")
    else:
        _trace(f"  [E] Reply generated in-language ({input_language_detected}) — skipping back-translation")
    translated_response = llm_response

    return {
        "response": translated_response,
        "trust_data": trust_data,
        "agent_pipeline_used": agent_pipeline_used,
        "follow_up_questions": follow_up_questions,
        "rag_source": None,  # Could add source tracking later
    }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE VIEW
# ═══════════════════════════════════════════════════════════════════════════

class ServViaChatViewSet(GenericViewSet):
    """
    ServVia 4.0 Chat Pipeline.

    Replaces the legacy ChatAPIViewSet with the strict neurosymbolic
    pipeline: Emergency → Chronobiology → RAG + Multi-Agent → Safety → Response.

    All endpoints are unauthenticated (matching legacy behavior) with
    email-based identification.
    """

    authentication_classes = []
    permission_classes = []

    @action(detail=False, methods=["post"])
    def get_answer_for_text_query(self, request):
        """
        Primary chat endpoint.

        POST /api/chat/get_answer_for_text_query/
        Body: { "email_id": "...", "query": "..." }
        """
        email_id = request.data.get("email_id")
        original_query = request.data.get("query")

        _trace(f">>> REQUEST | {original_query}")

        response_data = Response(
            {"message": None, "query": original_query, "error": False}
        )

        try:
            # ─── AUTH ────────────────────────────────────────────────
            authenticated_user = authenticate_user_based_on_email(email_id)
            if not authenticated_user:
                response_data.data["message"] = "Invalid Email ID"
                response_data.status_code = status.HTTP_401_UNAUTHORIZED
                return response_data

            if not original_query:
                response_data.data["message"] = "Please submit a query."
                response_data.status_code = status.HTTP_400_BAD_REQUEST
                return response_data

            _trace(f"  User: {mask_email(email_id)} | Query: {original_query[:80]}")

            # ═══════════════════════════════════════════════════════
            # STEP A: EMERGENCY DETECTION (hardcoded, no LLM)
            # ═══════════════════════════════════════════════════════
            _trace("  [A] Emergency Detection...")
            emergency_type = EmergencySystem.detect_intent(original_query)
            if emergency_type:
                _trace(f"  [A] EMERGENCY DETECTED: {emergency_type}")
                emergency_response = EmergencySystem.get_response(emergency_type)
                response_data.data["message"] = "Emergency response"
                response_data.data["response"] = emergency_response
                response_data.data["pipeline"] = "emergency_intercept"
                response_data.data["emergency_type"] = emergency_type
                return response_data

            # ═══════════════════════════════════════════════════════
            # STEP B: CHRONOBIOLOGY CONTEXT (passive, no LLM)
            # ═══════════════════════════════════════════════════════
            _trace("  [B] Chronobiology inference...")
            bio_state = _chrono_engine.infer_state(
                local_time=datetime.now(timezone(timedelta(hours=5, minutes=30))),
            )

            # ═══════════════════════════════════════════════════════
            # PRE-PIPELINE: User data + Language detection
            # ═══════════════════════════════════════════════════════
            user_data, message_obj = preprocess_user_data(
                original_query, email_id, authenticated_user
            )
            user_id = user_data.get("user_id")
            user_name = user_data.get("user_name")
            message_id = user_data.get("message_id")
            chat_history = get_user_chat_history(user_id) if user_id else None

            # Fast English detection heuristic (avoids API call for obvious English)
            _ascii_ratio = sum(1 for c in original_query if ord(c) < 128) / max(len(original_query), 1)
            if _ascii_ratio > 0.95:
                # Very likely English — skip Google Translate API call entirely
                query_in_english = original_query
                input_language_detected = "en"
                _is_english = True
                _trace("  [T] Fast English detect (ASCII > 95%) — skipping API")
            else:
                # Non-ASCII content — use Google Translate for detection + translation
                _trace("  [T] Non-ASCII — calling language detection API...")
                query_in_english, input_language_detected = asyncio.run(
                    detect_language_and_translate_to_english(original_query)
                )
                _is_english = input_language_detected in ("en", "en-US", "en-GB", "english")
                _trace(f"  [T] Language: {input_language_detected}")

            # Load user profile
            user_profile_data = None
            try:
                from user_profile.models import UserProfile
                profile = UserProfile.objects.get(email=email_id)
                user_profile_data = {
                    "allergies": profile.get_allergies_list(),
                    "medical_conditions": profile.get_conditions_list(),
                    "current_medications": profile.get_medications_list(),
                    "first_name": profile.first_name,
                }
                if profile.first_name:
                    user_name = profile.first_name
            except Exception:
                pass

            bio_context_str = ""
            if bio_state.advisory:
                bio_context_str = (
                    f"Circadian Phase: {bio_state.circadian_phase.value}, "
                    f"Season: {bio_state.seasonal_influence.value}, "
                    f"Sleep Pressure: {bio_state.sleep_pressure_estimate.value}"
                )

            # ═══════════════════════════════════════════════════════
            # STEP C: SINGLE ASYNC PIPELINE (one event loop)
            # ═══════════════════════════════════════════════════════
            _trace("  [C] Starting async pipeline...")
            pipeline_result = asyncio.run(
                _run_pipeline(
                    query_in_english=query_in_english,
                    input_language_detected=input_language_detected,
                    is_english=_is_english,
                    email_id=email_id,
                    user_name=user_name or "",
                    message_id=message_id,
                    chat_history=chat_history,
                    user_profile_data=user_profile_data,
                    bio_context_str=bio_context_str,
                )
            )

            llm_response = pipeline_result["response"]
            trust_data = pipeline_result["trust_data"]
            agent_pipeline_used = pipeline_result["agent_pipeline_used"]
            follow_up_questions = pipeline_result["follow_up_questions"]

            # ═══════════════════════════════════════════════════════
            # STEP D-2: SAFETY VALIDATION (deterministic, no LLM)
            # ═══════════════════════════════════════════════════════
            _trace("  [D-2] Safety validation (herb-drug interactions)...")
            flagged_herbs = []
            medical_profile = _build_medical_profile(email_id, user_profile_data)
            proposed_herbs = _extract_herbs_from_response(llm_response)

            for herb_name in proposed_herbs:
                proposal = RemedyProposal(
                    herb_or_remedy_name=herb_name,
                    intended_effect="LLM-recommended remedy",
                )
                result = _safety_validator.validate_remedy(medical_profile, proposal)
                if not result.is_safe:
                    flagged_herbs.append((herb_name, result))
                    _trace(f"  [D-2] FLAGGED: {herb_name} — {result.reason[:60]}")

            # ═══════════════════════════════════════════════════════
            # STEP E: FINAL OUTPUT
            # ═══════════════════════════════════════════════════════
            if flagged_herbs:
                # 1. Replace flagged herbs with safe substitutes in remedy text
                final_response = _substitute_flagged_remedies(llm_response, flagged_herbs)
                # 2. Insert summary alert block after all remedies
                warning_block = _format_safety_inline_warning(flagged_herbs)
                final_response = _insert_after_remedies(final_response, warning_block)
                pipeline_status = "safety_flagged"
            else:
                final_response = llm_response
                pipeline_status = "safe_response"

            # Strip the machine-readable herb declaration before sending to UI
            final_response = re.sub(
                r'\s*<!--\s*HERBS_USED:.*?-->', '', final_response
            ).rstrip()

            # ─── Build response ──────────────────────────────────
            response_data.data["message"] = "Successful retrieval of response"
            response_data.data["message_id"] = message_id
            response_data.data["response"] = final_response
            response_data.data["follow_up_questions"] = follow_up_questions
            response_data.data["pipeline"] = pipeline_status
            response_data.data["bio_state"] = {
                "circadian_phase": bio_state.circadian_phase.value,
                "seasonal_influence": bio_state.seasonal_influence.value,
                "sleep_pressure": bio_state.sleep_pressure_estimate.value,
                "is_misaligned": bio_state.is_misaligned,
            }

            if flagged_herbs:
                response_data.data["safety"] = {
                    "is_safe": False,
                    "flagged_herbs": [h for h, _ in flagged_herbs],
                    "warnings": [
                        {
                            "herb": h,
                            "reason": r.reason,
                            "contraindications": r.contraindications,
                            "washout_days_remaining": r.washout_days_remaining,
                            "substitute": _ALLERGEN_SUBSTITUTE_MAP.get(h.lower()),
                        }
                        for h, r in flagged_herbs
                    ],
                }

            if trust_data:
                response_data.data["trust_verification"] = trust_data

            if agent_pipeline_used:
                response_data.data["agent_verified"] = True

            _trace(f"  [E] DONE | {pipeline_status} | {len(final_response)} chars")

        except Exception as error:
            logger.error(error, exc_info=True)
            _trace(f"  [!] PIPELINE ERROR: {error}")
            response_data.data.update(
                {"message": "Something went wrong", "error": True}
            )
            response_data.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        return response_data

    @action(detail=False, methods=["post"])
    def feedback(self, request):
        """
        Closed-loop feedback endpoint — updates Neo4j Graph RAG edge weights.

        POST /api/chat/feedback/
        Body: {"remedy": str, "bio_state": str, "outcome_score": int}
        """
        remedy = request.data.get("remedy")
        bio_state = request.data.get("bio_state")
        outcome_score = request.data.get("outcome_score")

        if not remedy or not bio_state or outcome_score is None:
            return Response(
                {"error": "Missing required fields: remedy, bio_state, outcome_score"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if outcome_score not in (1, -1):
            return Response(
                {"error": "outcome_score must be +1 or -1"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from graph_rag.updater import AdaptiveFeedbackEngine
            engine = AdaptiveFeedbackEngine()
            new_weight = engine.update_edge_weight(remedy, bio_state, outcome_score)
            engine.close()

            return Response(
                {
                    "status": "success",
                    "remedy": remedy,
                    "bio_state": bio_state,
                    "outcome_score": outcome_score,
                    "new_weight": new_weight,
                },
                status=status.HTTP_200_OK,
            )
        except KeyError:
            return Response(
                {
                    "error": "Neo4j credentials not configured. "
                    "Set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in environment."
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.error(f"Feedback endpoint error: {e}", exc_info=True)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"])
    def synthesise_audio(self, request):
        """Proxy to legacy TTS endpoint."""
        from legacy_healthcare.api.views import ChatAPIViewSet
        legacy = ChatAPIViewSet()
        return legacy.synthesise_audio(request)

    @action(detail=False, methods=["post"])
    def transcribe(self, request):
        """
        Voice → text with automatic language detection (Whisper).

        POST /api/chat/transcribe/   (multipart/form-data)
        Form: { "audio": <file>, "email_id": "..." (optional) }

        Returns: { "transcript": str, "language": iso_code, "engine": str }

        The transcript comes back in the language's native script, so sending it
        straight to the chat endpoint lets the pipeline auto-detect the language
        and reply in the same language — no language selector needed.
        """
        from api.voice_asr import transcribe_audio_clip

        audio_file = request.FILES.get("audio")
        if not audio_file:
            return Response(
                {"error": "No audio file provided (field 'audio')."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            content = audio_file.read()
            filename = getattr(audio_file, "name", "") or "audio.webm"
            result = transcribe_audio_clip(content, filename=filename)
            if not result.get("transcript"):
                return Response(
                    {
                        "transcript": "",
                        "language": "",
                        "engine": result.get("engine", "none"),
                        "message": "Could not transcribe audio.",
                    },
                    status=status.HTTP_200_OK,
                )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Transcribe endpoint error: {e}", exc_info=True)
            return Response(
                {"error": "Transcription failed.", "transcript": "", "language": ""},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"])
    def transcribe_audio(self, request):
        """Proxy to legacy ASR endpoint."""
        from legacy_healthcare.api.views import ChatAPIViewSet
        legacy = ChatAPIViewSet()
        return legacy.transcribe_audio(request)

    @action(detail=False, methods=["post"])
    def get_answer_by_voice_query(self, request):
        """Proxy to legacy voice endpoint."""
        from legacy_healthcare.api.views import ChatAPIViewSet
        legacy = ChatAPIViewSet()
        return legacy.get_answer_by_voice_query(request)


# ═══════════════════════════════════════════════════════════════════════════
# SSE STREAMING ENDPOINT — ChatGPT-style real-time response
# ═══════════════════════════════════════════════════════════════════════════

@csrf_exempt
def stream_chat_view(request):
    """
    Server-Sent Events streaming endpoint.

    POST /api/chat/stream/
    Body: { "email_id": "...", "query": "..." }

    Sends real-time stage updates as the pipeline progresses, then streams
    the final response word-by-word for a ChatGPT-style typing effect.

    Events:
        stage  — Pipeline progress: {"id": str, "label": str, "icon": str}
        token  — Response word:     {"text": str}
        done   — Final metadata:    {pipeline, bio_state, safety, ...}
        error  — Error:             {"message": str}
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    email_id = (body.get("email_id") or "").strip()
    original_query = (body.get("query") or "").strip()
    session_id = (body.get("session_id") or "").strip()

    if not email_id or not original_query:
        return JsonResponse({"error": "Missing email_id or query"}, status=400)

    # Set session scope for conversation (new page load = new session = fresh context)
    if session_id:
        try:
            from core_temporal.conversation.manager import conversation_manager
            conversation_manager.set_session(email_id, session_id)
        except Exception:
            pass

    event_q = queue.Queue()

    def _sse(event, data):
        """Format a single SSE event."""
        payload = json.dumps(data, ensure_ascii=False)
        return f"event: {event}\ndata: {payload}\n\n"

    def _pipeline_worker():
        """Run the full pipeline in a background thread, posting events to queue."""
        _stream_start = _time.time()
        try:
            _trace(f">>> STREAM | {original_query}")

            # ─── AUTH ─────────────────────────────────────────
            authenticated_user = authenticate_user_based_on_email(email_id)
            if not authenticated_user:
                event_q.put(("error", {"message": "Invalid Email ID"}))
                return

            # ─── EMERGENCY ────────────────────────────────────
            event_q.put(("stage", {"id": "emergency", "label": "Checking for emergencies...", "icon": "fa-shield-alt"}))
            emergency_type = EmergencySystem.detect_intent(original_query)
            if emergency_type:
                _trace(f"  [A] EMERGENCY: {emergency_type}")
                response_text = EmergencySystem.get_response(emergency_type)
                # Emergencies bypass word-by-word streaming — dump full response instantly
                event_q.put(("emergency_instant", {
                    "response": response_text,
                    "pipeline": "emergency_intercept",
                    "emergency_type": emergency_type,
                }))
                return

            # ─── CHRONOBIOLOGY ────────────────────────────────
            event_q.put(("stage", {"id": "bio", "label": "Analyzing biological context...", "icon": "fa-clock"}))
            bio_state = _chrono_engine.infer_state(
                local_time=datetime.now(timezone(timedelta(hours=5, minutes=30))),
            )

            # ─── LANGUAGE + PREP ──────────────────────────────
            event_q.put(("stage", {"id": "prep", "label": "Processing your query...", "icon": "fa-language"}))

            user_data, message_obj = preprocess_user_data(original_query, email_id, authenticated_user)
            user_id = user_data.get("user_id")
            user_name = user_data.get("user_name")
            message_id = user_data.get("message_id")
            chat_history = get_user_chat_history(user_id) if user_id else None

            _ascii_ratio = sum(1 for c in original_query if ord(c) < 128) / max(len(original_query), 1)
            if _ascii_ratio > 0.95:
                query_in_english = original_query
                input_language_detected = "en"
                _is_english = True
            else:
                query_in_english, input_language_detected = asyncio.run(
                    detect_language_and_translate_to_english(original_query)
                )
                _is_english = input_language_detected in ("en", "en-US", "en-GB", "english")

            # Load user profile
            user_profile_data = None
            try:
                from user_profile.models import UserProfile
                profile = UserProfile.objects.get(email=email_id)
                user_profile_data = {
                    "allergies": profile.get_allergies_list(),
                    "medical_conditions": profile.get_conditions_list(),
                    "current_medications": profile.get_medications_list(),
                    "first_name": profile.first_name,
                }
                if profile.first_name:
                    user_name = profile.first_name
            except Exception:
                pass

            bio_context_str = ""
            if bio_state.advisory:
                bio_context_str = (
                    f"Circadian Phase: {bio_state.circadian_phase.value}, "
                    f"Season: {bio_state.seasonal_influence.value}, "
                    f"Sleep Pressure: {bio_state.sleep_pressure_estimate.value}"
                )

            # ─── PIPELINE ────────────────────────────────────
            needs_diag = _needs_diagnosis(query_in_english.lower())
            if needs_diag:
                event_q.put(("stage", {"id": "knowledge", "label": "Searching medical knowledge base...", "icon": "fa-search"}))
            else:
                event_q.put(("stage", {"id": "knowledge", "label": "Finding the best remedies...", "icon": "fa-leaf"}))

            def _progress(stage_id, label, icon="fa-cog"):
                event_q.put(("stage", {"id": stage_id, "label": label, "icon": icon}))

            pipeline_result = asyncio.run(
                _run_pipeline(
                    query_in_english=query_in_english,
                    input_language_detected=input_language_detected,
                    is_english=_is_english,
                    email_id=email_id,
                    user_name=user_name or "",
                    message_id=message_id,
                    chat_history=chat_history,
                    user_profile_data=user_profile_data,
                    bio_context_str=bio_context_str,
                    progress_fn=_progress,
                )
            )

            llm_response = pipeline_result["response"]
            trust_data = pipeline_result["trust_data"]
            agent_pipeline_used = pipeline_result["agent_pipeline_used"]
            follow_up_questions = pipeline_result["follow_up_questions"]

            # ─── SAFETY VALIDATION (skip for conversational follow-ups) ─────
            _is_followup = _is_conversational_followup(query_in_english.lower())
            flagged_herbs = []

            if _is_followup:
                final_response = llm_response
                pipeline_status = "safe_response"
            else:
                event_q.put(("stage", {"id": "safety", "label": "Running pharmacovigilance check...", "icon": "fa-shield-alt"}))
                medical_profile = _build_medical_profile(email_id, user_profile_data)
                proposed_herbs = _extract_herbs_from_response(llm_response)

                for herb_name in proposed_herbs:
                    proposal = RemedyProposal(
                        herb_or_remedy_name=herb_name,
                        intended_effect="LLM-recommended remedy",
                    )
                    result = _safety_validator.validate_remedy(medical_profile, proposal)
                    if not result.is_safe:
                        flagged_herbs.append((herb_name, result))

                # ─── BUILD RESULT ─────────────────────────────────
                if flagged_herbs:
                    final_response = _substitute_flagged_remedies(llm_response, flagged_herbs)
                    warning_block = _format_safety_inline_warning(flagged_herbs)
                    final_response = _insert_after_remedies(final_response, warning_block)
                    pipeline_status = "safety_flagged"
                else:
                    final_response = llm_response
                    pipeline_status = "safe_response"

            # Strip the machine-readable herb declaration before sending to UI
            final_response = re.sub(
                r'\s*<!--\s*HERBS_USED:.*?-->', '', final_response
            ).rstrip()

            metadata = {
                "pipeline": pipeline_status,
                "bio_state": {
                    "circadian_phase": bio_state.circadian_phase.value,
                    "seasonal_influence": bio_state.seasonal_influence.value,
                    "sleep_pressure": bio_state.sleep_pressure_estimate.value,
                    "is_misaligned": bio_state.is_misaligned,
                },
                "follow_up_questions": follow_up_questions,
            }

            if flagged_herbs:
                metadata["safety"] = {
                    "is_safe": False,
                    "flagged_herbs": [h for h, _ in flagged_herbs],
                    "warnings": [
                        {
                            "herb": h,
                            "reason": r.reason,
                            "contraindications": r.contraindications,
                            "washout_days_remaining": r.washout_days_remaining,
                            "substitute": _ALLERGEN_SUBSTITUTE_MAP.get(h.lower()),
                        }
                        for h, r in flagged_herbs
                    ],
                }

            if trust_data:
                metadata["trust_verification"] = trust_data

            if agent_pipeline_used:
                metadata["agent_verified"] = True

            # ─── SAVE TO CONVERSATION MEMORY ─────────────────
            try:
                from core_temporal.conversation.manager import conversation_manager
                conversation_manager.add_message(
                    email_id, 'assistant', final_response,
                    metadata={"pipeline": pipeline_status}
                )
            except Exception as conv_e:
                logger.warning(f"Failed to save assistant response to conversation: {conv_e}")

            _elapsed = _time.time() - _stream_start
            _trace(f"  ServVia responded in {_elapsed:.2f}s")
            event_q.put(("result", {"response": final_response, **metadata}))

        except Exception as e:
            logger.error(f"Streaming pipeline error: {e}", exc_info=True)
            _trace(f"  [!] STREAM ERROR: {e}")
            event_q.put(("error", {"message": f"Pipeline error: {type(e).__name__}"}))
        finally:
            event_q.put(("end", None))

    def _event_generator():
        """SSE generator — reads from queue, yields events to client."""
        thread = threading.Thread(target=_pipeline_worker, daemon=True)
        thread.start()

        while True:
            try:
                event_type, data = event_q.get(timeout=180)
            except queue.Empty:
                yield _sse("error", {"message": "Request timeout"})
                break

            if event_type == "end":
                break
            elif event_type == "stage":
                yield _sse("stage", data)
            elif event_type == "error":
                yield _sse("error", data)
                break
            elif event_type == "emergency_instant":
                # Emergencies: send full response at once, no typing animation
                yield _sse("emergency", data)
                break
            elif event_type == "result":
                # Stream the response word-by-word
                response_text = data.pop("response", "")
                yield _sse("stage", {"id": "streaming", "label": "", "icon": "fa-pen"})

                words = response_text.split(" ")
                word_count = len(words)
                # Adaptive speed: longer responses type faster
                base_delay = 0.015 if word_count < 300 else (0.008 if word_count < 700 else 0.004)

                for i, word in enumerate(words):
                    yield _sse("token", {"text": word + (" " if i < word_count - 1 else "")})
                    # Variable delay for natural feel
                    if word.endswith((".", "!", "?", ":")):
                        _time.sleep(base_delay * 2.5)
                    elif word.endswith((",", ";", "—")):
                        _time.sleep(base_delay * 1.5)
                    else:
                        _time.sleep(base_delay)

                yield _sse("done", data)

        thread.join(timeout=5)

    resp = StreamingHttpResponse(_event_generator(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp
