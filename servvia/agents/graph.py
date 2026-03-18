"""
ServVia 4.0 -Multi-Agent Verification Graph
==============================================

LangGraph StateGraph implementing a Diagnostician -> Proposer -> Critic -> Fallback
circuit breaker for clinical safety verification with GPT-5o-mini diagnosis.

Architecture:
    ┌───────────────┐     ┌──────────┐     ┌──────────┐
    │ Diagnostician │────▶│ Proposer │────▶│  Critic  │
    │ (GPT-5o-mini) │     └──────────┘     └──────────┘
    └───────────────┘          ▲                │
                               │          ┌─────┴─────┐
                               │          │           │
                               │     approved?   rejected?
                               │          │           │
                               │          ▼           ▼
                               │        [END]   revision_count < 2?
                               │                  │          │
                               │                 yes         no
                               │                  │          │
                               └──────────────────┘          ▼
                                                    ┌──────────────┐
                                                    │   Fallback   │
                                                    │ (hardcoded)  │
                                                    └──────────────┘

Author: ServVia Engineering
Version: 4.0.0
"""

import json
import logging
import asyncio
import os
import sys
from datetime import datetime
from typing import TypedDict

from langgraph.graph import StateGraph, END

from agents.prompts import (
    DIAGNOSTICIAN_PROMPT,
    PROPOSER_PROMPT,
    CRITIC_PROMPT,
    FALLBACK_RESPONSE,
)
from django_core.config import Config

logger = logging.getLogger("ServVia.MultiAgent")


def _trace(msg: str):
    """Write timestamped trace to stdout with safe encoding for Windows."""
    ts = datetime.now().strftime("%H:%M:%S")
    # Encode safely for Windows cp1252 -replace unsupported chars
    safe_msg = msg.encode("ascii", errors="replace").decode("ascii")
    try:
        sys.__stdout__.write(f"  [AGENT {ts}] {safe_msg}\n")
        sys.__stdout__.flush()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# LEAN GRAPH STATE -Minimal payload to save tokens
# ═══════════════════════════════════════════════════════════════════════════

class AgentState(TypedDict):
    user_symptoms: str       # Original user query
    draft_response: str      # Proposer's current output
    critic_feedback: str     # Critic's JSON feedback (for revision)
    revision_count: int      # Circuit breaker counter
    rag_context: str         # RAG chunks (Proposer only -NOT sent to Critic)
    bio_context: str         # Chronobiology advisory string
    # ── Diagnostician output ──
    diagnosis_output: str    # Structured JSON from GPT-5o-mini diagnostician
    symptom_list: list       # Parsed individual symptoms
    primary_condition: str   # Diagnosed condition name (e.g. "Dengue Fever")
    # ── User profile (injected into Proposer for allergen-free generation) ──
    user_name: str           # Patient's first name (empty string if unknown)
    user_allergies: list     # Declared allergens -LLM must never suggest these
    user_medications: list   # Current medications -LLM checks interactions
    user_conditions: list    # Known medical conditions


# ═══════════════════════════════════════════════════════════════════════════
# GROQ FALLBACK -Called when primary OpenAI/GitHub Models hits 429
# ═══════════════════════════════════════════════════════════════════════════

async def _call_groq(
    prompt: str,
    model: str,
    temperature: float = 0.3,
) -> str:
    """
    Fallback LLM call via Groq API. Uses the same prompt and expects
    identical output format (plain text or JSON) as the primary model.
    Returns the response text or empty string on failure.
    """
    from groq import AsyncGroq, RateLimitError as GroqRateLimitError

    api_key = Config.GROQ_API_KEY
    if not api_key:
        logger.error("GROQ_API_KEY not set — Groq fallback unavailable")
        return ""

    client = AsyncGroq(api_key=api_key)

    try:
        _trace(f"Groq FALLBACK | model={model} | temp={temperature}")
        logger.info(f"[GROQ] Fallback call | model={model}")

        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )

        if response and response.choices:
            content = response.choices[0].message.content
            if content:
                _trace(f"Groq FALLBACK OK | {len(content)} chars")
                logger.info(f"[GROQ] Fallback success | {len(content)} chars")
                return content.strip()

        logger.error("[GROQ] Fallback returned empty content")
        return ""
    except GroqRateLimitError as e:
        logger.error(f"[GROQ] Fallback also rate-limited: {e}")
        return ""
    except Exception as e:
        logger.error(f"[GROQ] Fallback exception: {e}", exc_info=True)
        return ""


# ═══════════════════════════════════════════════════════════════════════════
# LLM CALL HELPER -Primary OpenAI with Groq 429 fallback
# ═══════════════════════════════════════════════════════════════════════════

async def _call_llm(
    prompt: str,
    temperature: float = 0.3,
    model: str = None,
    agent_role: str = None,
) -> str:
    """
    Call primary OpenAI endpoint. If the primary exhausts retries (typically
    due to 429 rate limit), automatically fall back to Groq.

    Args:
        prompt: The full prompt string.
        temperature: Sampling temperature (ignored for reasoning models).
        model: Primary OpenAI model name.
        agent_role: One of 'diagnostician', 'proposer', 'critic' — used to
                    select the correct Groq fallback model.

    Returns the response text or empty string on failure.
    """
    from legacy_healthcare.rag_service.openai_service import make_openai_request
    from django_core.config import Config

    kwargs = {"temperature": temperature, "max_retries": 2}
    if model:
        kwargs["model"] = model

    # ── 1. Try primary (OpenAI / GitHub Models) ──
    try:
        response, exception, retries = await make_openai_request(prompt, **kwargs)
        if response and response.choices:
            content = response.choices[0].message.content
            if content:
                return content.strip()
            logger.error("LLM returned a response with empty content")
        else:
            logger.warning(
                f"Primary LLM failed after {retries} retries | "
                f"API error: {exception}"
            )
    except Exception as e:
        logger.error(f"Primary LLM exception: {e}", exc_info=True)
        exception = str(e)

    # ── 2. Fallback to Groq on primary failure ──
    if not agent_role:
        logger.warning("No agent_role specified — cannot select Groq fallback model")
        return ""

    groq_model = Config.GROQ_FALLBACK_MODELS.get(agent_role)
    if not groq_model:
        logger.warning(f"No Groq fallback model configured for role '{agent_role}'")
        return ""

    _trace(f"Primary FAILED — falling back to Groq ({groq_model})")
    logger.info(
        f"[FALLBACK] Primary {model} failed — switching to Groq {groq_model} "
        f"for {agent_role}"
    )

    # Critic uses temp=0.0 on Groq (deterministic); others keep their temperature
    groq_temp = 0.0 if agent_role == "critic" else temperature

    return await _call_groq(prompt, model=groq_model, temperature=groq_temp)


# ═══════════════════════════════════════════════════════════════════════════
# NODE: DIAGNOSTICIAN — GPT-4.1 Clinical Diagnosis Engine
# ═══════════════════════════════════════════════════════════════════════════

async def diagnostician_node(state: AgentState) -> dict:
    """
    GPT-4.1 diagnostic analysis node.
    Produces a structured clinical assessment with reasoning,
    individual symptom parsing, and per-symptom remedy suggestions.
    Runs ONCE — revision loops skip this node and reuse cached diagnosis.
    """
    from django_core.config import Config

    allergies = state.get("user_allergies") or []
    medications = state.get("user_medications") or []
    conditions = state.get("user_conditions") or []

    allergies_str = ", ".join(str(a) for a in allergies) if allergies else "None declared"
    medications_str = ", ".join(str(m) for m in medications) if medications else "None declared"
    conditions_str = ", ".join(str(c) for c in conditions) if conditions else "None declared"

    # Skip if diagnosis was pre-computed (parallel execution from views.py)
    if state.get("diagnosis_output"):
        _trace("Diagnostician SKIP | Pre-computed diagnosis found")
        return {}

    _trace(f"Diagnostician START | Model: {Config.GPT_5_MINI_MODEL}")
    logger.info(
        f"[DIAG]Diagnostician node | Model: {Config.GPT_5_MINI_MODEL} | "
        f"Query: {state['user_symptoms'][:80]}"
    )

    try:
        prompt = DIAGNOSTICIAN_PROMPT.format(
            user_allergies=allergies_str,
            user_medications=medications_str,
            user_conditions=conditions_str,
            user_symptoms=state["user_symptoms"],
            rag_context=state.get("rag_context", "No additional context available."),
        )
    except Exception as fmt_err:
        logger.error(f"DIAGNOSTICIAN prompt format error: {fmt_err}", exc_info=True)
        return {"diagnosis_output": "", "symptom_list": []}

    try:
        raw_output = await _call_llm(
            prompt,
            temperature=0.2,
            model=Config.GPT_5_MINI_MODEL,
            agent_role="diagnostician",
        )
    except Exception as llm_err:
        logger.error(f"DIAGNOSTICIAN _call_llm exception: {llm_err}", exc_info=True)
        return {"diagnosis_output": "", "symptom_list": []}

    if not raw_output:
        logger.warning(
            "Diagnostician returned empty -Proposer will operate without diagnosis"
        )
        return {"diagnosis_output": "", "symptom_list": []}

    # Parse the structured JSON
    try:
        cleaned = raw_output.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0].strip()

        diagnosis = json.loads(cleaned)
        symptom_list = diagnosis.get("symptom_list", [])
        primary_condition = diagnosis.get("primary_condition", "")
        _trace(f"Diagnostician DONE | severity={diagnosis.get('severity')} | condition={primary_condition} | symptoms={len(symptom_list)}")
        logger.info(
            f"[DIAG]Diagnostician result: severity={diagnosis.get('severity')} | "
            f"condition={primary_condition} | symptoms={symptom_list} | "
            f"assessment={diagnosis.get('assessment', '')[:100]}"
        )
        return {
            "diagnosis_output": cleaned,
            "symptom_list": symptom_list,
            "primary_condition": primary_condition,
        }
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(
            f"Diagnostician JSON parse failed: {e} | Raw: {raw_output[:200]}"
        )
        # Pass raw text as best-effort -Proposer can still use it
        return {"diagnosis_output": raw_output[:1500], "symptom_list": [], "primary_condition": ""}


# ═══════════════════════════════════════════════════════════════════════════
# NODE: PROPOSER -Clinical triage assistant
# ═══════════════════════════════════════════════════════════════════════════

async def proposer_node(state: AgentState) -> dict:
    """
    Generate a clinically safe response. On revision, incorporates
    the Critic's feedback to fix issues. Uses cached diagnosis from
    the Diagnostician node.
    """
    feedback_section = ""
    if state.get("critic_feedback"):
        feedback_section = (
            f"\n\n=== REVISION REQUIRED ===\n"
            f"Your previous draft was REJECTED by the medical peer reviewer.\n"
            f"Feedback: {state['critic_feedback']}\n"
            f"Fix the issues above in your revised response. "
            f"Do NOT repeat the same mistakes.\n"
        )

    # Format user profile lists into readable strings for the prompt
    allergies = state.get("user_allergies") or []
    medications = state.get("user_medications") or []
    conditions = state.get("user_conditions") or []
    name = state.get("user_name") or ""

    allergies_str  = ", ".join(str(a) for a in allergies)  if allergies  else "None declared"
    medications_str = ", ".join(str(m) for m in medications) if medications else "None declared"
    conditions_str  = ", ".join(str(c) for c in conditions)  if conditions  else "None declared"

    # Format diagnosis context from Diagnostician output
    diagnosis_raw = state.get("diagnosis_output", "")
    if diagnosis_raw:
        diagnosis_context = (
            f"=== DIAGNOSTIC ASSESSMENT (GPT-5o-mini Clinical Analysis) ===\n"
            f"{diagnosis_raw}\n"
            f"=== END DIAGNOSTIC ASSESSMENT ===\n"
            f"Use this assessment in your response. Include the reasoning."
        )
    else:
        diagnosis_context = "No diagnostic assessment available. Do NOT state a diagnosis."

    revision = state.get("revision_count", 0)
    _trace(f"Proposer START | Revision #{revision}")
    logger.info(
        f"Proposer node | Revision #{revision} | "
        f"Query: {state['user_symptoms'][:80]}"
    )

    # Get condition name from diagnostician -used in the h2 header
    condition_name = state.get("primary_condition", "") or "Under Evaluation"

    try:
        prompt = PROPOSER_PROMPT.format(
            user_name=name,
            user_allergies=allergies_str,
            user_medications=medications_str,
            user_conditions=conditions_str,
            user_symptoms=state["user_symptoms"],
            rag_context=state.get("rag_context", "No additional context available."),
            bio_context=state.get("bio_context", "No chronobiology context."),
            critic_feedback=feedback_section,
            diagnosis_context=diagnosis_context,
            condition_name=condition_name,
        )
    except Exception as fmt_err:
        logger.error(f"PROPOSER prompt format error: {fmt_err}", exc_info=True)
        return {"draft_response": FALLBACK_RESPONSE}

    logger.debug(f"Proposer prompt length: {len(prompt)} chars")

    try:
        draft = await _call_llm(
            prompt,
            temperature=0.3,
            model=Config.MODEL_CHAT,
            agent_role="proposer",
        )
    except Exception as llm_err:
        logger.error(f"PROPOSER _call_llm exception: {llm_err}", exc_info=True)
        return {"draft_response": FALLBACK_RESPONSE}

    if not draft:
        logger.warning(
            "Proposer LLM returned empty string -check API key, model name, "
            "and server logs for 'LLM call failed' errors"
        )
        draft = FALLBACK_RESPONSE
    else:
        _trace(f"Proposer DONE | Draft length: {len(draft)} chars")
        logger.info(f"Proposer draft length: {len(draft)} chars")

    return {"draft_response": draft}


# ═══════════════════════════════════════════════════════════════════════════
# NODE: CRITIC -Medical peer reviewer
# ═══════════════════════════════════════════════════════════════════════════

async def critic_node(state: AgentState) -> dict:
    """
    Review the Proposer's draft for clinical safety.
    Only receives symptoms + draft (NOT the RAG chunks) to save tokens.
    Outputs minimal JSON: {"is_approved": bool, "feedback": str}
    """
    prompt = CRITIC_PROMPT.format(
        user_symptoms=state["user_symptoms"],
        draft_response=state["draft_response"],
    )

    _trace("Critic START | Reviewing draft...")
    logger.info("[CRITIC]Critic node | Reviewing draft for clinical safety...")

    # o3-mini is a reasoning model: temperature is omitted (400 error if sent),
    # reasoning_effort="high" is injected by make_openai_request automatically.
    # On Groq fallback, critic uses llama-3.3-70b-versatile with temp=0.0
    raw_output = await _call_llm(
        prompt,
        model=Config.MODEL_BRAIN,
        agent_role="critic",
    )

    # Parse the Critic's JSON output
    try:
        # Strip any markdown fences the LLM might add
        cleaned = raw_output.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        verdict = json.loads(cleaned)
        is_approved = verdict.get("is_approved", True)
        feedback = verdict.get("feedback", "No feedback provided")
    except (json.JSONDecodeError, AttributeError) as e:
        _trace(f"Critic JSON PARSE FAILED -defaulting to APPROVE | {e}")
        logger.warning(f"Critic JSON parse failed: {e} | Raw: {raw_output[:200]}")
        # Default to APPROVE on parse failure -safety is better served
        # by showing a medical-referral response than triggering fallback
        is_approved = True
        feedback = "Auto-approved (Critic output was unparseable)"

    _trace(f"Critic DONE | approved={is_approved} | {feedback[:80]}")
    logger.info(f"[CRITIC]Critic verdict: approved={is_approved} | {feedback[:100]}")

    # Encode the verdict back into the state
    critic_result = json.dumps({"is_approved": is_approved, "feedback": feedback})

    return {
        "critic_feedback": critic_result,
        "revision_count": state.get("revision_count", 0) + 1,
    }


# ═══════════════════════════════════════════════════════════════════════════
# NODE: FALLBACK -Zero-LLM hardcoded safe response
# ═══════════════════════════════════════════════════════════════════════════

async def fallback_node(state: AgentState) -> dict:
    """
    Circuit breaker: after failed revisions, bypass LLM entirely
    and return a hardcoded safe response.
    """
    logger.critical(
        f"[ALERT]FALLBACK TRIGGERED | Revision count: {state['revision_count']} | "
        f"Query: {state['user_symptoms'][:80]}"
    )
    return {"draft_response": FALLBACK_RESPONSE}


# ═══════════════════════════════════════════════════════════════════════════
# CONDITIONAL ROUTING -Circuit breaker logic
# ═══════════════════════════════════════════════════════════════════════════

def route_after_critic(state: AgentState) -> str:
    """
    Route based on Critic's verdict and revision count:
      - approved -> END
      - rejected + revision_count < 2 -> back to Proposer (revision)
      - rejected + revision_count >= 2 -> Fallback
    """
    try:
        verdict = json.loads(state.get("critic_feedback", "{}"))
        is_approved = verdict.get("is_approved", True)
    except (json.JSONDecodeError, TypeError):
        is_approved = True  # Default approve on parse failure

    if is_approved:
        logger.info("[OK]Critic APPROVED -routing to final output")
        return "approved"

    revision_count = state.get("revision_count", 0)

    if revision_count < 2:
        logger.info(f"[REVISE]Critic REJECTED -routing to Proposer for revision #{revision_count}")
        return "revise"
    else:
        logger.warning(f"[BLOCK]Critic REJECTED x{revision_count} -routing to FALLBACK")
        return "fallback"


# ═══════════════════════════════════════════════════════════════════════════
# GRAPH BUILDER -Compile the LangGraph workflow
# ═══════════════════════════════════════════════════════════════════════════

def build_verification_graph() -> StateGraph:
    """
    Build and compile the multi-agent verification graph.

    Flow:
        diagnostician -> proposer -> critic ->
        [approved: END | revise: proposer | fallback: fallback_node -> END]

    Revision loops go back to Proposer (NOT Diagnostician) -diagnosis
    is cached in state and reused, saving an expensive GPT-5o-mini call.

    Returns:
        Compiled LangGraph runnable.
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("diagnostician", diagnostician_node)
    graph.add_node("proposer", proposer_node)
    graph.add_node("critic", critic_node)
    graph.add_node("fallback", fallback_node)

    # Set entry point -Diagnostician runs first
    graph.set_entry_point("diagnostician")

    # Diagnostician -> Proposer (always)
    graph.add_edge("diagnostician", "proposer")

    # Proposer -> Critic (always)
    graph.add_edge("proposer", "critic")

    # Critic -> conditional routing
    graph.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "approved": END,
            "revise": "proposer",
            "fallback": "fallback",
        },
    )

    # Fallback -> END (always)
    graph.add_edge("fallback", END)

    compiled = graph.compile()
    logger.info("[BUILD]Multi-Agent Verification Graph compiled (with Diagnostician)")
    return compiled


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON -Compile once, reuse across requests
# ═══════════════════════════════════════════════════════════════════════════

_compiled_graph = None


def get_verification_graph():
    """Get or create the compiled verification graph singleton."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_verification_graph()
    return _compiled_graph


async def run_proposer_only(
    user_symptoms: str,
    rag_context: str = "",
    bio_context: str = "",
    user_name: str = "",
    user_allergies: list = None,
    user_medications: list = None,
    user_conditions: list = None,
) -> str:
    """
    Fast path for minor queries — Proposer only, no Critic review.
    Saves one LLM call (~5-10s) for simple ailments like headache, cold, etc.
    """
    state: AgentState = {
        "user_symptoms": user_symptoms,
        "draft_response": "",
        "critic_feedback": "",
        "revision_count": 0,
        "rag_context": rag_context[:2000],
        "bio_context": bio_context,
        "diagnosis_output": "",
        "symptom_list": [],
        "primary_condition": "",
        "user_name": user_name or "",
        "user_allergies": user_allergies or [],
        "user_medications": user_medications or [],
        "user_conditions": user_conditions or [],
    }

    _trace("Proposer-ONLY fast path (minor query, skipping Critic)")
    result = await proposer_node(state)
    draft = result.get("draft_response", FALLBACK_RESPONSE)
    if not draft:
        draft = FALLBACK_RESPONSE
    _trace(f"Proposer-ONLY DONE | {len(draft)} chars")
    return draft


async def run_diagnostician_standalone(
    user_symptoms: str,
    user_allergies: list = None,
    user_medications: list = None,
    user_conditions: list = None,
) -> dict:
    """
    Run GPT-5o-mini Diagnostician as a standalone call (for parallel execution).
    Returns dict with diagnosis_output, symptom_list, primary_condition.
    """
    from django_core.config import Config

    allergies = user_allergies or []
    medications = user_medications or []
    conditions = user_conditions or []

    allergies_str = ", ".join(str(a) for a in allergies) if allergies else "None declared"
    medications_str = ", ".join(str(m) for m in medications) if medications else "None declared"
    conditions_str = ", ".join(str(c) for c in conditions) if conditions else "None declared"

    _trace(f"Diagnostician PARALLEL START | Model: {Config.GPT_5_MINI_MODEL}")

    try:
        prompt = DIAGNOSTICIAN_PROMPT.format(
            user_allergies=allergies_str,
            user_medications=medications_str,
            user_conditions=conditions_str,
            user_symptoms=user_symptoms,
            rag_context="Use your own medical knowledge for diagnosis.",
        )
    except Exception as fmt_err:
        _trace(f"Diagnostician prompt format error: {fmt_err}")
        return {"diagnosis_output": "", "symptom_list": [], "primary_condition": ""}

    try:
        raw_output = await _call_llm(
            prompt,
            temperature=0.2,
            model=Config.GPT_5_MINI_MODEL,
            agent_role="diagnostician",
        )
    except Exception as llm_err:
        _trace(f"Diagnostician LLM error: {llm_err}")
        return {"diagnosis_output": "", "symptom_list": [], "primary_condition": ""}

    if not raw_output:
        _trace("Diagnostician returned empty")
        return {"diagnosis_output": "", "symptom_list": [], "primary_condition": ""}

    try:
        cleaned = raw_output.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0].strip()

        diagnosis = json.loads(cleaned)
        symptom_list = diagnosis.get("symptom_list", [])
        primary_condition = diagnosis.get("primary_condition", "")
        _trace(f"Diagnostician PARALLEL DONE | condition={primary_condition} | severity={diagnosis.get('severity')}")
        return {
            "diagnosis_output": cleaned,
            "symptom_list": symptom_list,
            "primary_condition": primary_condition,
        }
    except (json.JSONDecodeError, AttributeError) as e:
        _trace(f"Diagnostician JSON parse failed: {e}")
        return {"diagnosis_output": raw_output[:1500], "symptom_list": [], "primary_condition": ""}


async def run_verification_pipeline(
    user_symptoms: str,
    rag_context: str = "",
    bio_context: str = "",
    user_name: str = "",
    user_allergies: list = None,
    user_medications: list = None,
    user_conditions: list = None,
    # Pre-computed diagnosis (from parallel execution)
    diagnosis_output: str = "",
    symptom_list: list = None,
    primary_condition: str = "",
) -> str:
    """
    Execute the Diagnostician -> Proposer -> Critic -> Fallback pipeline.
    If diagnosis_output is provided, the Diagnostician node is skipped (parallel mode).
    """
    graph = get_verification_graph()

    initial_state: AgentState = {
        "user_symptoms": user_symptoms,
        "draft_response": "",
        "critic_feedback": "",
        "revision_count": 0,
        "rag_context": rag_context[:2000],
        "bio_context": bio_context,
        "diagnosis_output": diagnosis_output,
        "symptom_list": symptom_list or [],
        "primary_condition": primary_condition,
        "user_name": user_name or "",
        "user_allergies": user_allergies or [],
        "user_medications": user_medications or [],
        "user_conditions": user_conditions or [],
    }

    mode = "parallel (diagnosis pre-computed)" if diagnosis_output else "sequential"
    _trace(f"Pipeline START | mode={mode}")
    logger.info(f"[START]Starting Multi-Agent Pipeline | mode={mode} | Query: {user_symptoms[:80]}...")

    final_state = await graph.ainvoke(initial_state)

    pipeline_path = "diagnostician->proposer->critic" if not diagnosis_output else "proposer->critic"
    revision_count = final_state.get("revision_count", 0)
    if revision_count > 1:
        pipeline_path += f"->revision({revision_count - 1})"

    if final_state.get("draft_response") == FALLBACK_RESPONSE:
        pipeline_path += "->FALLBACK"

    _trace(f"Pipeline DONE | Path: {pipeline_path}")
    logger.info(f"[OK]Multi-Agent Pipeline complete | Path: {pipeline_path}")

    return final_state.get("draft_response", FALLBACK_RESPONSE)
