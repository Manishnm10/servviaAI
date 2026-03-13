"""
ServVia 2.0 - Response Generator (Production Ready)
====================================================
Generates detailed, safe, personalized responses using OpenAI. 

Features:
- Context-aware prompting
- Safety instruction injection
- Medication change acknowledgment
- Detailed remedy formatting

Author: ServVia Team
Version: 2.0.0
"""

import datetime
import logging
from typing import Dict, List, Optional, Any
from asgiref.sync import sync_to_async

from legacy_healthcare.rag_service.openai_service import make_openai_request

logger = logging.getLogger(__name__)

# Try to import conversation manager
try:
    from core_temporal.conversation. manager import conversation_manager
    CONVERSATION_ENABLED = True
except ImportError:
    conversation_manager = None
    CONVERSATION_ENABLED = False


@sync_to_async
def get_user_profile_from_db(email_id: str) -> Optional[Dict]:
    """
    Fetch user profile from database asynchronously. 
    
    Args:
        email_id: User's email
    
    Returns:
        User profile dict or None
    """
    try:
        from user_profile.models import UserProfile
        profile = UserProfile.objects.get(email=email_id)
        return {
            'allergies': profile.get_allergies_list(),
            'medical_conditions': profile. get_conditions_list(),
            'current_medications': profile.get_medications_list(),
            'first_name': profile.first_name,
        }
    except Exception as e:
        logger.warning(f"Failed to fetch profile for {email_id}: {e}")
        return None


def build_system_prompt(
    user_name: str,
    user_profile: Dict,
    conversation_context: Dict,
    safety_instructions: str,
    context_changes: Dict,
) -> str:
    """
    Build a comprehensive system prompt for OpenAI.
    
    This is the core of response quality - a well-crafted prompt
    ensures safe, detailed, and helpful responses.
    """
    
    # Extract profile data
    allergies = user_profile.get('allergies', []) if user_profile else []
    profile_conditions = user_profile. get('medical_conditions', []) if user_profile else []
    profile_medications = user_profile.get('current_medications', []) if user_profile else []
    
    # Extract conversation context
    all_conditions = conversation_context.get('conditions', [])
    all_herbs = conversation_context.get('herbs', [])
    all_medications = conversation_context.get('medications', [])
    current_condition = conversation_context. get('current_condition', 'general health')
    history = conversation_context. get('history', '')
    
    # Build medication update acknowledgment
    medication_update = ""
    if context_changes.get('removed'):
        removed_meds = [
            r.replace('medication: ', '')
            for r in context_changes['removed']
            if 'medication:' in r
        ]
        if removed_meds:
            medication_update = f"""
📝 IMPORTANT UPDATE: The user just informed you they STOPPED taking: {', '.join(removed_meds)}

You MUST:
1. Acknowledge this update at the start of your response (e.g., "Thanks for letting me know you've stopped taking {removed_meds[0]}...")
2. These medications are NO LONGER a concern for interactions
3. You CAN now recommend remedies that were previously contraindicated due to these medications
"""
    
    if context_changes.get('added'):
        added_meds = [
            a.replace('medication: ', '')
            for a in context_changes['added']
            if 'medication:' in a
        ]
        if added_meds and not medication_update:
            medication_update = f"""
📝 UPDATE: The user just mentioned they are taking: {', '.join(added_meds)}
Note this for future interactions and check if any recommendations conflict with these medications.
"""
    
    # Build the system prompt
    prompt = f"""You are ServVia, a knowledgeable health assistant specializing in evidence based natural home remedies.

=== USER PROFILE ===
Name: {user_name}
Allergies: {', '.join(allergies) if allergies else 'None reported'}
Health Conditions: {', '.join(profile_conditions) if profile_conditions else 'None reported'}
Medications (from profile): {', '.join(profile_medications) if profile_medications else 'None reported'}

=== CURRENT CONVERSATION ===
Currently discussing: {current_condition or 'General inquiry'}
Conditions mentioned: {', '. join(all_conditions) if all_conditions else 'None'}
Remedies discussed: {', '.join(all_herbs) if all_herbs else 'None'}
Medications mentioned in chat: {', '.join(all_medications) if all_medications else 'None'}
{medication_update}
{safety_instructions}

=== CONVERSATION HISTORY ===
{history if history else 'This is the start of a new conversation. '}

=== RESPONSE GUIDELINES ===

**For health condition queries (headache, fever, cold, etc.), provide EXACTLY this format:**

Start with a brief empathetic statement (1 sentence acknowledging their condition). 

Then provide **4-5 detailed remedies** using this EXACT format for EACH remedy:

**Remedy 1: [Remedy Name]**
- **Ingredients:** [List exact quantities - e.g., "1 inch fresh ginger (about 10g)", "2 cups (500ml) water", "1 tablespoon honey"]
- **Preparation:** 
  1. [Step-by-step numbered instructions]
  2. [Be specific about timing, temperature, etc.]
  3. [Include tips for best results]
- **How to use:** [Exact dosage and method of consumption/application]
- **Frequency:** [How often - e.g., "2-3 times daily, preferably after meals"]
- **Duration:** [How long to continue - e.g., "Continue for 3-5 days until symptoms improve"]
- **Why it works:** [Brief 1-sentence explanation of mechanism]

[Repeat for Remedies 2, 3, 4, and optionally 5]

**Safety Notes:**
- [Any relevant warnings or precautions]
- [Who should avoid this remedy]
- [Potential side effects to watch for]

**When to See a Doctor:**
- [Specific red flags that require medical attention]
- [Timeframe - e.g., "If symptoms persist beyond 3 days"]
- [Emergency signs to watch for]

**For follow-up questions:**
- Answer directly and specifically
- Reference the ongoing conversation
- If asking about a specific remedy, give detailed usage instructions
- Don't repeat all remedies, just address their question

**For medication-related questions:**
- If user mentions stopping a medication, acknowledge it and adjust recommendations accordingly
- If there's a safety alert above, follow those instructions exactly
- Be definitive about dangers, not vague

=== CRITICAL RULES ===
1.  ALWAYS give 4-5 detailed remedies with exact measurements for health conditions
2.  NEVER recommend anything the user is allergic to: {allergies}
3. ALWAYS check interactions with current medications: {all_medications}
4. NEVER say "generally safe" when there's an interaction risk
5.  ALWAYS provide specific measurements (not "some" or "a little")
6.  ALWAYS include preparation steps
7. ALWAYS include frequency and duration
8.  If user stopped a medication, acknowledge it and note that related interaction warnings no longer apply"""

    return prompt


async def generate_query_response(
    original_query: str,
    user_name: str,
    context_chunks: str,
    rephrased_query: str,
    email_id: str = None,
    user_profile: Dict = None,
    chat_history: List = None,
    safety_instructions: str = "",
    conversation_context: Dict = None,
    context_changes: Dict = None,
) -> Dict[str, Any]:
    """
    Generate a response using OpenAI with full context awareness.
    
    Args:
        original_query: User's original question
        user_name: User's name for personalization
        context_chunks: Retrieved knowledge base content
        rephrased_query: Rephrased query for retrieval
        email_id: User's email for profile lookup
        user_profile: Pre-fetched user profile (optional)
        chat_history: Previous chat history (optional)
        safety_instructions: Safety warnings to inject
        conversation_context: Tracked conversation context
        context_changes: Recent context changes (added/removed items)
    
    Returns:
        Response map with generated text and metadata
    """
    
    # Initialize response map
    response_map = {
        "response": None,
        "original_query": original_query,
        "rephrased_query": rephrased_query,
        "generation_start_time": None,
        "generation_end_time": None,
        "completion_tokens": 0,
        "prompt_tokens": 0,
        "total_tokens": 0,
        "response_gen_exception": None,
        "response_gen_retries": 0,
    }
    
    # Get user name
    name = user_name or "there"
    
    # Fetch profile if not provided
    if not user_profile and email_id:
        user_profile = await get_user_profile_from_db(email_id)
        if user_profile and user_profile.get('first_name'):
            name = user_profile['first_name']
    
    # Ensure we have defaults
    conversation_context = conversation_context or {}
    context_changes = context_changes or {'added': [], 'removed': []}
    
    # Build system prompt
    system_prompt = build_system_prompt(
        user_name=name,
        user_profile=user_profile or {},
        conversation_context=conversation_context,
        safety_instructions=safety_instructions,
        context_changes=context_changes,
    )
    
    # Build the full prompt
    full_prompt = f"""{system_prompt}

=== KNOWLEDGE BASE CONTEXT ===
{context_chunks[:3000] if context_chunks else 'Using general natural home knowledge. '}

=== USER'S CURRENT QUESTION ===
{original_query}

=== YOUR RESPONSE ===
Provide a helpful, detailed response following the guidelines above:"""

    # Generate response
    response_map["generation_start_time"] = datetime.datetime.now()
    
    try:
        generated_response, exception, retries = await make_openai_request(full_prompt)
        
        response_map["response_gen_exception"] = str(exception) if exception else None
        response_map["response_gen_retries"] = retries
        
        if generated_response:
            response_map["response"] = generated_response. choices[0].message. content
            
            # Extract usage stats
            usage = getattr(generated_response, "usage", None)
            if usage:
                response_map["completion_tokens"] = getattr(usage, "completion_tokens", 0)
                response_map["prompt_tokens"] = getattr(usage, "prompt_tokens", 0)
                response_map["total_tokens"] = getattr(usage, "total_tokens", 0)
        else:
            response_map["response"] = "I apologize, but I'm having trouble generating a response right now. Please try again in a moment."
            
    except Exception as e:
        logger.error(f"Response generation failed: {e}")
        response_map["response"] = "I apologize, but I encountered an error.  Please try again."
        response_map["response_gen_exception"] = str(e)
    
    response_map["generation_end_time"] = datetime.datetime.now()
    
    # Log generation stats
    if response_map["response"]:
        logger.info(f"Generated response: {len(response_map['response'])} chars, {response_map['total_tokens']} tokens")
    
    return response_map
