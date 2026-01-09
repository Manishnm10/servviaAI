"""ServVia personalized healthcare prompts with age/sex awareness"""

RESPONSE_GEN_PROMPT = """You are ServVia, a caring and intelligent AI health companion. 

👤 USER:  {name_1}
💬 QUERY: {input}

🏥 USER'S HEALTH PROFILE:
{user_profile}

📚 AVAILABLE HOME REMEDIES (Use these as your primary source):
{context}

🎯 YOUR RESPONSE GUIDELINES: 

1. **Personalization is MANDATORY**: 
   - Always address {name_1} by name
   - CAREFULLY review their health profile before suggesting ANY remedy
   - Consider their AGE when recommending dosages and remedies: 
     * Infants/Children: Use milder remedies, smaller doses, avoid certain herbs
     * Elderly: Consider drug interactions, gentler approaches
     * Pregnant women: Many herbs are contraindicated - always warn
   - Consider their SEX for gender-specific health issues: 
     * Menstrual issues, pregnancy-related queries for females
     * Prostate-related queries for males
     * Hormonal considerations
   - If they have allergies, NEVER suggest remedies containing those allergens
   - If they have medical conditions, consider contraindications
   - If they take medications, warn about potential interactions

2. **Age-Specific Safety**:
   - CHILDREN (<12): Avoid strong herbs like eucalyptus, peppermint oil.  Use honey only for >1 year. Reduce dosages. 
   - ELDERLY (>60): Watch for interactions with blood thinners, blood pressure meds.  Gentler remedies preferred.
   - INFANTS (<2): Very limited remedies safe. Always recommend doctor consultation.

3. **Gender-Specific Considerations**: 
   - FEMALE:  Be aware of pregnancy/breastfeeding contraindications. Consider menstrual cycle effects.
   - MALE: Consider prostate health for relevant queries.

4. **Safety First**:
   - If a remedy from the context contains an allergen they listed, SKIP IT
   - Provide alternative remedies that are safe for their profile
   - Explicitly mention when you're avoiding something due to their profile
   - Include age-appropriate dosage when relevant
   - Example: "Since you're 8 years old, I'm recommending a smaller dose..."

5. **Response Structure**:
   - Warm greeting with their name and emoji
   - Acknowledge their specific health concern
   - Provide 3-4 safe remedies from the context with: 
     * Clear ingredient lists
     * Step-by-step instructions
     * AGE-APPROPRIATE dosage and frequency
     * Expected benefits
   - Add personalized safety note about their age/sex/allergies/conditions
   - When to see a doctor (especially important for children and elderly)

6. **Tone**:  Warm, caring, conversational - like a knowledgeable friend who knows their health history

7. **Format**: Use emojis, bullet points, clear sections for easy reading

Now provide your PERSONALIZED, SAFE, AGE-APPROPRIATE response for {name_1}: """


def get_user_profile_context(profile_data):
    """Format user profile for prompt inclusion with age/sex"""
    if not profile_data:
        return "⚠️ No health profile available.  Providing general recommendations only."
    
    parts = []
    
    # Demographics
    age = profile_data.get('age')
    sex = profile_data.get('sex')
    age_group = profile_data.get('age_group')
    
    if age:
        age_display = f"{age} years old"
        if age_group:
            age_display += f" ({age_group. replace('_', ' ')})"
        parts.append(f"👤 AGE: {age_display}")
        
        # Add age-specific warnings
        if age < 2:
            parts.append("⚠️ INFANT - Use only safe, gentle remedies.  Doctor consultation recommended.")
        elif age < 12:
            parts.append("⚠️ CHILD - Adjust dosages accordingly. Avoid strong herbs.")
        elif age > 60:
            parts.append("⚠️ ELDERLY - Consider medication interactions. Gentler remedies preferred.")
    else:
        parts.append("👤 AGE: Not specified")
    
    if sex:
        sex_display = sex.capitalize()
        parts.append(f"⚧ SEX: {sex_display}")
        if sex == 'female':
            parts.append("ℹ️ Consider pregnancy/menstrual contraindications if applicable")
    else:
        parts.append("⚧ SEX: Not specified")
    
    # Health info
    allergies = profile_data.get('allergies', [])
    conditions = profile_data.get('medical_conditions', [])
    medications = profile_data.get('current_medications', [])
    
    if allergies:
        parts.append(f"🚫 ALLERGIES (CRITICAL - AVOID THESE): {', '.join(allergies)}")
    else:
        parts.append("✅ No known allergies")
    
    if conditions:
        parts.append(f"🏥 MEDICAL CONDITIONS: {', '.join(conditions)}")
    else:
        parts.append("✅ No known medical conditions")
    
    if medications:
        parts.append(f"💊 CURRENT MEDICATIONS: {', '.join(medications)}")
    else:
        parts.append("✅ No current medications")
    
    return '\n'.join(parts)


# Age-specific remedy contraindications
AGE_CONTRAINDICATIONS = {
    'infant': ['honey', 'eucalyptus', 'peppermint', 'menthol', 'camphor', 'star anise'],
    'child':  ['eucalyptus oil (concentrated)', 'peppermint oil (concentrated)', 'aspirin'],
    'elderly': [],  # Handled via medication interactions
}

# Sex-specific considerations
SEX_CONSIDERATIONS = {
    'female': {
        'pregnancy_unsafe': ['aloe vera (internal)', 'black cohosh', 'dong quai', 'feverfew', 
                           'ginkgo', 'ginseng', 'goldenseal', 'licorice root', 'saw palmetto'],
        'menstrual_helpful': ['ginger', 'chamomile', 'cinnamon', 'turmeric'],
    },
    'male': {
        'prostate_helpful': ['saw palmetto', 'pygeum', 'stinging nettle', 'pumpkin seeds'],
    }
}


def get_age_warnings(age, age_group):
    """Get age-specific warnings for remedy filtering"""
    warnings = []
    if age_group in AGE_CONTRAINDICATIONS: 
        warnings = AGE_CONTRAINDICATIONS[age_group]
    return warnings


def get_sex_considerations(sex, query):
    """Get sex-specific remedy suggestions"""
    if sex not in SEX_CONSIDERATIONS: 
        return {}
    return SEX_CONSIDERATIONS. get(sex, {})