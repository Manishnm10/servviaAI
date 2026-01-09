"""
ServVia 2.0 - Response Generator (Production Ready)
====================================================
Generates detailed, safe, personalized responses using OpenAI. 

Features:
- Context-aware prompting
- Safety instruction injection
- Medication change acknowledgment
- Detailed remedy formatting
- Age-appropriate recommendations (AI-driven, not hardcoded)

Author: ServVia Team
Version:  2.1.0
"""

import datetime
import logging
from typing import Dict, List, Optional, Any
from asgiref.sync import sync_to_async

from rag_service.openai_service import make_openai_request

logger = logging.getLogger(__name__)

# Try to import conversation manager
try:
    from servvia2.conversation.manager import conversation_manager
    CONVERSATION_ENABLED = True
except ImportError: 
    conversation_manager = None
    CONVERSATION_ENABLED = False


@sync_to_async
def get_user_profile_from_db(email_id: str) -> Optional[Dict]:
    """
    Fetch user profile from database asynchronously.
    """
    try:
        from user_profile. models import UserProfile
        profile = UserProfile.objects.get(email=email_id)
        return {
            'allergies': profile.get_allergies_list(),
            'medical_conditions': profile.get_conditions_list(),
            'current_medications': profile.get_medications_list(),
            'first_name': profile. first_name,
            'age': profile.age,
            'sex': profile.sex,
            'age_group': profile.get_age_group(),
        }
    except Exception as e: 
        logger.warning(f"Failed to fetch profile for {email_id}: {e}")
        return None


def get_age_safety_context(age: int, age_group:  str, asking_for_other: bool = False, relationship: str = None, query_subject: str = None) -> Dict[str, Any]:
    """
    Generate comprehensive age-based safety context.
    
    Instead of hardcoding specific ingredients, we provide the AI with
    medical guidelines and let it + Trust Engine make informed decisions. 
    
    This approach is better because:
    1. Medical knowledge evolves - AI can stay current
    2. Context matters - some ingredients safe in small amounts
    3. Trust Engine validates against evidence database
    4. More comprehensive than any hardcoded list
    """
    
    # Add context prefix if asking for someone else
    context_prefix = ""
    if asking_for_other: 
        subject_desc = query_subject or f"their {relationship}" if relationship else "someone else"
        context_prefix = f"""
🎯🎯🎯 IMPORTANT:  USER IS ASKING FOR {subject_desc. upper()} 🎯🎯🎯
The user is NOT asking about themselves. They are asking for:  {subject_desc}
ALL recommendations must be appropriate for {subject_desc}.
Start your response with: "For your {relationship or 'family member'} ({subject_desc})..."
================================================================================
"""
    
    if not age:
        return {
            'age_category': 'unknown',
            'safety_level': 'standard',
            'dosage_modifier': 1.0,
            'guidelines': context_prefix + 'Age not specified.  Using standard adult guidelines.',
            'special_instructions': ''
        }
    
    # Infant (0-2 years)
    if age < 2:
        return {
            'age_category':  'infant',
            'safety_level': 'maximum_caution',
            'dosage_modifier': 0.1,  # 10% of adult dose max
            'guidelines': f"""
🚨 INFANT SAFETY PROTOCOL (Age:  {age} {'year' if age == 1 else 'months' if age < 1 else 'years'}) 🚨

MEDICAL REALITY:  Infants have immature organ systems that cannot process many substances safely.

YOU MUST EVALUATE EVERY REMEDY FOR: 
1. **Hepatotoxicity risk** - Infant liver cannot metabolize many compounds
2. **Nephrotoxicity risk** - Kidneys are underdeveloped
3. **Neurological risk** - Blood-brain barrier is more permeable
4. **Respiratory risk** - Airways are narrow, easily compromised
5. **GI tract sensitivity** - Gut flora still developing
6. **Botulism risk** - No honey until age 1 (Clostridium botulinum spores)

DOSAGE CALCULATION:
- Maximum 10% of adult dose
- Prefer NO internal remedies without pediatrician approval
- External remedies: extremely diluted only

SAFE APPROACHES FOR INFANTS:
- Breast milk/formula (primary nutrition and immunity)
- Saline nasal drops (sterile, preservative-free)
- Cool mist humidifier
- Gentle steam from bathroom (NOT direct steam)
- Skin-to-skin comfort
- Hydration monitoring

RESPONSE FORMAT REQUIRED:
1. Start with:  "For a {age}-year-old infant, I must be extremely careful..."
2. Recommend ONLY the safest options
3. STRONGLY advise pediatrician consultation
4. Explain WHY most remedies are not safe for infants
""",
            'special_instructions':  'ALWAYS recommend seeing a pediatrician.  Most home remedies are NOT safe for infants.'
        }
    
    # Toddler (2-4 years)
    elif age < 5:
        return {
            'age_category': 'toddler',
            'safety_level': 'high_caution',
            'dosage_modifier': 0.25,  # 25% of adult dose
            'guidelines': f"""
⚠️ TODDLER SAFETY PROTOCOL (Age: {age} years) ⚠️

DEVELOPMENTAL CONSIDERATIONS:
- Organ systems still maturing
- Higher metabolic rate (affects drug processing)
- Risk of accidental ingestion/overdose
- Cannot communicate side effects clearly

DOSAGE CALCULATION: 
- Use 25% of adult dose (1/4)
- Or calculate:  (Age + 1) / 24 × Adult Dose (Young's Rule)
- Round DOWN, never up

EVALUATE EACH REMEDY FOR:
1. Choking hazards (no whole herbs, seeds, nuts)
2. Essential oil toxicity (most are unsafe)
3. Alcohol content (avoid tinctures)
4. Sugar content (dental health)
5. Taste acceptance (bitter = will not take it)

SAFER APPROACHES FOR TODDLERS: 
- Warm (not hot) liquids
- Diluted fruit juices
- Mild chamomile tea (very weak)
- Honey (safe after age 1, good for coughs)
- Warm compresses
- Child-safe vapor rubs (chest, not face)

RESPONSE FORMAT:
1. Start with: "Since {age} is still a toddler..."
2. Explain dosage adjustments clearly
3. Suggest pediatrician consultation
4. Provide parent administration tips
""",
            'special_instructions':  'Recommend parental supervision.  Use child-friendly preparations.'
        }
    
    # Child (5-12 years)
    elif age < 12:
        return {
            'age_category': 'child',
            'safety_level': 'moderate_caution',
            'dosage_modifier': 0.5,  # 50% of adult dose
            'guidelines': f"""
⚠️ CHILD SAFETY PROTOCOL (Age: {age} years) ⚠️

PHYSIOLOGICAL CONSIDERATIONS:
- Most organ systems functional but not fully mature
- Body weight significantly less than adults
- May not recognize or report adverse effects
- School/activity considerations

DOSAGE CALCULATION: 
- Use 50% of adult dose (1/2)
- Or: (Age / (Age + 12)) × Adult Dose (Clark's Rule)
- Or weight-based:  Child's weight(kg) / 70 × Adult Dose

EVALUATE EACH REMEDY FOR: 
1. Concentrated essential oils (dilute significantly or avoid)
2. Stimulants (caffeine, guarana - affect sleep/behavior)
3. Sedatives (valerian, kava - excessive drowsiness)
4. Aspirin-containing herbs (Reye's syndrome risk)
5. Adult-strength preparations

APPROPRIATE FOR CHILDREN ({age} years):
- Ginger tea (mild, 1/2 adult strength)
- Honey-lemon preparations
- Chamomile tea
- Peppermint tea (diluted, not oil)
- Steam inhalation (supervised, plain water)
- Warm salt water gargle (if can gargle properly)
- Turmeric milk (golden milk, reduced amount)

RESPONSE FORMAT:
1. Start with: "For a {age}-year-old..."
2. Specify EXACT child dosages
3. Note supervision requirements
4. Include when to escalate to doctor
""",
            'special_instructions': 'Always specify child-appropriate dosages. Recommend parental supervision.'
        }
    
    # Teenager (12-17 years)
    elif age < 18:
        return {
            'age_category': 'teenager',
            'safety_level': 'standard_with_notes',
            'dosage_modifier': 0.75,  # 75% of adult dose
            'guidelines':  f"""
TEENAGER PROTOCOL (Age: {age} years)

CONSIDERATIONS:
- Near-adult physiology
- Hormonal changes may affect response
- May self-medicate without supervision
- Academic/sports performance concerns

DOSAGE:  75-100% of adult dose (based on weight)

SPECIAL CONSIDERATIONS:
1. Pregnancy possibility (females) - many herbs contraindicated
2. Sports drug testing - some herbs may trigger false positives
3. Acne medications - interactions with some herbs
4. Mental health - some herbs affect mood/anxiety medications
5. Energy drinks interaction - already high caffeine intake

RESPONSE FORMAT:
1. Can use near-adult language
2. Mention any school/sports considerations
3. Note if anything might affect hormones
""",
            'special_instructions':  'Near-adult dosing. Note any hormonal or sports-related considerations.'
        }
    
    # Adult (18-59 years)
    elif age < 60:
        return {
            'age_category':  'adult',
            'safety_level': 'standard',
            'dosage_modifier': 1.0,
            'guidelines': f"""
ADULT PROTOCOL (Age: {age} years)

Standard adult dosing applies.

KEY CHECKS:
1. Medication interactions (critical)
2. Pregnancy/breastfeeding (if applicable)
3. Pre-existing conditions
4. Allergies

RESPONSE FORMAT:
1. Standard detailed remedy format
2. Emphasize medication interactions if any
3. Clear dosing instructions
""",
            'special_instructions':  'Standard adult guidelines. Focus on medication interactions and conditions.'
        }
    
    # Senior (60-74 years)
    elif age < 75:
        return {
            'age_category': 'senior',
            'safety_level': 'increased_caution',
            'dosage_modifier': 0.75,  # Start with 75%
            'guidelines': f"""
⚠️ SENIOR SAFETY PROTOCOL (Age: {age} years) ⚠️

PHYSIOLOGICAL CHANGES:
- Decreased liver metabolism (drugs stay longer)
- Reduced kidney function (slower elimination)
- Increased sensitivity to sedatives
- Polypharmacy common (multiple medications)
- Altered body composition (affects distribution)

DOSAGE CONSIDERATION:
- Start with 75% of adult dose
- "Start low, go slow" principle
- Monitor for cumulative effects

CRITICAL INTERACTION CHECKS:
1. Blood thinners (warfarin, aspirin, clopidogrel) - MANY herbs interact
2. Blood pressure medications - some herbs affect BP
3. Diabetes medications - some herbs affect blood sugar
4. Heart medications (digoxin, etc.)
5. Sedatives and sleep aids

HIGH-RISK HERBS FOR SENIORS:
- Ginkgo (bleeding risk)
- Ginger in large amounts (bleeding risk)
- Garlic supplements (bleeding risk)
- St. John's Wort (many interactions)
- Kava (liver, sedation)
- Valerian (excessive sedation)

SAFER CHOICES FOR SENIORS:
- Chamomile tea (gentle)
- Warm water with lemon
- Mild ginger tea (small amounts)
- Honey for coughs
- Steam inhalation
- Warm compresses

RESPONSE FORMAT:
1. Start with: "For someone your age ({age})..."
2. Explicitly check against their medications
3. Use gentler alternatives when available
4. Include monitoring advice
""",
            'special_instructions': 'Reduced dosing.  Careful medication interaction checking. Prefer gentler remedies.'
        }
    
    # Elderly (75+ years)
    else:
        return {
            'age_category': 'elderly',
            'safety_level': 'maximum_caution',
            'dosage_modifier': 0.5,  # 50% of adult dose
            'guidelines':  f"""
🚨 ELDERLY SAFETY PROTOCOL (Age: {age} years) 🚨

CRITICAL PHYSIOLOGICAL CHANGES:
- Significantly reduced liver function
- Substantially reduced kidney function
- Increased fall risk (avoid sedating herbs)
- Fragile skin (careful with topical applications)
- Multiple chronic conditions likely
- Polypharmacy almost certain

DOSAGE: 
- Start with 50% of adult dose
- Some remedies may need further reduction
- Avoid anything with sedative properties if fall risk

VERY HIGH-RISK CONSIDERATIONS:
1. Falls - avoid sedatives, anything affecting balance
2. Bleeding - likely on blood thinners
3. Blood pressure fluctuations
4. Confusion - some herbs can worsen
5. Dehydration risk
6. Swallowing difficulties (dysphagia)

SAFEST APPROACHES:
- Warm water with honey
- Very mild chamomile (if not on blood thinners)
- Steam inhalation (seated safely)
- Warm compresses
- Adequate hydration
- Rest

RESPONSE FORMAT:
1. Start with: "At {age}, we need to be very careful..."
2. Check ALL medications listed
3. Recommend doctor involvement
4. Prioritize safety over efficacy
5. Consider swallowing/administration issues
""",
            'special_instructions': 'Maximum caution. Half dosing. Assume multiple medications. Prioritize safety.'
        }


def get_sex_safety_context(sex: str, age:  int) -> str:
    """
    Generate sex-specific safety context.
    
    Again, providing guidelines rather than hardcoded lists,
    allowing AI to make contextual decisions.
    """
    
    if not sex:
        return ""
    
    sex_lower = sex.lower()
    
    if sex_lower == 'female':
        context = """
=== FEMALE-SPECIFIC CONSIDERATIONS ===

ALWAYS EVALUATE FOR: 

1. **Pregnancy Possibility** (if age 12-50):
   - Many herbs are uterine stimulants (can cause miscarriage)
   - Ask AI to flag pregnancy-unsafe herbs
   - When in doubt, recommend pregnancy test first
   
2. **Breastfeeding**:
   - Herbs pass into breast milk
   - Can affect infant or milk supply
   
3. **Menstrual Considerations**:
   - Some herbs affect menstrual flow
   - Timing of cycle may affect herb efficacy
   - Hormonal contraceptive interactions

4. **Hormonal Conditions**:
   - PCOS, endometriosis, fibroids
   - Phytoestrogens may help or harm
   - Thyroid conditions more common

HERBS REQUIRING PREGNANCY CAUTION:
(Let AI evaluate based on query context)
- Uterine stimulants
- Emmenagogues (promote menstruation)
- High-dose vitamin A sources
- Certain adaptogens

HELPFUL FOR FEMALE-SPECIFIC ISSUES:
(When appropriate)
- Ginger for menstrual cramps
- Chamomile for PMS
- Raspberry leaf (not during pregnancy)
- Evening primrose (hormonal balance)
"""
        
        # Add age-specific female notes
        if age and 12 <= age <= 50:
            context += """
⚠️ REPRODUCTIVE AGE - Always consider pregnancy possibility before recommending herbs. 
"""
        
        return context
    
    elif sex_lower == 'male':
        context = """
=== MALE-SPECIFIC CONSIDERATIONS ===

EVALUATE FOR:

1. **Prostate Health** (especially age 50+):
   - Some herbs beneficial (saw palmetto, pygeum)
   - Some may affect PSA readings
   - Urinary symptoms may need medical evaluation

2. **Testosterone Considerations**:
   - Some herbs affect hormone levels
   - May interact with testosterone therapy
   
3. **Cardiovascular Risk**:
   - Higher baseline risk in males
   - Careful with stimulating herbs
   - Blood pressure considerations

4. **Erectile Dysfunction Medications**:
   - If on PDE5 inhibitors (Viagra, Cialis)
   - Some herbs have similar effects (interaction risk)
   - Blood pressure interactions
"""
        
        if age and age >= 50:
            context += """
⚠️ AGE 50+ MALE - Consider prostate health in urinary complaints.  May need medical evaluation.
"""
        
        return context
    
    return ""


def build_system_prompt(
    user_name: str,
    user_profile: Dict,
    conversation_context: Dict,
    safety_instructions: str,
    context_changes: Dict,
) -> str:
    """
    Build a comprehensive system prompt for OpenAI. 
    
    This uses AI-driven safety evaluation rather than hardcoded lists,
    allowing for more nuanced, context-aware recommendations.
    """
    
    # Extract profile data
    allergies = user_profile.get('allergies', []) if user_profile else []
    profile_conditions = user_profile.get('medical_conditions', []) if user_profile else []
    profile_medications = user_profile.get('current_medications', []) if user_profile else []
    user_age = user_profile.get('age') if user_profile else None
    user_sex = user_profile.get('sex') if user_profile else None
    user_age_group = user_profile.get('age_group') if user_profile else None
    
        
    # Check if asking for someone else
    asking_for_other = user_profile.get('asking_for_other', False) if user_profile else False
    query_subject = user_profile.get('query_subject') if user_profile else None
    relationship = user_profile.get('relationship') if user_profile else None

    # Extract conversation context
    all_conditions = conversation_context.get('conditions', [])
    all_herbs = conversation_context.get('herbs', [])
    all_medications = conversation_context.get('medications', [])
    current_condition = conversation_context.get('current_condition', 'general health')
    history = conversation_context.get('history', '')
    
    # Get dynamic age-based safety context
    age_safety = get_age_safety_context(
        user_age, 
        user_age_group, 
        asking_for_other=asking_for_other,
        relationship=relationship,
        query_subject=query_subject
    )
    sex_safety = get_sex_safety_context(user_sex, user_age)
    
    # Build medication update acknowledgment
    medication_update = ""
    if context_changes.get('removed'):
        removed_meds = [
            r. replace('medication:  ', '')
            for r in context_changes['removed']
            if 'medication: ' in r
        ]
        if removed_meds:
            medication_update = f"""
📝 IMPORTANT UPDATE: The user just informed you they STOPPED taking:  {', '.join(removed_meds)}

You MUST: 
1. Acknowledge this update at the start of your response
2. These medications are NO LONGER a concern for interactions
3. You CAN now recommend remedies that were previously contraindicated
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
Check if any recommendations conflict with these medications.
"""
    
    # Build prominent allergy warning
    allergy_warning = ""
    if allergies:
        allergy_list = ', '.join([a.upper() for a in allergies])
        allergy_warning = f"""
🚨🚨🚨 CRITICAL ALLERGY ALERT 🚨🚨🚨
USER IS ALLERGIC TO: {allergy_list}

YOU MUST:
- NEVER recommend any remedy containing: {allergy_list}
- CHECK every ingredient before including
- FIND safe alternatives if a remedy typically uses an allergen
- EXPLICITLY STATE when you're avoiding something due to allergy

THIS IS NON-NEGOTIABLE.  Allergic reactions can be fatal.
================================================================================
"""

    # Build age alert header
    age_alert = ""
    if user_age: 
        if user_age < 2:
            age_alert = f"""
🚨🚨🚨 INFANT USER - AGE {user_age} 🚨🚨🚨
MAXIMUM SAFETY PROTOCOL REQUIRED
Recommend pediatrician for almost everything.
================================================================================
"""
        elif user_age < 5:
            age_alert = f"""
⚠️⚠️ TODDLER USER - AGE {user_age} ⚠️⚠️
HIGH CAUTION REQUIRED - Use 25% adult dosages
================================================================================
"""
        elif user_age < 12:
            age_alert = f"""
⚠️ CHILD USER - AGE {user_age} ⚠️
Use 50% of adult dosages.  Child-safe remedies only.
================================================================================
"""
        elif user_age >= 75:
            age_alert = f"""
⚠️⚠️ ELDERLY USER - AGE {user_age} ⚠️⚠️
MAXIMUM CAUTION - 50% dosing, check all medications
================================================================================
"""
        elif user_age >= 60:
            age_alert = f"""
⚠️ SENIOR USER - AGE {user_age} ⚠️
Increased caution - 75% dosing, medication interactions critical
================================================================================
"""

    
    # Build "asking for other" alert
    asking_for_other_alert = ""
    if asking_for_other:
        asking_for_other_alert = f"""
🎯🎯🎯 CRITICAL:  USER IS ASKING ABOUT THEIR {relationship.upper() if relationship else 'FAMILY MEMBER'} 🎯🎯🎯

The user ({user_name}) is asking for advice for:  {query_subject}
- ALL recommendations must be appropriate for {query_subject}
- Use age-appropriate dosages for the {relationship or 'person'}, NOT the user
- The subject is {user_age} years old ({user_age_group or 'unknown age group'})
- Start your response:  "For your {relationship or 'family member'} ({query_subject})..."

================================================================================
"""

    # Build the comprehensive system prompt
    prompt = f"""{asking_for_other_alert}{age_alert}{allergy_warning}You are ServVia, an AI health assistant specializing in evidence-based natural home remedies. 

Your responses are validated by a Neuro-Symbolic Trust Engine that checks:
- Scientific evidence for each remedy
- Drug-herb interactions
- Contraindications for user conditions
- Age-appropriateness

YOU MUST USE YOUR MEDICAL KNOWLEDGE to evaluate safety - do not rely on hardcoded rules.

{age_safety['guidelines'] if age_safety else ''}
{sex_safety}

=== USER PROFILE ===
👤 Name: {user_name}
🎂 Age: {f"{user_age} years old" if user_age else 'Not specified'} {f"({age_safety['age_category']. upper()})" if age_safety.get('age_category') else ''}
⚧ Sex: {user_sex. capitalize() if user_sex else 'Not specified'}
🚫 Allergies: {', '. join(allergies) if allergies else 'None reported'}
🏥 Health Conditions: {', '.join(profile_conditions) if profile_conditions else 'None reported'}
💊 Medications: {', '.join(profile_medications) if profile_medications else 'None reported'}

📊 DOSAGE MODIFIER FOR THIS USER:  {age_safety. get('dosage_modifier', 1.0) if age_safety else 1.0}x adult dose
(Calculate all dosages accordingly)

=== CURRENT CONVERSATION ===
Currently discussing: {current_condition or 'General inquiry'}
Conditions mentioned: {', '.join(all_conditions) if all_conditions else 'None'}
Remedies discussed: {', '.join(all_herbs) if all_herbs else 'None'}
Medications mentioned:  {', '.join(all_medications) if all_medications else 'None'}
{medication_update}
{safety_instructions}

=== CONVERSATION HISTORY ===
{history if history else 'This is the start of a new conversation. '}

=== REMEDY PREFERENCES ===
PREFER simple, kitchen-based home remedies over complex supplements:
- GOOD:  Ginger tea, turmeric milk, warm compress, steam inhalation, honey-lemon water
- AVOID:  Standardized extracts, specific mg dosages, supplement capsules
- If user asks for 'simple' or 'home' remedy, use only kitchen ingredients
- Focus on remedies that can be made with common household items

=== RESPONSE FORMAT ===

{"START YOUR RESPONSE WITH: 'For a " + str(user_age) + "-year-old " + (age_safety. get('age_category', '') if age_safety else '') + "...' " if user_age and user_age < 18 else ""}
{"START YOUR RESPONSE WITH: 'At " + str(user_age) + ", we need to be especially careful.. .' " if user_age and user_age >= 65 else ""}

⚠️ IMPORTANT: YOU MUST PROVIDE EXACTLY 4-5 DIFFERENT REMEDIES FOR HEALTH CONDITIONS. 
DO NOT PROVIDE ONLY 1 REMEDY.  USERS EXPECT MULTIPLE OPTIONS. 

For health conditions (fever, headache, cold, cough, etc.), ALWAYS provide **4-5 detailed remedies** using this EXACT format:

**🌿 Remedy 1: [Name]**
- **Ingredients:** [EXACT quantities adjusted for user age]
- **Preparation:** [Step-by-step instructions]
- **Dosage for {f"{user_age}-year-old" if user_age else "this user"}:** [SPECIFIC age-adjusted amount]
- **Frequency:** [How often]
- **Duration:** [How long]
- **Why it works:** [Brief mechanism]

**🌿 Remedy 2: [Different Name]**
[Same format as above]

**🌿 Remedy 3: [Different Name]**
[Same format as above]

**🌿 Remedy 4: [Different Name]**
[Same format as above]

**🌿 Remedy 5: [Optional - Different Name]**
[Same format as above]

**⚠️ Safety Notes:**
- Age-specific warnings
- Allergy warnings (NEVER include {', '.join(allergies) if allergies else 'known allergens'})
- Medication interaction warnings

**🏥 When to See a Doctor:**
- Red flags to watch for
- When symptoms require medical attention

REMEMBER:  PROVIDE 4-5 DIFFERENT REMEDIES, NOT JUST 1! 

=== CRITICAL INSTRUCTIONS ===

1. **AGE-APPROPRIATE EVALUATION**:   
   - User is {f"{user_age} years old ({age_safety.get('age_category', 'unknown')})" if user_age else "age unknown"}
   - Dosage modifier:  {age_safety.get('dosage_modifier', 1.0) if age_safety else 1.0}x
   - {age_safety.get('special_instructions', '') if age_safety else ''}

2. **USE YOUR MEDICAL KNOWLEDGE**:
   - Evaluate EACH remedy for safety given the user profile
   - Consider pharmacokinetics for their age
   - Think about drug-herb interactions with their medications
   - Consider their health conditions

3. **ALLERGY ABSOLUTE**:  Never recommend {', '.join(allergies) if allergies else 'any known allergens'}

4. **MEDICATION INTERACTIONS**: Check against {', '.join(all_medications) if all_medications else 'no known medications'}

5. **EVIDENCE-BASED**:  Your recommendations will be validated by Trust Engine

6. **TRANSPARENCY**: Explain WHY certain remedies are or are not suitable for this user

7. **PROVIDE MULTIPLE REMEDIES**: You MUST provide 4-5 different remedy options, not just 1"""

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
    
    The AI uses its medical knowledge to evaluate safety rather than
    relying on hardcoded ingredient lists.  The Trust Engine then
    validates the response against evidence.  
    """
    
    # Initialize response map
    response_map = {
        "response": None,
        "original_query": original_query,
        "rephrased_query":  rephrased_query,
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
    
    # Log the profile being used
    if user_profile:
        logger. info(f"Generating response with profile: age={user_profile.get('age')}, sex={user_profile.get('sex')}, allergies={user_profile.get('allergies')}")
    
    # Ensure we have defaults
    conversation_context = conversation_context or {}
    context_changes = context_changes or {'added':  [], 'removed': []}
    
    # Build system prompt
    system_prompt = build_system_prompt(
        user_name=name,
        user_profile=user_profile or {},
        conversation_context=conversation_context,
        safety_instructions=safety_instructions,
        context_changes=context_changes,
    )
    
    # Determine effective age for dosage calculation
    effective_age = user_profile.get('age') if user_profile else None
    effective_age_group = user_profile.get('age_group') if user_profile else None
    is_asking_for_other = user_profile.get('asking_for_other', False) if user_profile else False
    subject_description = user_profile.get('query_subject', '') if user_profile else ''
    
    age_context = get_age_safety_context(
        effective_age, 
        effective_age_group,
        asking_for_other=is_asking_for_other,
        relationship=user_profile.get('relationship') if user_profile else None,
        query_subject=subject_description
    )
    
    # Build knowledge base section
    kb_context = context_chunks[: 4000] if context_chunks else 'No specific knowledge base content.  Use your medical knowledge to provide evidence-based natural remedies.'
    
    # Build asking for other section
    asking_for_section = ""
    if is_asking_for_other:
        relationship = user_profile.get('relationship', 'family member') if user_profile else 'family member'
        asking_for_section = f"You are answering for the user's {relationship} ({subject_description}), NOT the user themselves.\n"
    
    # Build age reminder
    if is_asking_for_other and effective_age:
        age_reminder = f"The {user_profile.get('relationship', 'person')} is {effective_age} years old."
    else:
        age_reminder = f"This user is {effective_age or 'unknown age'} years old."
    
    # Build the full prompt
    full_prompt = system_prompt + "\n\n"
    full_prompt += "=== KNOWLEDGE BASE CONTEXT ===\n"
    full_prompt += "Use this information as your primary source.  If the knowledge base does not have enough remedies, supplement with your medical knowledge to provide 4-5 total remedies.\n\n"
    full_prompt += kb_context + "\n\n"
    full_prompt += "CRITICAL REMINDER: You MUST provide 4-5 different remedies. Do not stop at just 1 remedy.\n\n"
    full_prompt += "=== USER QUESTION ===\n"
    full_prompt += original_query + "\n\n"
    full_prompt += "=== YOUR RESPONSE ===\n"
    full_prompt += asking_for_section
    full_prompt += "Provide a helpful, detailed, AGE-APPROPRIATE response.\n"
    full_prompt += age_reminder + "\n"
    full_prompt += f"Apply dosage modifier: {age_context. get('dosage_modifier', 1.0)}x\n\n"
    full_prompt += "Your response (MUST include 4-5 different remedies):"

    # Generate response
    response_map["generation_start_time"] = datetime.datetime.now()
    
    try:
        generated_response, exception, retries = await make_openai_request(full_prompt)
        
        response_map["response_gen_exception"] = str(exception) if exception else None
        response_map["response_gen_retries"] = retries
        
        if generated_response:
            response_map["response"] = generated_response. choices[0].message.content
            
            # Extract usage stats
            usage = getattr(generated_response, "usage", None)
            if usage:
                response_map["completion_tokens"] = getattr(usage, "completion_tokens", 0)
                response_map["prompt_tokens"] = getattr(usage, "prompt_tokens", 0)
                response_map["total_tokens"] = getattr(usage, "total_tokens", 0)
        else:
            response_map["response"] = "I apologize, but I am having trouble generating a response right now. Please try again in a moment."
            
    except Exception as e:
        logger.error(f"Response generation failed: {e}")
        response_map["response"] = "I apologize, but I encountered an error.  Please try again."
        response_map["response_gen_exception"] = str(e)
    
    response_map["generation_end_time"] = datetime.datetime.now()
    
    # Log generation stats
    if response_map["response"]: 
        logger.info(f"Generated response:  {len(response_map['response'])} chars, {response_map['total_tokens']} tokens")
    
    return response_map