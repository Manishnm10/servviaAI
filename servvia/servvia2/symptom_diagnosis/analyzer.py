"""
ServVia 2.0 - Intelligent Symptom Diagnosis Engine
====================================================
LLM-powered multi-symptom analysis that uses the medical textbook
on Farmstack VectorDB instead of hardcoded disease patterns.

Architecture:
    User Query 
        → Stage 1: Symptom Extraction (LLM) 
        → Stage 2: Farmstack VectorDB Retrieval (medical textbook)
        → Stage 3: Disease Reasoning (LLM over textbook context)
        → Triage Decision 
        → Response

No hardcoded diseases. The textbook IS the knowledge base.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SymptomProfile:
    """Structured representation of extracted symptoms"""
    symptoms: List[str] = field(default_factory=list)
    severity: str = "mild"
    duration: str = "unknown"
    onset: str = "unknown"
    symptom_count: int = 0
    has_fever: bool = False
    fever_grade: str = "unknown"
    has_pain: bool = False
    pain_locations: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)
    raw_query: str = ""
    # Populated by Stage 1 — the LLM generates a search query
    # optimized for finding matching diseases in the textbook
    search_query: str = ""


@dataclass
class DiagnosisResult:
    """Result of the diagnosis pipeline"""
    needs_medical_attention: bool = False
    is_emergency: bool = False
    possible_conditions: List[Dict] = field(default_factory=list)
    primary_condition: str = ""
    confidence: float = 0.0
    severity: str = "mild"
    reasoning: str = ""
    recommendation: str = ""
    home_remedy_appropriate: bool = True
    symptom_profile: Optional[SymptomProfile] = None
    vectordb_context: str = ""
    triage_level: str = "self-care"


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYMPTOM_EXTRACTION_PROMPT = """You are a medical symptom analyzer. Extract structured information from the user's health complaint.

USER MESSAGE: "{query}"

Analyze carefully and respond in EXACT JSON format (no markdown, no extra text, just the JSON object):
{{
    "symptoms": ["list", "every", "distinct", "symptom", "mentioned"],
    "severity": "mild|moderate|severe|critical",
    "onset": "sudden|gradual|unknown",
    "duration": "how long they have had symptoms, or unknown",
    "has_fever": true or false,
    "fever_grade": "none|low-grade|moderate|high-grade|unknown",
    "has_pain": true or false,
    "pain_locations": ["head", "joints", "muscles", "chest", "abdomen", "etc"],
    "red_flags": ["list any dangerous symptoms: breathing difficulty, chest pain, confusion, severe bleeding, seizures, inability to keep fluids down, loss of consciousness, very high fever above 104F, etc."],
    "symptom_count": number_of_distinct_symptoms_as_integer,
    "search_query": "Write a medical search query that describes this COMBINATION of symptoms to find matching diseases in a medical textbook. Be specific. Example: 'sudden onset high fever with severe joint pain, muscle pain, skin rash, nausea and vomiting - differential diagnosis of viral hemorrhagic fever vs dengue vs chikungunya'"
}}

RULES:
- Extract EVERY symptom, even if implied (e.g., "body is aching" = muscle pain, body ache)
- "high-grade fever" or "104F" = fever_grade: "high-grade"
- "intense", "severe", "worst" = increase severity  
- "sudden", "acute", "abrupt" = onset: "sudden"
- "since 3 days" = duration: "3 days"
- The search_query MUST describe the symptom COMBINATION, not individual symptoms
- Red flags: breathing difficulty, chest pain, confusion, loss of consciousness, severe bleeding, seizures, persistent vomiting, high fever (>104F/40C), neck stiffness, worst headache of life
"""


DIAGNOSIS_REASONING_PROMPT = """You are an expert medical diagnostic AI. Based on the patient's symptoms and the medical reference information retrieved from our textbook database, provide a differential diagnosis.

PATIENT SYMPTOMS: {symptoms_summary}
SEVERITY: {severity}
ONSET: {onset}
DURATION: {duration}
FEVER: {fever_info}
RED FLAGS: {red_flags}
{user_context}

MEDICAL REFERENCE INFORMATION (from our textbook database):
---
{vectordb_context}
---

Based on ALL of the above, respond in EXACT JSON format (no markdown, no extra text):
{{
    "possible_conditions": [
        {{
            "condition": "Disease Name",
            "confidence": 0.85,
            "matching_symptoms": ["symptom1", "symptom2"],
            "key_differentiators": "what specifically makes this diagnosis likely given the symptom combination"
        }}
    ],
    "primary_condition": "Most Likely Disease Name",
    "overall_confidence": 0.85,
    "needs_medical_attention": true,
    "is_emergency": false,
    "home_remedy_appropriate": false,
    "reasoning": "The combination of X + Y + Z symptoms suggests a systemic infectious disease like [Disease Name].",
    "recommendation": "Specific actionable advice for the patient",
    "triage_level": "self-care|monitor|see-doctor|urgent-care|emergency"
}}

CRITICAL DIAGNOSTIC RULES:
1. NEVER reduce a multi-symptom presentation to a single minor condition. "Headache + high fever + joint pain + rash + vomiting" is NOT "just a headache."
2. Consider the COMBINATION — multiple systemic symptoms with sudden onset + high fever almost always indicate an infectious disease (dengue, malaria, typhoid, chikungunya, meningitis, etc.)
3. Use the medical reference text to ground your diagnosis. If the textbook describes a disease matching these symptoms, reference it.
4. If the textbook doesn't cover it, use your general medical knowledge, but state lower confidence.
5. If >=3 symptoms AND fever is high-grade AND onset is sudden → needs_medical_attention should almost always be true.
6. home_remedy_appropriate = false for any serious infectious disease, emergency, or condition requiring lab diagnosis.
7. Be honest about confidence. If symptoms are ambiguous, list multiple differentials.
8. triage_level guide:
   - "self-care": single mild symptom, no red flags (e.g., mild headache)
   - "monitor": mild condition but watch for worsening (e.g., low fever + cough)
   - "see-doctor": needs professional evaluation within 24-48h
   - "urgent-care": needs medical attention same day
   - "emergency": go to ER immediately (red flags, life-threatening)
"""


# ---------------------------------------------------------------------------
# Core Engine
# ---------------------------------------------------------------------------

class SymptomDiagnosisEngine:
    """
    LLM + VectorDB powered symptom diagnosis.
    
    No hardcoded disease patterns. Uses:
    - LLM (Stage 1) to understand and extract symptoms
    - Farmstack VectorDB (Stage 2) to retrieve textbook context
    - LLM (Stage 3) to reason over symptoms + textbook → diagnosis
    """

    def __init__(self, vectordb_retriever: Callable = None):
        """
        Args:
            vectordb_retriever: Async function to retrieve from Farmstack.
                Signature: async (query: str, top_k: int) -> List[str]
                
                Use retrieve_from_farmstack from vectordb_adapter.py,
                or retrieve_from_farmstack_with_email if you have the email.
        """
        self.vectordb_retriever = vectordb_retriever
        logger.info("SymptomDiagnosisEngine initialized")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def diagnose(
        self,
        query: str,
        user_profile: Dict = None,
        chat_history: List = None,
    ) -> DiagnosisResult:
        """
        Full diagnosis pipeline.
        
        Returns DiagnosisResult — check .home_remedy_appropriate to decide
        whether to proceed with normal remedy generation or show a medical alert.
        """
        logger.info(f"🩺 Starting diagnosis for: {query[:100]}...")

        # Stage 1: Extract structured symptoms via LLM
        symptom_profile = await self._extract_symptoms(query)
        logger.info(
            f"   Extracted {symptom_profile.symptom_count} symptoms, "
            f"severity={symptom_profile.severity}, "
            f"fever={symptom_profile.fever_grade}"
        )

        # Quick path: single mild symptom → skip expensive diagnosis
        if self._is_simple_query(symptom_profile):
            logger.info("   Simple query → skipping full diagnosis pipeline")
            return DiagnosisResult(
                home_remedy_appropriate=True,
                primary_condition=(
                    symptom_profile.symptoms[0] 
                    if symptom_profile.symptoms 
                    else "general health"
                ),
                severity="mild",
                confidence=0.5,
                reasoning="Single mild symptom detected. Home remedies appropriate.",
                symptom_profile=symptom_profile,
                triage_level="self-care",
            )

        # Stage 2: Query Farmstack VectorDB for textbook content
        vectordb_context = await self._retrieve_medical_context(symptom_profile)
        logger.info(f"   Retrieved {len(vectordb_context)} chars from Farmstack textbook")

        # Stage 3: LLM differential diagnosis over symptoms + textbook
        diagnosis = await self._reason_diagnosis(
            symptom_profile, vectordb_context, user_profile
        )
        diagnosis.symptom_profile = symptom_profile
        diagnosis.vectordb_context = vectordb_context

        logger.info(
            f"   ✅ Diagnosis: {diagnosis.primary_condition} "
            f"(confidence={diagnosis.confidence:.0%}, "
            f"emergency={diagnosis.is_emergency}, "
            f"home_remedy_ok={diagnosis.home_remedy_appropriate})"
        )

        return diagnosis

    # ------------------------------------------------------------------
    # Stage 1: Symptom Extraction (LLM)
    # ------------------------------------------------------------------

    async def _extract_symptoms(self, query: str) -> SymptomProfile:
        """Use LLM to extract structured symptoms from free-text."""
        prompt = SYMPTOM_EXTRACTION_PROMPT.format(query=query)

        try:
            raw = await self._call_llm(prompt, max_tokens=500, temperature=0.1)
            parsed = self._parse_json(raw)

            profile = SymptomProfile(
                symptoms=parsed.get("symptoms", []),
                severity=parsed.get("severity", "mild"),
                onset=parsed.get("onset", "unknown"),
                duration=parsed.get("duration", "unknown"),
                has_fever=parsed.get("has_fever", False),
                fever_grade=parsed.get("fever_grade", "unknown"),
                has_pain=parsed.get("has_pain", False),
                pain_locations=parsed.get("pain_locations", []),
                red_flags=parsed.get("red_flags", []),
                symptom_count=parsed.get("symptom_count", len(parsed.get("symptoms", []))),
                raw_query=query,
                search_query=parsed.get("search_query", " ".join(parsed.get("symptoms", []))),
            )
            return profile

        except Exception as e:
            logger.error(f"Symptom extraction failed: {e}")
            return SymptomProfile(
                symptoms=[query], symptom_count=1,
                severity="unknown", raw_query=query,
                search_query=query,
            )

    # ------------------------------------------------------------------
    # Stage 2: Farmstack VectorDB Retrieval
    # ------------------------------------------------------------------

    async def _retrieve_medical_context(self, profile: SymptomProfile) -> str:
        """
        Query the Farmstack VectorDB to get medical textbook content
        relevant to the user's symptom combination.
        
        Sends multiple targeted queries to maximize relevant retrieval.
        """
        if not self.vectordb_retriever:
            logger.warning("No VectorDB retriever configured — diagnosis "
                           "will rely on LLM knowledge only")
            return ""

        all_chunks: List[str] = []

        try:
            # Query 1: Use the LLM-generated search query
            # This is the most important query — it captures the full
            # symptom combination as a medical search
            primary_chunks = await self.vectordb_retriever(
                profile.search_query, top_k=5
            )
            all_chunks.extend(primary_chunks)

            # Query 2: If high fever is present, specifically search
            # for infectious diseases (dengue, malaria, etc.)
            if profile.has_fever and profile.fever_grade in ("high-grade", "moderate"):
                fever_symptoms = " ".join(profile.symptoms[:4])
                fever_query = (
                    f"infectious disease differential diagnosis: "
                    f"fever with {fever_symptoms}"
                )
                fever_chunks = await self.vectordb_retriever(fever_query, top_k=3)
                all_chunks.extend(fever_chunks)

            # Query 3: If red flags are present, search for emergencies
            if profile.red_flags:
                red_flag_query = (
                    f"medical emergency warning signs: "
                    f"{' '.join(profile.red_flags)}"
                )
                red_flag_chunks = await self.vectordb_retriever(red_flag_query, top_k=2)
                all_chunks.extend(red_flag_chunks)

        except Exception as e:
            logger.error(f"VectorDB retrieval error: {e}", exc_info=True)

        # Deduplicate chunks (same text can appear in multiple queries)
        seen = set()
        unique = []
        for chunk in all_chunks:
            fingerprint = chunk[:150] if chunk else ""
            if fingerprint and fingerprint not in seen:
                seen.add(fingerprint)
                unique.append(chunk)

        # Combine into a single context string (limit to ~8 chunks)
        context = "\n\n---\n\n".join(unique[:8])
        return context

    # ------------------------------------------------------------------
    # Stage 3: Diagnostic Reasoning (LLM)
    # ------------------------------------------------------------------

    async def _reason_diagnosis(
        self,
        profile: SymptomProfile,
        vectordb_context: str,
        user_profile: Dict = None,
    ) -> DiagnosisResult:
        """LLM reasons over symptoms + textbook context → diagnosis."""

        symptoms_summary = ", ".join(profile.symptoms)
        fever_info = (
            f"Present — {profile.fever_grade}" 
            if profile.has_fever 
            else "Not reported"
        )
        red_flags = ", ".join(profile.red_flags) if profile.red_flags else "None"

        # Build optional user context
        user_context = ""
        if user_profile:
            age = user_profile.get('age', 'unknown')
            sex = user_profile.get('sex', 'unknown')
            conditions = user_profile.get('medical_conditions', [])
            medications = user_profile.get('current_medications', [])
            user_context = f"\nPATIENT INFO: {age} years old, {sex}"
            if conditions:
                user_context += f", pre-existing: {', '.join(conditions)}"
            if medications:
                user_context += f", medications: {', '.join(medications)}"

        prompt = DIAGNOSIS_REASONING_PROMPT.format(
            symptoms_summary=symptoms_summary,
            severity=profile.severity,
            onset=profile.onset,
            duration=profile.duration,
            fever_info=fever_info,
            red_flags=red_flags,
            user_context=user_context,
            vectordb_context=(
                vectordb_context 
                if vectordb_context 
                else "No matching textbook content found. Use your general "
                     "medical knowledge, but note lower confidence."
            ),
        )

        try:
            raw = await self._call_llm(prompt, max_tokens=800, temperature=0.2)
            parsed = self._parse_json(raw)

            # Extract severity from first condition if present
            severity = profile.severity
            conditions = parsed.get("possible_conditions", [])
            if conditions and isinstance(conditions[0], dict):
                severity = conditions[0].get("severity_assessment", severity) or severity

            return DiagnosisResult(
                possible_conditions=conditions,
                primary_condition=parsed.get("primary_condition", "Unknown"),
                confidence=float(parsed.get("overall_confidence", 0.5)),
                needs_medical_attention=parsed.get("needs_medical_attention", False),
                is_emergency=parsed.get("is_emergency", False),
                home_remedy_appropriate=parsed.get("home_remedy_appropriate", True),
                severity=severity,
                reasoning=parsed.get("reasoning", ""),
                recommendation=parsed.get("recommendation", ""),
                triage_level=parsed.get("triage_level", "self-care"),
            )

        except Exception as e:
            logger.error(f"Diagnostic reasoning failed: {e}")
            # Safety fallback: multi-symptom + fever → cautious response
            if profile.symptom_count >= 3 and profile.has_fever:
                return DiagnosisResult(
                    needs_medical_attention=True,
                    is_emergency=False,
                    home_remedy_appropriate=False,
                    primary_condition="Undiagnosed multi-symptom condition",
                    severity="moderate",
                    confidence=0.3,
                    reasoning=(
                        "Multiple symptoms with fever detected. AI analysis "
                        "could not complete. Medical consultation recommended "
                        "as a safety precaution."
                    ),
                    recommendation="Please consult a doctor for proper diagnosis.",
                    triage_level="see-doctor",
                )
            return DiagnosisResult(home_remedy_appropriate=True, primary_condition="general health")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_simple_query(self, profile: SymptomProfile) -> bool:
        """
        A query is simple if the user described 2 or fewer symptoms
        with no fever and no real red flags.
        
        Simple queries go straight to the normal remedy pipeline —
        no diagnosis interception needed.
        """
        # 3+ symptoms = always run full diagnosis
        if profile.symptom_count >= 3:
            return False
        # High fever = always run full diagnosis
        if profile.fever_grade in ("high-grade", "moderate"):
            return False
        # Everything else (1-2 mild symptoms) = simple
        return True

    async def _call_llm(
        self, prompt: str, max_tokens: int = 500, temperature: float = 0.2
    ) -> str:
        try:
            from rag_service.openai_service import make_openai_request
            response, error, retries = await make_openai_request(prompt)
            if response and response.choices:
                return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
        return "{}"

    def _parse_json(self, text: str) -> Dict:
        """Robustly parse JSON from LLM output."""
        if not text:
            return {}
        
        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Extract from code blocks
        try:
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0].strip()
            elif "{" in text:
                start = text.index("{")
                end = text.rindex("}") + 1
                json_str = text[start:end]
            else:
                return {}
            return json.loads(json_str)
        except (json.JSONDecodeError, IndexError, ValueError):
            logger.warning(f"Could not parse LLM JSON: {text[:200]}...")
            return {}


# ---------------------------------------------------------------------------
# Response Builder — for when diagnosis says "don't give home remedies"
# ---------------------------------------------------------------------------

def build_diagnosis_response(
    diagnosis: DiagnosisResult,
    user_name: str = "there",
) -> str:
    """
    Build a user-facing response when the diagnosis engine determines
    the user has a serious condition that needs medical attention.
    
    This builds ONLY the diagnosis/triage portion. The rest of the
    response (remedies, Trust Engine, chronobiological timing) is
    handled by the normal pipeline.
    """
    profile = diagnosis.symptom_profile
    symptoms_str = ", ".join(profile.symptoms) if profile else "your symptoms"

    response = ""

    # Header based on severity
    if diagnosis.is_emergency:
        response += f"🚨 **URGENT HEALTH ALERT — {user_name}**\n\n"
    elif diagnosis.needs_medical_attention:
        response += f"⚠️ **IMPORTANT HEALTH NOTICE — {user_name}**\n\n"

    # Acknowledge symptoms
    response += (
        f"I've carefully analyzed the symptoms you described "
        f"({symptoms_str}).\n\n"
    )

    # Primary diagnosis with confidence
    if diagnosis.primary_condition and diagnosis.primary_condition != "Unknown":
        if diagnosis.confidence >= 0.7:
            emoji = "🟢"
        elif diagnosis.confidence >= 0.4:
            emoji = "🟡"
        else:
            emoji = "🔴"
        response += (
            f"**🩺 Assessment: {diagnosis.primary_condition}** "
            f"{emoji} ({diagnosis.confidence:.0%} confidence)\n\n"
        )

    # Clinical reasoning — clean, no textbook references
    if diagnosis.reasoning:
        response += f"**📋 Why I think this:**\n{diagnosis.reasoning}\n\n"

    # Differential diagnoses
    if len(diagnosis.possible_conditions) > 1:
        response += "**🔍 Other possibilities to consider:**\n"
        for cond in diagnosis.possible_conditions[1:4]:
            conf = cond.get("confidence", 0)
            name = cond.get("condition", "Unknown")
            diff = cond.get("key_differentiators", "")
            if conf >= 0.7:
                e = "🟢"
            elif conf >= 0.4:
                e = "🟡"
            else:
                e = "🔴"
            response += f"- {e} **{name}** ({conf:.0%}) — {diff}\n"
        response += "\n"

    # Recommendation
    if diagnosis.recommendation:
        response += f"**🏥 What you should do:**\n{diagnosis.recommendation}\n\n"

    # Action steps based on triage level
    if diagnosis.is_emergency or diagnosis.triage_level == "emergency":
        response += "---\n\n"
        response += "**🚑 IMMEDIATE ACTIONS:**\n"
        response += "1. **Go to the nearest hospital or emergency room NOW**\n"
        response += "2. **Do NOT rely on home remedies** for this condition\n"
        response += "3. **Call emergency services** if symptoms worsen\n"
        response += "4. **Stay hydrated** with water/ORS while heading to the hospital\n"
        response += "5. **Note the time** your symptoms started — doctors need this\n\n"
    elif diagnosis.triage_level in ("urgent-care", "see-doctor"):
        response += "---\n\n"
        response += "**💊 While awaiting medical care:**\n"
        response += "- Stay hydrated (water, ORS, clear broths)\n"
        response += "- Rest and avoid strenuous activity\n"
        response += "- Monitor your temperature regularly\n"
        response += "- Note all symptoms and when they started\n"
        timeframe = "today" if diagnosis.triage_level == "urgent-care" else "within 24-48 hours"
        response += f"- **See a doctor {timeframe}**\n\n"

    return response