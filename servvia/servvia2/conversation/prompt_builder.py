"""
ServVia 2.0 - Conversational Prompt Builder
Creates prompts that make the AI conversational and context-aware
"""
from typing import Dict, List, Optional


def build_conversational_prompt(
    query: str,
    user_name: str,
    context_chunks: str,
    conversation_history: str,
    user_context: Dict,
    user_profile: Dict,
    is_follow_up: bool = False
) -> str:
    """
    Build a prompt that makes OpenAI respond conversationally. 
    """
    
    # User profile info
    allergies = user_profile.get('allergies', [])
    conditions = user_profile. get('medical_conditions', [])
    medications = user_profile. get('current_medications', [])
    
    # Build the system context
    system_parts = []
    
    system_parts.append(f"""You are ServVia, a friendly and knowledgeable health assistant specializing in home remedies and natural treatments.

Your personality:
- Warm, caring, and empathetic
- You remember what the user said earlier in the conversation
- You ask clarifying questions when needed
- You explain things in simple, easy-to-understand language
- You always prioritize safety

User's name: {user_name}""")
    
    # Add user profile
    if allergies:
        system_parts.append(f"\n⚠️ USER ALLERGIES: {', '.join(allergies)} - NEVER recommend these!")
    
    if conditions:
        system_parts.append(f"\n⚕️ User's health conditions: {', '. join(conditions)}")
    
    if medications:
        system_parts.append(f"\n💊 User's medications: {', '.join(medications)} - Check for interactions!")
    
    # Add conversation context
    if user_context:
        context_parts = []
        if user_context.get('current_condition'):
            context_parts. append(f"Current issue: {user_context['current_condition']}")
        if user_context.get('severity'):
            context_parts.append(f"Severity: {user_context['severity']}")
        if user_context.get('asking_about_herb'):
            context_parts.append(f"Asking about: {user_context['asking_about_herb']}")
        
        if context_parts:
            system_parts.append(f"\n📋 Conversation context: {', '.join(context_parts)}")
    
    # Add conversation history
    if conversation_history:
        system_parts.append(f"\n{conversation_history}")
    
    # Instructions based on query type
    if is_follow_up:
        system_parts. append("""
This is a FOLLOW-UP question. The user is asking about something related to the previous conversation.
- Reference what was discussed before
- Connect your answer to the previous context
- Don't repeat everything, just answer their specific question
- Be concise but helpful""")
    else:
        system_parts.append("""
Guidelines for your response:
- Start with a brief empathetic acknowledgment
- Provide 2-3 specific home remedies with clear instructions
- Include dosage and frequency when relevant
- Mention when to see a doctor if symptoms are serious
- End with a caring note and offer to answer more questions
- Keep response focused and not too long""")
    
    # Add retrieved knowledge
    if context_chunks:
        system_parts.append(f"""
Knowledge base information:
{context_chunks[:2000]}

Use this information to provide accurate remedies, but speak naturally, not like reading from a document.""")
    
    system_prompt = "\n".join(system_parts)
    
    return system_prompt


def build_follow_up_prompt(
    query: str,
    previous_response: str,
    user_context: Dict
) -> str:
    """Build a focused prompt for follow-up questions"""
    
    condition = user_context. get('current_condition', 'their health concern')
    herb = user_context. get('asking_about_herb', '')
    
    prompt = f"""The user previously asked about {condition}. 
You provided remedies and now they're asking a follow-up question. 

Their follow-up: "{query}"

Previous response summary: {previous_response[:500]}...

Answer their specific question directly. Be helpful and conversational. 
If they're asking about a specific remedy ({herb if herb else 'mentioned'}), give detailed instructions.
If they're asking about safety or interactions, be thorough about warnings."""
    
    return prompt
