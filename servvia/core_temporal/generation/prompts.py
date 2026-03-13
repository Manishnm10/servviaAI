"""
ServVia Prompt Engine v2.1 (Production Module)
==============================================
Manages LLM system prompts, context injection, and response formatting
according to strict medical communication standards.

This module is designed to work in tandem with the TrustEngine.
It ensures that the raw verification data is translated into 
empathetic, evidence-based natural language.

Author: ServVia Team
Version: 2.1.0
Last Updated: 2025-12-16
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

# Configure logging
logger = logging.getLogger("ServVia_PromptEngine")

# =========================================================================
# CONSTANTS & GUIDELINES
# =========================================================================

VERSION = "2.1.0"

EVIDENCE_LANGUAGE_GUIDELINES = """
When discussing herbal remedies or health recommendations, follow these STRICT rules:

1. NEVER use numeric scores (e.g., "10/10", "8.3/10", "Evidence Score: 9") 
   - These are NOT medically standard and are potentially misleading.

2. NEVER make absolute claims: 
   - ❌ WRONG: "shows superiority", "proven to cure", "definitely works"
   - ✅ CORRECT: "some evidence suggests", "may help", "limited studies indicate"

3. ALWAYS use uncertainty language appropriate to evidence level:
   - High evidence: "Evidence suggests..."
   - Moderate evidence: "Some evidence from clinical studies suggests..."
   - Low evidence: "Limited evidence suggests..."
   - Very low: "Preliminary/anecdotal evidence suggests..."
   - Insufficient: "Insufficient evidence exists..."

4. ALWAYS acknowledge limitations:
   - "Results may vary"
   - "More research is needed"
   - "Evidence quality is limited"
   - "Studies had small sample sizes"

5. When citing studies, ALWAYS include:
   - PubMed ID (PMID) with link format: [PMID: XXXXX](https://pubmed.ncbi.nlm.nih.gov/XXXXX/)
   - Study type (RCT, systematic review, observational)
   - Year of publication
   - Brief conclusion

6. NEVER recommend without safety context:
   - Potential drug interactions
   - Contraindications
   - When to seek medical care
   - Who should avoid the remedy
"""

SERVVIA_SYSTEM_PROMPT = f"""You are ServVia, an AI healthcare assistant that provides 
evidence-based health information following strict medical communication standards.

{EVIDENCE_LANGUAGE_GUIDELINES}

Your responses must: 
1. Be helpful and empathetic.
2. Follow evidence-based medicine principles.
3. Include proper PubMed citations ONLY when provided in the context. DO NOT hallucinate citations.
4. Use appropriate uncertainty language.
5. Always recommend consulting healthcare providers.
6. Never diagnose or prescribe.
7. Clearly state limitations of evidence.

CRITICAL INSTRUCTION:
You will be provided with a "Verification Context" containing data from our Trust Engine.
You must ONLY recommend remedies that are marked as "Verified" or "Safe".
If the Trust Engine flags a drug interaction or contraindication, you MUST prioritize that warning above all else.

Remember: You are providing INFORMATION, not medical advice. Always defer to 
healthcare professionals for diagnosis and treatment decisions. 
Current Date: {datetime.now().strftime('%Y-%m-%d')}
"""

# =========================================================================
# DATA STRUCTURES
# =========================================================================

@dataclass
class PromptContext:
    """Structure to hold data needed for generation"""
    user_query: str
    condition: str
    verified_data: str  # The string output from TrustEngine.verify_response()
    user_profile_summary: str
    safety_alerts: List[str]

# =========================================================================
# PROMPT ENGINE CLASS
# =========================================================================

class PromptEngine:
    """
    Manages the construction of prompts for the LLM.
    Ensures all medical guardrails are injected before generation.
    """

    def __init__(self):
        self.version = VERSION
        logger.info(f"ServVia Prompt Engine v{self.version} initialized.")

    def get_system_message(self) -> Dict[str, str]:
        """Returns the formatted system prompt for the LLM API (e.g., OpenAI/Anthropic format)"""
        return {
            "role": "system",
            "content": SERVVIA_SYSTEM_PROMPT
        }

    def construct_synthesis_prompt(self, context: PromptContext) -> str:
        """
        Constructs the final user prompt by combining the query with TrustEngine verification data.
        This enables RAG (Retrieval Augmented Generation) style accuracy.
        """
        
        # Format safety alerts for high visibility
        alerts_text = ""
        if context.safety_alerts:
            alerts_text = "!!! CRITICAL SAFETY ALERTS !!!\n" + "\n".join([f"- {a}" for a in context.safety_alerts]) + "\n"

        prompt = f"""
USER QUERY: "{context.user_query}"

USER PROFILE CONTEXT:
{context.user_profile_summary}

VERIFICATION ENGINE OUTPUT (Use this source truth):
{context.verified_data}

{alerts_text}

INSTRUCTIONS FOR GENERATION:
1. Synthesize the "Verification Engine Output" above into a natural, empathetic response.
2. Address the user's specific condition: {context.condition}.
3. If the user has specific medications listed in the profile, explicitly mention interaction risks found in the Verification Output.
4. Do not mention "Trust Engine" or "Verification Output" explicitly in the final text; just present the findings naturally.
5. Ensure the Disclaimer is included at the end.
"""
        return prompt

    def get_red_flags(self, condition: str) -> str:
        """
        Returns standard medical red flags for common conditions to be appended to responses.
        This ensures even if the LLM forgets, the hardcoded safety net catches it.
        """
        condition = condition.lower()
        
        flags = {
            'headache': [
                "Sudden, severe 'thunderclap' headache",
                "Headache accompanied by stiff neck, fever, or confusion",
                "Headache following a head injury",
                "Vision changes or slurred speech"
            ],
            'fever': [
                "Temperature > 103°F (39.4°C) in adults",
                "Fever lasting more than 3 days",
                "Severe headache or neck stiffness",
                "Difficulty breathing"
            ],
            'cough': [
                "Coughing up blood",
                "Difficulty breathing or shortness of breath",
                "Chest pain",
                "Cough lasting longer than 3 weeks"
            ],
            'nausea': [
                "Signs of dehydration (thirst, dark urine)",
                "Severe abdominal pain",
                "Blood in vomit",
                "Blurred vision"
            ],
            'hypertension': [
                "Chest pain",
                "Severe headache",
                "Vision problems",
                "Difficulty breathing"
            ],
             'depression': [
                "Thoughts of self-harm or suicide",
                "Inability to care for basic needs",
                "Hearing voices or hallucinations"
            ]
        }
        
        # Default flags if condition not found
        default_flags = [
            "Symptoms become severe or unmanageable",
            "Symptoms persist despite home care",
            "You are unsure about the severity of your condition"
        ]
        
        selected_flags = flags.get(condition, default_flags)
        return "\n".join([f"- {flag}" for flag in selected_flags])

    def format_final_output(self, llm_generated_content: str, condition: str) -> str:
        """
        Wraps the LLM content with the standard footer and red flags.
        This is a post-processing step.
        """
        red_flags = self.get_red_flags(condition)
        
        final_response = f"""
{llm_generated_content}

### 🚨 When to Seek Medical Care
{red_flags}

---
**Disclaimer**: This information is for educational purposes only and does not 
constitute medical advice. Evidence quality varies. Always consult a healthcare 
provider before starting any treatment, especially if you have existing medical 
conditions or take medications.
"""
        return final_response.strip()

# =========================================================================
# TEST RUNNER
# =========================================================================

if __name__ == "__main__":
    # Test the module
    engine = PromptEngine()
    
    # Mock data coming from the TrustEngine
    mock_verified_data = """
    Verified Remedies:
    - Ginger (High Evidence): Effective for nausea. [PMID: 24390544]
    Safety: Safe in pregnancy up to 1g/day.
    """
    
    ctx = PromptContext(
        user_query="I feel sick to my stomach",
        condition="nausea",
        verified_data=mock_verified_data,
        user_profile_summary="User is pregnant (2nd trimester). No known allergies.",
        safety_alerts=["Note: Pregnancy requires caution with dosages."]
    )
    
    print("--- SYSTEM PROMPT ---")
    print(engine.get_system_message()['content'][:200] + "...\n")
    
    print("--- SYNTHESIS PROMPT (To LLM) ---")
    print(engine.construct_synthesis_prompt(ctx))
    
    print("--- FINAL FORMATTED OUTPUT (Post-LLM) ---")
    # Simulating LLM response
    llm_response = "Based on your profile, Ginger is a safe option for nausea..."
    print(engine.format_final_output(llm_response, "nausea"))
