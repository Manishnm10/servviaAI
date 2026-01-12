"""
ServVia 2.0 - Agentic RAG Pipeline (Production Ready)
======================================================
Intelligent health assistant pipeline with:
- Contextual conversation memory
- Drug-herb interaction safety
- Evidence-based verification
- Chronobiological recommendations

Author: ServVia Team
Version: 2.0. 0
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from generation.generate_response import generate_query_response
from rag_service.content_retrieval import retrieve_content
from rag_service.query_rephrase import rephrase_query

logger = logging. getLogger(__name__)

# Import conversation manager
try:
    from servvia2. conversation. manager import conversation_manager
    CONVERSATION_ENABLED = True
except ImportError:
    conversation_manager = None
    CONVERSATION_ENABLED = False
    logger.warning("Conversation manager not available")


# =============================================================================
# EMERGENCY DETECTION SYSTEM
# =============================================================================

EMERGENCY_RESPONSES = {
    'cardiac_arrest': """🚨 **EMERGENCY - CARDIAC ARREST / NOT BREATHING**

**CALL 112 (India) / 911 (US) / 999 (UK) IMMEDIATELY**

**CPR Steps (Hands-Only for untrained):**

1. **CHECK** - Tap shoulders firmly, shout "Are you OK?"
2. **CALL** - If no response, call emergency services immediately
3. **PUSH** - Start chest compressions:
   - Place heel of hand on center of chest
   - Push hard and fast (at least 2 inches deep)
   - Rate: 100-120 compressions per minute
   - Allow full chest recoil between compressions

4. **If trained in CPR:**
   - After 30 compressions, give 2 rescue breaths
   - Tilt head back, lift chin, pinch nose
   - Breathe into mouth until chest rises

5. **CONTINUE** until help arrives or person responds

**🔴 This is a life-threatening emergency. Every second counts.**""",

    'choking': """🚨 **EMERGENCY - CHOKING**

**CALL 112 (India) / 911 (US) / 999 (UK)**

**For ADULTS - Heimlich Maneuver:**

1. Stand behind the person
2. Make a fist with one hand
3. Place fist just above the belly button
4. Grasp fist with other hand
5. Give quick, upward thrusts
6.  Repeat until object is expelled

**For INFANTS (under 1 year):**
1. Place face-down on your forearm
2. Give 5 back blows between shoulder blades
3. Turn over, give 5 chest thrusts
4. Repeat until object comes out

**If person becomes unconscious, start CPR.**

**🔴 This is a life-threatening emergency.**""",

    'cardiac': """🚨 **EMERGENCY - POSSIBLE HEART ATTACK**

**CALL 112 (India) / 911 (US) / 999 (UK) IMMEDIATELY**

**While waiting for help:**

1. Have the person sit or lie in a comfortable position
2.  Loosen any tight clothing
3. If available and not allergic, give aspirin (325mg, chew don't swallow)
4. Stay calm and reassure the person
5. Be prepared to perform CPR if they become unresponsive
6. Do NOT let them walk or exert themselves

**Warning signs:**
- Chest pain or pressure
- Pain spreading to arm, jaw, or back
- Shortness of breath
- Cold sweat, nausea
- Lightheadedness

**🔴 Do NOT drive yourself to the hospital. Wait for ambulance.**""",

    'stroke': """🚨 **EMERGENCY - POSSIBLE STROKE**

**CALL 112 (India) / 911 (US) / 999 (UK) IMMEDIATELY**

**Remember F.A.S. T. :**

- **F**ace: Ask them to smile.  Does one side droop?
- **A**rms: Ask them to raise both arms. Does one drift down?
- **S**peech: Ask them to repeat a phrase. Is it slurred? 
- **T**ime: If ANY of these signs, call emergency immediately! 

**While waiting:**
1. Note the TIME symptoms started (critical for treatment)
2. Keep them calm and lying down
3. Do NOT give food, water, or medication
4.  Loosen tight clothing
5. If unconscious, place in recovery position

**🔴 Time is brain.  Every minute matters.**""",

    'mental_health': """🚨 **You Are Not Alone - Help Is Available**

**Please reach out to someone right now:**

**Crisis Helplines:**
- 🇮🇳 India: iCall - 9152987821 | Vandrevala Foundation - 1860-2662-345
- 🇺🇸 USA: 988 (Suicide & Crisis Lifeline)
- 🇬🇧 UK: 116 123 (Samaritans)
- 🌍 International: findahelpline.com

**If you or someone is in immediate danger:**
Call 112 (India) / 911 (US) / 999 (UK)

**Remember:**
- This feeling is temporary
- You matter and your life has value
- Professional help works - millions have recovered
- Reaching out is a sign of strength, not weakness

**Please talk to someone.  We care about you.  💙**""",

    'poisoning': """🚨 **EMERGENCY - POISONING / OVERDOSE**

**CALL POISON CONTROL IMMEDIATELY:**
- 🇮🇳 India: 1800-11-6117 (AIIMS)
- 🇺🇸 USA: 1-800-222-1222
- 🇬🇧 UK: 111

**Do NOT:**
- Induce vomiting unless told to by poison control
- Give anything to eat or drink
- Wait for symptoms to appear

**Do:**
1. Call poison control immediately
2. Have the container/substance ready to describe
3. Know the person's age and weight
4. Note the time of exposure
5. If on skin, remove clothing and rinse with water
6. If in eyes, rinse with water for 15-20 minutes

**🔴 This is a medical emergency. Call immediately.**""",

    'allergic_reaction': """🚨 **EMERGENCY - SEVERE ALLERGIC REACTION (ANAPHYLAXIS)**

**CALL 112 (India) / 911 (US) / 999 (UK)**

**If person has an EpiPen:**
1. Remove blue safety cap
2. Press orange tip firmly into outer thigh
3.  Hold for 10 seconds
4.  Note the time

**While waiting for help:**
1.  Have person lie down with legs elevated
2.  Loosen tight clothing
3. If vomiting, turn on side
4. Stay with them constantly
5. Be ready to perform CPR

**Signs of anaphylaxis:**
- Difficulty breathing, wheezing
- Swelling of face, lips, tongue
- Rapid heartbeat
- Dizziness or fainting
- Hives or rash

**🔴 Anaphylaxis can be fatal within minutes. Call immediately.**""",

    'severe_bleeding': """🚨 **EMERGENCY - SEVERE BLEEDING**

**CALL 112 (India) / 911 (US) / 999 (UK)**

**Immediate steps:**

1. **Apply direct pressure** - Use clean cloth, press firmly
2. **Don't remove the cloth** - Add more layers on top if soaked
3. **Elevate** - Raise injured area above heart level if possible
4. **Apply pressure to pressure points** if direct pressure doesn't work
5. **Use tourniquet** only as last resort for life-threatening limb bleeding

**Do NOT:**
- Remove embedded objects
- Apply tourniquet unless trained and necessary
- Stop applying pressure to check the wound

**🔴 Call emergency services immediately for severe bleeding.**""",
}


def check_emergency(query: str) -> Optional[str]:
    """
    Check if query indicates an emergency situation. 
    Returns emergency type or None. 
    """
    query_lower = query. lower()
    
    emergency_keywords = {
        # Cardiac arrest / breathing
        'cardiac_arrest': ['cpr', 'not breathing', 'stopped breathing', 'no pulse', 'unconscious not breathing'],
        'choking': ['choking', 'cant breathe', "can't breathe", 'something stuck throat', 'heimlich'],
        'cardiac': ['heart attack', 'chest pain', 'chest pressure', 'heart pain'],
        'stroke': ['stroke', 'face drooping', 'arm weakness', 'slurred speech', 'sudden confusion'],
        'mental_health': ['suicide', 'kill myself', 'want to die', 'end my life', 'self harm', 'hurt myself'],
        'poisoning': ['poisoning', 'overdose', 'swallowed poison', 'took too many pills', 'drank bleach'],
        'allergic_reaction': ['anaphylaxis', 'allergic reaction severe', 'cant breathe allergy', 'throat closing'],
        'severe_bleeding': ['severe bleeding', 'wont stop bleeding', 'blood everywhere', 'arterial bleeding'],
    }
    
    for emergency_type, keywords in emergency_keywords.items():
        for keyword in keywords:
            if keyword in query_lower:
                return emergency_type
    
    return None


def get_emergency_response(emergency_type: str) -> str:
    """Get the appropriate emergency response"""
    return EMERGENCY_RESPONSES.get(
        emergency_type, 
        """🚨 **EMERGENCY DETECTED**

**CALL 112 (India) / 911 (US) / 999 (UK)**

Please describe the emergency to the dispatcher. 
Stay calm and follow their instructions.

**This is a medical emergency. Professional help is essential.**"""
    )


# =============================================================================
# DRUG-HERB INTERACTION DATABASE
# =============================================================================

INTERACTION_DATABASE = {
    'ginger': {
        'drugs': ['aspirin', 'ibuprofen', 'warfarin', 'blood thinner', 'coumadin', 'plavix', 'clopidogrel', 'anticoagulant'],
        'severity': 'HIGH',
        'reason': 'Ginger inhibits platelet aggregation (blood thinning effect).  Combined with anticoagulants, this significantly increases bleeding risk - bruising, prolonged bleeding from cuts, or internal bleeding.',
        'alternatives': ['Peppermint oil (topical)', 'Lavender aromatherapy', 'Cold compress', 'Chamomile tea'],
    },
    'turmeric': {
        'drugs': ['aspirin', 'warfarin', 'blood thinner', 'coumadin', 'metformin', 'diabetes medication', 'insulin'],
        'severity': 'HIGH',
        'reason': 'Curcumin has antiplatelet effects and can lower blood sugar. Risk of bleeding with anticoagulants and hypoglycemia with diabetes medications.',
        'alternatives': ['Boswellia (for inflammation)', 'Cold compress', 'Rest and elevation', 'Omega-3 foods'],
    },
    'garlic': {
        'drugs': ['aspirin', 'warfarin', 'blood thinner', 'hiv medication', 'saquinavir'],
        'severity': 'MODERATE',
        'reason': 'Garlic has blood-thinning properties. Use only small culinary amounts with blood thinners.',
        'alternatives': ['Onion (milder effect)', 'Oregano', 'Thyme'],
    },
    'ashwagandha': {
        'drugs': ['thyroid medication', 'levothyroxine', 'synthroid', 'sedative', 'benzodiazepine', 'immunosuppressant'],
        'severity': 'HIGH',
        'reason': 'Ashwagandha stimulates thyroid function and has sedative properties. May interfere with thyroid medication dosing and compound sedative effects.',
        'alternatives': ['Chamomile tea (for stress)', 'Lavender aromatherapy', 'Deep breathing exercises', 'Brahmi'],
    },
    'licorice': {
        'drugs': ['blood pressure medication', 'bp medicine', 'antihypertensive', 'diuretic', 'digoxin', 'heart medication'],
        'severity': 'HIGH',
        'reason': 'Glycyrrhizin in licorice raises blood pressure and depletes potassium.  Counteracts BP medications and can cause dangerous heart rhythms with digoxin.',
        'alternatives': ['Honey (for sore throat)', 'Slippery elm', 'Marshmallow root'],
    },
    'ginseng': {
        'drugs': ['warfarin', 'blood thinner', 'diabetes medication', 'metformin', 'insulin', 'antidepressant', 'maoi'],
        'severity': 'MODERATE',
        'reason': 'Ginseng affects blood clotting and blood sugar levels. Has stimulant properties that may interact with MAOIs.',
        'alternatives': ['Green tea (moderate amounts)', 'Peppermint tea', 'Amla'],
    },
    'st johns wort': {
        'drugs': ['antidepressant', 'ssri', 'birth control', 'contraceptive', 'hiv medication', 'immunosuppressant', 'warfarin'],
        'severity': 'CRITICAL',
        'reason': "St. John's Wort induces liver enzymes (CYP450), dramatically reducing effectiveness of many medications. Risk of serotonin syndrome with SSRIs.",
        'alternatives': ['Lavender', 'Chamomile', 'Exercise', 'Light therapy'],
    },
    'valerian': {
        'drugs': ['sedative', 'benzodiazepine', 'sleep medication', 'ambien', 'alcohol'],
        'severity': 'HIGH',
        'reason': 'Valerian has sedative effects that compound with other CNS depressants, risking over-sedation or respiratory depression.',
        'alternatives': ['Chamomile tea', 'Warm milk', 'Lavender aromatherapy', 'Sleep hygiene practices'],
    },
    'kava': {
        'drugs': ['alcohol', 'sedative', 'benzodiazepine', 'antidepressant', 'levodopa'],
        'severity': 'CRITICAL',
        'reason': 'Kava has significant hepatotoxicity risk and compounds with other sedatives. Can interfere with dopamine medications.',
        'alternatives': ['Chamomile', 'Passionflower', 'Lavender'],
    },
    'ginkgo': {
        'drugs': ['aspirin', 'warfarin', 'blood thinner', 'nsaid', 'ibuprofen'],
        'severity': 'HIGH',
        'reason': 'Ginkgo inhibits platelet activating factor, increasing bleeding risk with anticoagulants.',
        'alternatives': ['Brahmi (for cognitive support)', 'Green tea', 'Omega-3 fatty acids'],
    },
    'echinacea': {
        'drugs': ['immunosuppressant', 'cyclosporine', 'corticosteroid'],
        'severity': 'MODERATE',
        'reason': 'Echinacea stimulates the immune system, potentially counteracting immunosuppressive therapy.',
        'alternatives': ['Vitamin C foods', 'Zinc lozenges', 'Rest and hydration'],
    },
}


def check_interactions(herbs: List[str], medications: List[str]) -> List[Dict]:
    """
    Check for drug-herb interactions.
    Returns list of interaction warnings. 
    """
    warnings = []
    
    if not herbs or not medications:
        return warnings
    
    for herb in herbs:
        herb_lower = herb. lower(). strip()
        
        if herb_lower in INTERACTION_DATABASE:
            interaction_data = INTERACTION_DATABASE[herb_lower]
            
            for med in medications:
                med_lower = med.lower().strip()
                
                for dangerous_drug in interaction_data['drugs']:
                    if dangerous_drug in med_lower or med_lower in dangerous_drug:
                        warnings.append({
                            'herb': herb,
                            'medication': med,
                            'severity': interaction_data['severity'],
                            'reason': interaction_data['reason'],
                            'alternatives': interaction_data['alternatives'],
                        })
                        break  # Found match, move to next medication
    
    return warnings


# =============================================================================
# ENTITY EXTRACTION
# =============================================================================

def extract_entities(query: str) -> Dict[str, List[str]]: 
    """
    Extract health conditions, herbs, and medications from query. 
    """
    query_lower = query.lower()
    
    # Health conditions - EXPANDED LIST
    conditions = []
    condition_keywords = {
        'headache': ['headache', 'head hurts', 'head pain', 'head ache', 'migraine'],
        'fever': ['fever', 'temperature', 'feverish', 'high temperature'],
        'cold': ['cold', 'runny nose', 'sneezing', 'stuffy nose', 'congestion', 'common cold'],
        'cough':  ['cough', 'coughing', 'dry cough', 'wet cough'],
        'nausea': ['nausea', 'nauseous', 'feeling sick', 'queasy', 'want to vomit'],
        'indigestion': ['indigestion', 'bloating', 'gas', 'stomach upset', 'acidity', 'heartburn', 'acid reflux'],
        'sore throat': ['sore throat', 'sorethroat', 'throat pain', 'throat hurts', 'scratchy throat', 'painful throat'],
        'anxiety': ['anxiety', 'anxious', 'worried', 'nervous', 'panic'],
        'stress': ['stress', 'stressed', 'overwhelmed', 'tension'],
        'insomnia': ['insomnia', 'cant sleep', "can't sleep", 'trouble sleeping', 'sleepless', 'sleep problems'],
        'fatigue':  ['fatigue', 'tired', 'exhausted', 'no energy', 'weakness', 'low energy'],
        'joint pain': ['joint pain', 'arthritis', 'joints hurt', 'knee pain', 'joint ache', 'joint stiffness'],
        'back pain': ['back pain', 'backache', 'back hurts', 'lower back', 'upper back pain'],
        'toothache': ['toothache', 'tooth pain', 'tooth hurts', 'dental pain'],
        'acne': ['acne', 'pimples', 'breakout', 'zits', 'blemishes', 'skin breakout'],
        'constipation': ['constipation', 'constipated', 'cant poop', 'hard stool'],
        'diarrhea':  ['diarrhea', 'loose stools', 'upset stomach', 'watery stool'],
        'motion sickness': ['motion sickness', 'car sick', 'travel sickness', 'sea sick', 'nausea travel', 'carsick', 'seasick'],

        # NEW CONDITIONS ADDED
        'menstrual cramps':  ['menstrual cramps', 'period pain', 'period cramps', 'menstrual pain', 'dysmenorrhea', 'cramps period', 'monthly cramps'],
        'pms': ['pms', 'premenstrual', 'pre-menstrual', 'before period'],
        'muscle pain': ['muscle pain', 'muscle ache', 'sore muscles', 'muscle soreness', 'myalgia'],
        'inflammation': ['inflammation', 'swelling', 'inflamed'],
        'allergies': ['allergies', 'allergic', 'hay fever', 'seasonal allergies'],
        'skin rash': ['skin rash', 'rash', 'skin irritation', 'itchy skin', 'eczema', 'dermatitis'],
        'burns': ['burns', 'burn', 'burnt', 'scalded'],
        'cuts': ['cuts', 'wound', 'wounds', 'bleeding cut'],
        'bruises': ['bruises', 'bruise', 'bruising'],
        'eye strain': ['eye strain', 'tired eyes', 'eye fatigue', 'dry eyes'],
        'ear pain': ['ear pain', 'earache', 'ear infection'],
        'sinus': ['sinus', 'sinusitis', 'sinus pain', 'sinus pressure', 'blocked sinuses'],
        'asthma': ['asthma', 'wheezing', 'breathing difficulty', 'shortness of breath'],
        'high blood pressure': ['high blood pressure', 'hypertension', 'bp high'],
        'low blood pressure': ['low blood pressure', 'hypotension', 'bp low'],
        'diabetes': ['diabetes', 'blood sugar', 'diabetic', 'sugar levels'],
        'weight loss': ['weight loss', 'lose weight', 'fat loss', 'obesity'],
        'hair loss': ['hair loss', 'hair fall', 'balding', 'thinning hair'],
        'dandruff': ['dandruff', 'flaky scalp', 'scalp issues'],
        'bad breath': ['bad breath', 'halitosis', 'mouth odor'],
        'bloating': ['bloating', 'bloated', 'belly bloat', 'gas'],
        'heartburn': ['heartburn', 'acid reflux', 'gerd', 'reflux'],
        'ulcers': ['ulcers', 'stomach ulcer', 'mouth ulcer', 'peptic ulcer'],
        'uti': ['uti', 'urinary tract infection', 'burning urination', 'bladder infection'],
        'kidney stones': ['kidney stones', 'kidney pain', 'renal stones'],
        'liver health': ['liver', 'fatty liver', 'liver detox'],
        'immunity': ['immunity', 'immune system', 'weak immunity', 'boost immunity'],
        'energy': ['energy', 'low energy', 'fatigue', 'tiredness'],
        'memory': ['memory', 'forgetfulness', 'brain fog', 'concentration'],
        'depression': ['depression', 'depressed', 'feeling low', 'sad'],
        'motion sickness': ['motion sickness', 'travel sickness', 'nausea travel', 'car sickness'],
        'hangover': ['hangover', 'alcohol hangover', 'after drinking'],

        # Add these to the condition_keywords dictionary in extract_entities function: 

        'mouth injury': ['cut in mouth', 'cut on lip', 'cut on inner lip', 'bit my lip', 'bit my tongue', 'tongue cut', 'lip cut', 'mouth cut', 'bleeding lip', 'bleeding mouth'],
        'cold sore': ['cold sore', 'fever blister', 'herpes labialis', 'herpes on lip'],
        'wound': ['wound', 'cut', 'bleeding', 'injury', 'injured', 'hurt', 'punched', 'hit', 'bruise', 'bruised', 'laceration', 'gash'],
        'burns': ['burn', 'burnt', 'burned', 'scalded', 'scald'],
        'bleeding': ['bleeding', 'blood', 'bleed', 'hemorrhage'],
        'bruise': ['bruise', 'bruised', 'contusion', 'black eye', 'swelling from hit'],
      
    }
    
    for condition, keywords in condition_keywords.items():
        for keyword in keywords:
            if keyword in query_lower:
                if condition not in conditions:
                    conditions.append(condition)
                    # If we found a specific match (mouth injury), prioritize it
                    if condition == 'mouth injury':
                        conditions = [condition] + [c for c in conditions if c != condition]
                break
    
    # Herbs
    herbs = []
    herb_list = [
        'ginger', 'turmeric', 'peppermint', 'garlic', 'honey', 'tulsi', 'basil',
        'ashwagandha', 'chamomile', 'cinnamon', 'clove', 'licorice', 'ginseng',
        'valerian', 'neem', 'amla', 'fennel', 'cumin', 'coriander', 'fenugreek',
        'mint', 'lavender', 'eucalyptus', 'tea tree', 'aloe vera', 'coconut oil',
        'ginkgo', 'echinacea', 'elderberry', 'brahmi', 'giloy', 'triphala',
        'moringa', 'shatavari', 'ajwain', 'cardamom', 'black pepper',
    ]
    
    for herb in herb_list:
        if herb in query_lower:
            herbs. append(herb)
    
    # Medications
    medications = []
    medication_keywords = {
        'aspirin': ['aspirin', 'disprin', 'ecosprin'],
        'ibuprofen': ['ibuprofen', 'advil', 'motrin', 'brufen'],
        'paracetamol': ['paracetamol', 'acetaminophen', 'tylenol', 'crocin', 'dolo'],
        'warfarin': ['warfarin', 'coumadin'],
        'blood thinner': ['blood thinner', 'blood thinners', 'anticoagulant'],
        'metformin': ['metformin', 'glycomet', 'glucophage'],
        'insulin': ['insulin'],
        'diabetes medication': ['diabetes medication', 'diabetes medicine', 'sugar medicine'],
        'blood pressure medication': ['blood pressure', 'bp medicine', 'bp medication', 'antihypertensive'],
        'thyroid medication': ['thyroid', 'levothyroxine', 'synthroid', 'thyroxine', 'eltroxin'],
        'antidepressant': ['antidepressant', 'ssri', 'prozac', 'zoloft', 'lexapro'],
        'sedative': ['sedative', 'sleeping pill', 'sleep medication', 'benzodiazepine'],
        'statin': ['statin', 'atorvastatin', 'cholesterol medicine'],
        'pan d': ['pan d', 'pantoprazole', 'pantop', 'ppi'],
        'omeprazole': ['omeprazole', 'omez', 'prilosec'],
    }
    
    for med_name, keywords in medication_keywords.items():
        for keyword in keywords:
            if keyword in query_lower:
                if med_name not in medications:
                    medications.append(med_name)
                break
    
    return {
        'conditions': conditions,
        'herbs': herbs,
        'medications': medications,
    }

def extract_query_subject(query:  str, user_profile: Dict = None) -> Dict:
    """
    Detect if the user is asking about someone else (child, parent, etc.)
    and extract relevant demographic overrides.
    
    This enables queries like: 
    - "my 8 year old child has headache"
    - "my baby has a cold"
    - "my 70 year old mother has joint pain"
    
    Returns:
        Dict with subject context and any age/demographic overrides
    """
    query_lower = query.lower()
    
    # Default:  use the user's own profile
    subject_context = {
        'is_self': True,
        'subject_description':  None,
        'age_override': None,
        'age_group_override': None,
        'sex_override': None,
        'relationship': None,
    }
    
    # ==========================================================================
    # CHILD PATTERNS
    # ==========================================================================
    child_patterns = [
        # "my X year old child/son/daughter/baby/kid/brother/sister"
        (r'my\s+(\d{1,2})\s*(?:year|yr|years|yrs)?\s*(?:-|\s)?old\s+(child|son|daughter|kid|boy|girl|baby|infant|toddler|brother|sister)', 'child_with_age'),
        # "X year old child" (without "my")
        (r'(\d{1,2})\s*(?:year|yr|years|yrs)?\s*(?:-|\s)?old\s+(child|son|daughter|kid|boy|girl|baby|infant|toddler|brother|sister)', 'child_with_age_no_my'),
        # "for my child/son/daughter/brother/sister" with age
        (r'for\s+my\s+(\d{1,2})\s*(?:year|yr|years|yrs)?\s*(?:-|\s)?old\s+(child|son|daughter|kid|boy|girl|brother|sister)', 'child_with_age'),
        # "my baby" (assume infant < 2)
        (r'\bmy\s+(baby|infant)\b', 'infant'),
        # "my toddler" (assume 2-4 years)
        (r'\bmy\s+toddler\b', 'toddler'),
        # "my child/son/daughter" without age (assume ~8 years)
        (r'\bmy\s+(child|kid)\b', 'child_unknown'),
        (r'\bmy\s+(son|boy)\b', 'son_unknown'),
        (r'\bmy\s+(daughter|girl)\b', 'daughter_unknown'),
        # "my X month old baby"
        (r'my\s+(\d{1,2})\s*(?:month|mo|months|mos)\s*old\s+(baby|infant)', 'infant_months'),
    ]
    
    for pattern, subject_type in child_patterns:
        logger.info(f"🔍 Trying pattern: {pattern[: 50]}...  for query: {query_lower}")
        try:
            match = re.search(pattern, query_lower)
            if match:
                logger. info(f"✅ PATTERN MATCHED!  Groups: {match.groups()}")
                subject_context['is_self'] = False
                groups = match.groups()
                
                age = None
                relation = None
                
                # Extract age and relation from groups
                for group in groups:
                    if group and group.isdigit():
                        age = int(group)
                    elif group and group in ['child', 'son', 'daughter', 'kid', 'boy', 'girl', 'baby', 'infant', 'toddler', 'brother', 'sister']:
                        relation = group
                
                # Handle different subject types
                if subject_type == 'infant_months':
                    months = age if age else 6
                    subject_context['age_override'] = 1
                    subject_context['age_group_override'] = 'infant'
                    subject_context['subject_description'] = f'{months}-month-old infant'
                    subject_context['relationship'] = 'baby'
                    
                elif subject_type in ['child_with_age', 'child_with_age_no_my'] and age:
                    subject_context['age_override'] = age
                    
                    # Determine age group
                    if age < 2:
                        subject_context['age_group_override'] = 'infant'
                        subject_context['subject_description'] = f'{age}-year-old infant'
                    elif age < 5:
                        subject_context['age_group_override'] = 'toddler'
                        subject_context['subject_description'] = f'{age}-year-old toddler'
                    elif age < 12:
                        subject_context['age_group_override'] = 'child'
                        subject_context['subject_description'] = f'{age}-year-old child'
                    elif age < 18:
                        subject_context['age_group_override'] = 'teenager'
                        subject_context['subject_description'] = f'{age}-year-old teenager'
                    else:
                        subject_context['age_group_override'] = 'young_adult'
                        subject_context['subject_description'] = f'{age}-year-old'
                    
                    # Set sex if determinable
                    if relation in ['son', 'boy', 'brother']: 
                        subject_context['sex_override'] = 'male'
                        subject_context['relationship'] = relation
                        logger.info(f"🔍 DEBUG: Set relationship to '{relation}' (male)")
                    elif relation in ['daughter', 'girl', 'sister']:  
                        subject_context['sex_override'] = 'female'
                        subject_context['relationship'] = relation
                        logger.info(f"🔍 DEBUG:  Set relationship to '{relation}' (female)")
                    else:
                        subject_context['relationship'] = relation or 'child'
                        logger.info(f"🔍 DEBUG:  Defaulted relationship to '{subject_context['relationship']}' (relation was:  {relation})")

                        
                elif subject_type == 'infant':
                    subject_context['age_override'] = 1
                    subject_context['age_group_override'] = 'infant'
                    subject_context['subject_description'] = 'infant (under 2 years)'
                    subject_context['relationship'] = 'baby'
                    
                elif subject_type == 'toddler': 
                    subject_context['age_override'] = 3
                    subject_context['age_group_override'] = 'toddler'
                    subject_context['subject_description'] = 'toddler (2-4 years)'
                    subject_context['relationship'] = 'toddler'
                    
                elif subject_type == 'child_unknown':
                    subject_context['age_override'] = 8
                    subject_context['age_group_override'] = 'child'
                    subject_context['subject_description'] = 'child (estimated 8 years)'
                    subject_context['relationship'] = 'child'
                    
                elif subject_type == 'son_unknown':
                    subject_context['age_override'] = 8
                    subject_context['age_group_override'] = 'child'
                    subject_context['subject_description'] = 'son (estimated 8 years)'
                    subject_context['relationship'] = 'son'
                    subject_context['sex_override'] = 'male'
                    
                elif subject_type == 'daughter_unknown':
                    subject_context['age_override'] = 8
                    subject_context['age_group_override'] = 'child'
                    subject_context['subject_description'] = 'daughter (estimated 8 years)'
                    subject_context['relationship'] = 'daughter'
                    subject_context['sex_override'] = 'female'
                
                return subject_context
        except re.error as e:
            logger.warning(f"Regex error in child pattern: {e}")
            continue
    
    # ==========================================================================
    # ELDERLY/PARENT/GRANDPARENT PATTERNS
    # ==========================================================================
    elderly_patterns = [
        # "my X year old grandfather/grandmother/mother/father"
        (r'my\s+(\d{2,3})\s*(?:year|yr|years|yrs)?\s*(?:-|\s)?old\s+(grandfather|grandpa|grandmother|grandma|mother|mom|mum|father|dad|parent|granny|nana|papa)', 'elderly_with_age'),
        # "my grandfather/grandmother" without age (assume 75 years)
        (r'\bmy\s+(grandfather|grandpa)\b', 'grandfather_unknown'),
        (r'\bmy\s+(grandmother|grandma|granny|nana)\b', 'grandmother_unknown'),
        # "my mother/father" without age (assume 55 years)
        (r'\bmy\s+(mother|mom|mum)\b', 'mother_unknown'),
        (r'\bmy\s+(father|dad|papa)\b', 'father_unknown'),
    ]
    
    for pattern, subject_type in elderly_patterns: 
        try:
            match = re.search(pattern, query_lower)
            if match: 
                subject_context['is_self'] = False
                groups = match.groups()

                logger.info(f"🔍 DEBUG:  Pattern matched:  {pattern}")
                logger.info(f"🔍 DEBUG:  Groups extracted: {groups}")

                age = None
                relation = None

                # Extract age and relation from groups
                for group in groups:
                    if group and group.isdigit():
                        age = int(group)
                    elif group and group in ['child', 'son', 'daughter', 'kid', 'boy', 'girl', 'baby', 'infant', 'toddler', 'brother', 'sister']:
                        relation = group

                
                if subject_type == 'elderly_with_age' and age:
                    subject_context['age_override'] = age
                    
                    if age >= 75:
                        subject_context['age_group_override'] = 'elderly'
                    elif age >= 60:
                        subject_context['age_group_override'] = 'senior'
                    else:
                        subject_context['age_group_override'] = 'adult'
                    
                    subject_context['subject_description'] = f'{age}-year-old {relation or "family member"}'
                    
                elif subject_type == 'grandfather_unknown':
                    subject_context['age_override'] = 75
                    subject_context['age_group_override'] = 'elderly'
                    subject_context['subject_description'] = 'grandfather (estimated 75 years)'
                    subject_context['sex_override'] = 'male'
                    relation = 'grandfather'
                    
                elif subject_type == 'grandmother_unknown':
                    subject_context['age_override'] = 75
                    subject_context['age_group_override'] = 'elderly'
                    subject_context['subject_description'] = 'grandmother (estimated 75 years)'
                    subject_context['sex_override'] = 'female'
                    relation = 'grandmother'
                    
                elif subject_type == 'mother_unknown':
                    subject_context['age_override'] = 55
                    subject_context['age_group_override'] = 'adult'
                    subject_context['subject_description'] = 'mother (estimated 55 years)'
                    subject_context['sex_override'] = 'female'
                    relation = 'mother'
                    
                elif subject_type == 'father_unknown': 
                    subject_context['age_override'] = 55
                    subject_context['age_group_override'] = 'adult'
                    subject_context['subject_description'] = 'father (estimated 55 years)'
                    subject_context['sex_override'] = 'male'
                    relation = 'father'
                
                # Set sex based on relation
                if relation in ['mother', 'mom', 'mum', 'grandmother', 'grandma', 'granny', 'nana']: 
                    subject_context['sex_override'] = 'female'
                elif relation in ['father', 'dad', 'grandfather', 'grandpa', 'papa']:
                    subject_context['sex_override'] = 'male'
                
                subject_context['relationship'] = relation
                return subject_context
                
        except re.error as e:
            logger.warning(f"Regex error in elderly pattern:  {e}")
            continue
    
    # ==========================================================================
    # SPOUSE/PARTNER PATTERNS
    # ==========================================================================
    spouse_patterns = [
        (r'\bmy\s+(husband|wife|spouse|partner)\b', 'spouse'),
        (r'\bmy\s+(\d{2,3})\s*(?:year|yr|years|yrs)?\s*(?:-|\s)?old\s+(husband|wife|spouse|partner)', 'spouse_with_age'),
    ]
    
    for pattern, subject_type in spouse_patterns: 
        try:
            match = re.search(pattern, query_lower)
            if match: 
                subject_context['is_self'] = False
                groups = match.groups()
                
                age = None
                relation = None
                
                for group in groups: 
                    if group and group. isdigit():
                        age = int(group)
                    elif group and group in ['husband', 'wife', 'spouse', 'partner']:
                        relation = group
                
                if age: 
                    subject_context['age_override'] = age
                    if age >= 60:
                        subject_context['age_group_override'] = 'senior'
                    else: 
                        subject_context['age_group_override'] = 'adult'
                    subject_context['subject_description'] = f'{age}-year-old {relation}'
                else:
                    # Assume similar age to user
                    user_age = user_profile.get('age', 30) if user_profile else 30
                    subject_context['age_override'] = user_age
                    subject_context['age_group_override'] = 'adult'
                    subject_context['subject_description'] = f'{relation} (estimated {user_age} years)'
                
                if relation == 'husband':
                    subject_context['sex_override'] = 'male'
                elif relation == 'wife':
                    subject_context['sex_override'] = 'female'
                
                subject_context['relationship'] = relation
                return subject_context
                
        except re.error as e:
            logger.warning(f"Regex error in spouse pattern: {e}")
            continue
    
    return subject_context

# =============================================================================
# MAIN PIPELINE
# =============================================================================

def filter_response_for_allergens(response: str, allergies: List[str]) -> str:
    """
    Layer 3: Post-process response to remove any allergen mentions that slipped through.
    
    This function removes remedy sections that mention allergens while preserving
    the structure and formatting of non-allergenic content.
    
    Args:
        response: The generated response text
        allergies: List of allergen names
    
    Returns:
        Filtered response with allergen mentions removed
    """
    if not allergies or not response:
        return response
    
    # Split response into lines for processing
    lines = response.split('\n')
    filtered_lines = []
    skip_remedy = False
    removed_remedies = []
    current_remedy_name = None
    remedy_start_index = None
    
    for line in lines:
        line_lower = line.lower()
        
        # Check if this is a remedy header (e.g., "**🌿 Remedy 1: Ginger Tea with Honey**")
        remedy_header_match = re.match(r'\*\*[🌿💊]?\s*Remedy\s+\d+:\s*(.+?)\*\*', line, re.IGNORECASE)
        if remedy_header_match:
            current_remedy_name = remedy_header_match.group(1).strip()
            remedy_start_index = len(filtered_lines)
            
            # Check if remedy name contains allergen
            contains_allergen = any(allergen.lower() in line_lower for allergen in allergies)
            if contains_allergen:
                skip_remedy = True
                for allergen in allergies:
                    if allergen.lower() in line_lower:
                        removed_remedies.append(current_remedy_name)
                        logger.info(f"🛡️ Layer 3: Removed remedy '{current_remedy_name}' containing allergen '{allergen}'")
                        break
                continue
            else:
                skip_remedy = False
                filtered_lines.append(line)
                continue
        
        # Check if we're entering a new section (not a remedy)
        if line.startswith('**') and not remedy_header_match:
            # Check for common section headers
            section_markers = ['safety notes', 'when to see', 'important', 'warning', 'note:', 'seasonal', 'timing', 'scientific validation', 'confidence score']
            if any(marker in line_lower for marker in section_markers):
                skip_remedy = False
                current_remedy_name = None
        
        # If we're skipping a remedy, check if we should continue skipping
        if skip_remedy:
            # Skip until we hit the next remedy or a major section
            if line.startswith('**🌿') or line.startswith('**💊') or (line.startswith('**⚠️') and 'Safety' in line):
                skip_remedy = False
                # Don't continue here - let it process as a new section
            else:
                continue
        
        # Check if current line contains allergen (even if not in remedy header)
        contains_allergen = any(allergen.lower() in line_lower for allergen in allergies)
        if contains_allergen and current_remedy_name and remedy_start_index is not None:
            # If we find an allergen in the ingredients or instructions, skip the entire remedy
            if not skip_remedy:
                skip_remedy = True
                for allergen in allergies:
                    if allergen.lower() in line_lower:
                        removed_remedies.append(current_remedy_name)
                        logger.info(f"🛡️ Layer 3: Removed remedy '{current_remedy_name}' - allergen '{allergen}' found in content")
                        break
                # Remove all lines from this remedy using slicing
                filtered_lines = filtered_lines[:remedy_start_index]
                continue
        
        # Add line if not skipping
        if not skip_remedy:
            filtered_lines.append(line)
    
    filtered_response = '\n'.join(filtered_lines)
    
    if removed_remedies:
        logger.info(f"🛡️ Layer 3: Removed {len(set(removed_remedies))} remedies total: {set(removed_remedies)}")
    
    return filtered_response


def execute_rag_pipeline(
    query_in_english: str,
    input_language_detected: str,
    email_id: str,
    user_name: str = None,
    message_id: str = None,
    chat_history: List = None,
    user_profile: Dict = None,
) -> Tuple[Dict, Dict]:
    """
    Main RAG pipeline execution. 
    
    This is the core function that:
    1.  Checks for emergencies
    2.  Manages conversation context
    3.  Detects drug-herb interactions
    4. Retrieves relevant knowledge
    5.  Generates safe, personalized responses
    6. Validates with Trust Engine
    7. Adds chronobiological context
    
    Args:
        query_in_english: User's query (translated to English if needed)
        input_language_detected: Detected input language
        email_id: User's email for context tracking
        user_name: User's name for personalization
        message_id: Message ID for logging
        chat_history: Previous chat history
        user_profile: User's health profile (allergies, conditions, medications)
    
    Returns:
        Tuple of (response_map, message_data_update)
    """
    
    response_map = {}
    original_query = query_in_english
    retrieval_start = datetime.now()
    retrieval_end = datetime.now()
    
    # ==========================================================================
    # LOGGING
    # ==========================================================================
    logger.info("=" * 70)
    logger. info("ServVia 2.0 Agentic Pipeline Started")
    logger. info(f"Query: {original_query}")
    logger. info(f"User: {email_id}")
    logger.info("=" * 70)


    # ==========================================================================
    # EXTRACT USER PROFILE DATA
    # ==========================================================================
    allergies = []
    profile_conditions = []
    profile_medications = []
    user_age = None
    user_sex = None
    user_age_group = None

    if user_profile:
        allergies = user_profile.get('allergies', []) or []
        profile_conditions = user_profile.get('medical_conditions', []) or []
        profile_medications = user_profile. get('current_medications', []) or []
        user_age = user_profile.get('age')
        user_sex = user_profile.get('sex')
        user_age_group = user_profile.get('age_group')
    

    # ==========================================================================
    # STEP 1: EMERGENCY DETECTION
    # ==========================================================================
    emergency_type = check_emergency(original_query)
    
    if emergency_type:
        logger. info(f"🚨 EMERGENCY DETECTED: {emergency_type}")
        
        emergency_response = get_emergency_response(emergency_type)
        
        response_map['generated_final_response'] = emergency_response
        response_map['intent'] = 'emergency'
        response_map['emergency_type'] = emergency_type
        
        return response_map, {
            'message_id': message_id,
            'query': original_query,
            'response': emergency_response,
            'intent': 'emergency',
        }
    
    # ==========================================================================
    # STEP 2: EXTRACT ENTITIES FROM CURRENT QUERY
    # ==========================================================================
    current_entities = extract_entities(original_query)
    logger.info(f"Extracted entities: {current_entities}")

    # ==========================================================================
    # INITIALIZE EFFECTIVE DEMOGRAPHICS (will be overridden if asking for other)
    # ==========================================================================
    effective_age = user_age
    effective_sex = user_sex
    effective_age_group = user_age_group
    effective_subject = None

    
    # ==========================================================================
    # STEP 2.5:  DETECT IF ASKING ABOUT SOMEONE ELSE (Child, Parent, etc.)
    # ==========================================================================
    query_subject = extract_query_subject(original_query, user_profile)

    # First, check if user is NOW asking about themselves (clear previous subject context)
    if CONVERSATION_ENABLED and conversation_manager and email_id:
        if conversation_manager.should_clear_subject_context(original_query):
            previous_subject = conversation_manager.get_subject_context(email_id)
            if previous_subject. get('asking_for_other'):
                logger.info(f"🔄 User switched to asking about THEMSELVES - clearing previous subject context")
                conversation_manager.clear_subject_context(email_id)
                # Reset query_subject to self
                query_subject = {
                    'is_self': True,
                    'subject_description': None,
                    'age_override': None,
                    'age_group_override': None,
                    'sex_override': None,
                    'relationship':  None,
                }

    # If current query detected a relationship, check if we have more specific age from previous context
    if not query_subject['is_self'] and CONVERSATION_ENABLED and conversation_manager and email_id:
        # First, try current subject context
        previous_context = conversation_manager.get_subject_context(email_id)
        
        # If no current context, try previous (preserved) context
        if not previous_context or not previous_context.get('asking_for_other'):
            previous_context = conversation_manager.get_previous_subject_context(email_id)
            if previous_context and previous_context.get('asking_for_other'):
                logger.info(f"📋 Found preserved previous subject context:  {previous_context. get('query_subject')}")
        
        if previous_context and previous_context. get('asking_for_other'):
            current_relationship = (query_subject. get('relationship') or '').lower()
            previous_relationship = (previous_context. get('relationship') or '').lower()
            
            # Define similar relationships
            similar_relationships = {
                'grandfather': ['grandfather', 'grandpa'],
                'grandmother': ['grandmother', 'grandma', 'granny', 'nana'],
                'father': ['father', 'dad', 'papa'],
                'mother': ['mother', 'mom', 'mum'],
                'son': ['son', 'boy'],
                'daughter': ['daughter', 'girl'],
                'child': ['child', 'kid'],
                'baby': ['baby', 'infant'],
            }
            
            # Check if current and previous relationships match
            for key, variants in similar_relationships.items():
                current_matches = current_relationship in variants
                previous_matches = previous_relationship in variants
                
                if current_matches and previous_matches:
                    # Same person!  Use the previous age if it's more specific
                    previous_age = previous_context.get('subject_age')
                    current_age = query_subject.get('age_override')
                    
                    # Default estimated ages (we use these when age is not specified)
                    default_ages = [55, 75, 8, 3, 1]
                    
                    if previous_age and current_age in default_ages:
                        logger.info(f"📋 MATCH!  Using previous age {previous_age} instead of {current_age} for {current_relationship}")
                        query_subject['age_override'] = previous_age
                        query_subject['age_group_override'] = previous_context.get('subject_age_group')
                        query_subject['subject_description'] = previous_context.get('query_subject')
                    break


    # If no subject detected AND user is not asking about themselves, carry forward previous context
    if query_subject['is_self'] and CONVERSATION_ENABLED and conversation_manager and email_id:
        if not conversation_manager.should_clear_subject_context(original_query):
            previous_context = conversation_manager.get_subject_context(email_id)
            if previous_context and previous_context.get('asking_for_other'):
                logger.info(f"📋 Carrying forward previous subject context:  {previous_context. get('query_subject')}")
                query_subject = {
                    'is_self':  False,
                    'subject_description': previous_context.get('query_subject'),
                    'age_override': previous_context.get('subject_age'),
                    'age_group_override': previous_context.get('subject_age_group'),
                    'sex_override': previous_context.get('subject_sex'),
                    'relationship': previous_context.get('relationship'),
                }

    # Apply the subject context to the profile
    if not query_subject['is_self']: 
        logger.info(f"🎯 Query is about someone else: {query_subject['subject_description']}")
        logger.info(f"🎯 Age override: {query_subject['age_override']}, Age group: {query_subject['age_group_override']}")
        
        # Create a modified profile for this query
        if user_profile:
            user_profile = user_profile.copy()
        else:
            user_profile = {}
        
        # Apply overrides
        user_profile['age'] = query_subject['age_override']
        user_profile['age_group'] = query_subject['age_group_override']
        user_profile['query_subject'] = query_subject['subject_description']
        user_profile['asking_for_other'] = True
        user_profile['relationship'] = query_subject.get('relationship')
        
        if query_subject.get('sex_override'):
            user_profile['sex'] = query_subject['sex_override']
        
        # Update local variables AND effective demographics
        user_age = query_subject['age_override']
        user_sex = query_subject.get('sex_override') or (user_profile.get('sex') if user_profile else None)
        user_age_group = query_subject['age_group_override']

        # Set effective demographics for response generation
        effective_age = user_age
        effective_sex = user_sex
        effective_age_group = user_age_group
        effective_subject = query_subject['subject_description']

        
        # Store/update this context for future follow-up queries
        if CONVERSATION_ENABLED and conversation_manager and email_id:
            conversation_manager.update_subject_context(
                email_id,
                asking_for_other=True,
                query_subject=query_subject['subject_description'],
                subject_age=query_subject['age_override'],
                subject_age_group=query_subject['age_group_override'],
                subject_sex=query_subject.get('sex_override'),
                relationship=query_subject.get('relationship')
            )
    else:
        logger.info(f"📋 Query is about the user themselves (age: {user_age})")
    
        # Ensure asking_for_other is explicitly set to False for clarity
        if user_profile:
            user_profile = user_profile.copy()
        else:
            user_profile = {}
    
        user_profile['asking_for_other'] = False
        user_profile['query_subject'] = None
        user_profile['relationship'] = None


    # ==========================================================================
    # LOG EFFECTIVE PROFILE
    # ==========================================================================
    if user_profile and user_profile.get('asking_for_other'):
        logger.info(f"📋 Profile (ASKING FOR {user_profile.get('relationship', 'other').upper()}) - Age: {user_profile.get('age')}, Sex: {user_profile.get('sex')}, Subject: {user_profile.get('query_subject')}")
        logger.info(f"📋 User's own allergies still apply: {allergies}")
    else:
        logger.info(f"📋 Profile - Allergies: {allergies}, Conditions: {profile_conditions}, Meds: {profile_medications}, Age: {user_age}, Sex: {user_sex}, Age Group: {user_age_group}")


    # ==========================================================================
    # LOG EFFECTIVE PROFILE
    # ==========================================================================
    logger.info(f"📊 EFFECTIVE DEMOGRAPHICS - Age: {effective_age}, Sex: {effective_sex}, Age Group: {effective_age_group}")

    if user_profile and user_profile.get('asking_for_other'):
        logger.info(f"📋 Profile (ASKING FOR {user_profile. get('relationship', 'other').upper()}) - Age: {user_profile.get('age')}, Sex: {user_profile. get('sex')}, Subject: {user_profile.get('query_subject')}")
        logger.info(f"📋 User's own allergies still apply: {allergies}")
    else:
        logger.info(f"📋 Profile - Allergies: {allergies}, Conditions: {profile_conditions}, Meds: {profile_medications}, Age: {user_age}, Sex: {user_sex}, Age Group: {user_age_group}")


    # ==========================================================================
    # STEP 3: UPDATE CONVERSATION CONTEXT
    # ==========================================================================
    context_changes = {'added': [], 'removed': []}
    accumulated_context = {'herbs': [], 'medications': [], 'conditions': []}
    
    if CONVERSATION_ENABLED and conversation_manager and email_id:
        # Update context (handles additions and removals)
        context_changes = conversation_manager.update_context(email_id, original_query)
        
        # Store user message
        conversation_manager.add_message(email_id, 'user', original_query)
        
        # Get accumulated context
        accumulated_context = conversation_manager.get_context(email_id)
        
        if context_changes. get('removed'):
            logger.info(f"🔄 User STOPPED: {context_changes['removed']}")
        if context_changes.get('added'):
            logger.info(f"➕ User ADDED: {context_changes['added']}")
    
    # ==========================================================================
    # STEP 4: MERGE ALL CONTEXT
    # ==========================================================================
    
    # Get stopped medications for filtering
    stopped_medications = []
    if context_changes.get('removed'):
        stopped_medications = [
            r. replace('medication: ', '').lower()
            for r in context_changes['removed']
            if 'medication:' in r
        ]
    
    # Merge herbs
    all_herbs = list(set(
        accumulated_context. get('herbs', []) +
        current_entities['herbs']
    ))
    
    # Merge medications (excluding stopped ones, including profile meds)
    all_medications = list(set(
        accumulated_context.get('medications', []) +
        current_entities['medications'] +
        profile_medications
    ))
    
    # Merge conditions
    all_conditions = list(set(
        accumulated_context.get('conditions', []) +
        current_entities['conditions']
    ))
    
    # Determine CURRENT condition
    # Priority: 1) Current query, 2) Subject-related condition from history, 3) Most recent
    current_condition = None
    
    if current_entities['conditions']:
        # Condition explicitly mentioned in current query
        current_condition = current_entities['conditions'][0]
        logger.info(f"📋 Condition from current query: {current_condition}")
    else:
        # For follow-up queries about someone else, find THEIR condition from history
        if CONVERSATION_ENABLED and conversation_manager and email_id:
            # Get the relationship we're asking about
            asking_for_relationship = None
            if user_profile and user_profile.get('asking_for_other'):
                asking_for_relationship = user_profile. get('relationship', '').lower()
            
            if asking_for_relationship:
                history = conversation_manager.get_history(email_id)
                
                # Search backward through messages for conditions related to THIS subject
                for msg in reversed(history[-8:]):  # Check last 8 messages
                    if msg.get('role') == 'user':
                        msg_content = msg.get('content', '').lower()
                        
                        # Check if this message mentions the same relationship
                        relationship_keywords = {
                            'grandfather': ['grandfather', 'grandpa', '95 year old grandfather', '95-year-old grandfather'],
                            'grandmother': ['grandmother', 'grandma', 'granny', 'nana'],
                            'father': ['father', 'dad'],
                            'mother': ['mother', 'mom', 'mum'],
                            'child': ['child', 'son', 'daughter', 'kid', 'baby'],
                        }
                        
                        # Find keywords for this relationship
                        rel_keywords = []
                        for key, variants in relationship_keywords.items():
                            if asking_for_relationship in variants or key == asking_for_relationship:
                                rel_keywords = variants
                                break
                        
                        # Check if message is about this relationship
                        if any(kw in msg_content for kw in rel_keywords):
                            msg_entities = extract_entities(msg. get('content', ''))
                            if msg_entities['conditions']:
                                current_condition = msg_entities['conditions'][0]
                                logger.info(f"📋 Found condition '{current_condition}' from {asking_for_relationship}'s history")
                                break
        
        # Fallback to most recent condition only if asking about self
        if not current_condition: 
            if user_profile and user_profile.get('asking_for_other'):
                # For "asking for other", use the subject's condition or default
                # Look in all_conditions for subject-related conditions
                for cond in reversed(all_conditions):
                    if cond != 'headache' or not user_profile.get('asking_for_other'):
                        current_condition = cond
                        logger.info(f"📋 Using condition from context: {current_condition}")
                        break
                if not current_condition and all_conditions:
                    current_condition = all_conditions[0]  # First condition added (likely the subject's)
                    logger.info(f"📋 Using first condition:  {current_condition}")
            elif all_conditions:
                current_condition = all_conditions[-1]
                logger.info(f"📋 Using most recent condition: {current_condition}")

    
    # ==========================================================================
    # STEP 5: CHECK DRUG-HERB INTERACTIONS
    # ==========================================================================
    interaction_warnings = []
    safety_instructions = ""
    
    if all_herbs and all_medications:
        interaction_warnings = check_interactions(all_herbs, all_medications)
        
        if interaction_warnings:
            logger.info(f"⚠️ INTERACTIONS FOUND: {len(interaction_warnings)}")
            
            safety_instructions = "\n\n🚨 CRITICAL SAFETY ALERTS 🚨\n"
            
            for warning in interaction_warnings:
                logger.info(f"   - {warning['herb']} + {warning['medication']} = {warning['severity']}")
                
                safety_instructions += f"""
**{warning['severity']} SEVERITY - DO NOT RECOMMEND {warning['herb']. upper()}**
User is taking: {warning['medication']}
Risk: {warning['reason']}
Safe alternatives to suggest: {', '.join(warning['alternatives'])}

You MUST:
1.  Clearly state that {warning['herb']} should NOT be used with {warning['medication']}
2.  Explain the specific risk in simple terms
3.  Recommend these safe alternatives instead

"""
    
    # ==========================================================================
    # STEP 6: QUERY REPHRASING
    # ==========================================================================
    rephrased_query = original_query
    
    try:
        rephrased_query = asyncio.run(
            rephrase_query(original_query, chat_history or [])
        )
        logger.info(f"Rephrased: {rephrased_query}")
    except Exception as e:
        logger.warning(f"Query rephrasing failed: {e}")
    
    # ==========================================================================
    # STEP 7: KNOWLEDGE RETRIEVAL
    # ==========================================================================
    context_chunks = ""
    chunks_list = []
    
    try:
        retrieval_start = datetime.now()
        
        retrieved = retrieve_content(rephrased_query, email_id, top_k=10)
        
        retrieval_end = datetime.now()
        
        if retrieved:
            chunks_list = retrieved. get('chunks', [])
            
            # Combine chunks into context
            chunk_texts = []
            for chunk in chunks_list[:5]:
                text = chunk.get('text', '') or chunk.get('content', '') or str(chunk)
                chunk_texts.append(text)
            
            context_chunks = "\n\n".join(chunk_texts)
        
        logger.info(f"Retrieved {len(chunks_list)} chunks")
        
    except Exception as e:
        logger.error(f"Knowledge retrieval failed: {e}")
        retrieval_end = datetime.now()
    
    # ==========================================================================
    # STEP 8: GENERATE RESPONSE
    # ==========================================================================
    llm_response = ""
    
    try:
        logger.info("Generating response with OpenAI...")
        
        # Get conversation history
        conversation_history = ""
        if CONVERSATION_ENABLED and conversation_manager and email_id:
            conversation_history = conversation_manager.get_formatted_history(email_id)
        
        generated = asyncio.run(
            generate_query_response(
                original_query=original_query,
                user_name=user_name,
                context_chunks=context_chunks,
                rephrased_query=rephrased_query,
                email_id=email_id,
                user_profile=user_profile,
                safety_instructions=safety_instructions,
                conversation_context={
                    'conditions': all_conditions,
                    'herbs': all_herbs,
                    'medications': all_medications,
                    'current_condition': current_condition,
                    'history': conversation_history,
                },
                context_changes=context_changes,
            )
        )
        
        llm_response = generated. get('response', '')
        
        logger.info(f"Response generated: {len(llm_response)} characters")
        
        response_map. update({
            'generation_start_time': generated.get('generation_start_time'),
            'generation_end_time': generated.get('generation_end_time'),
            'completion_tokens': generated.get('completion_tokens', 0),
            'prompt_tokens': generated.get('prompt_tokens', 0),
            'total_tokens': generated. get('total_tokens', 0),
        })
        
    except Exception as e:
        logger.error(f"Response generation failed: {e}")
        llm_response = "I'm having trouble generating a response right now. Please try again in a moment."
    
    # ==========================================================================
    # STEP 8.5: LAYER 3 - POST-PROCESS RESPONSE FOR ALLERGENS
    # ==========================================================================
    if allergies:
        logger.info(f"🛡️ Layer 3: Applying post-processing allergy filter for: {allergies}")
        llm_response = filter_response_for_allergens(llm_response, allergies)
        logger.info(f"🛡️ Layer 3: Post-processing complete")
    
    # Store assistant response
    if CONVERSATION_ENABLED and conversation_manager and email_id:
        conversation_manager.add_message(email_id, 'assistant', llm_response)
    
    # ==========================================================================
    # STEP 9: TRUST ENGINE VALIDATION
    # ==========================================================================
    verified_herbs = []
    
    try:
        logger.info("Running Trust Engine validation...")
        
        from servvia2.trust_engine. engine import TrustEngine
        
        trust_engine = TrustEngine()
        
        # Verify response with CURRENT condition and CURRENT medications
        results, global_warnings = trust_engine. verify_response(
            llm_response=llm_response,
            query=original_query,
            user_conditions=profile_conditions,
            user_medications=all_medications,
            user_allergies=allergies,
            current_condition=current_condition,  # Pass the actual condition! 
        )
        
        # Collect verified herbs
        for r in results:
            if r. is_valid and not r.is_hallucination:
                verified_herbs.append(r.herb_name)
        
        logger.info(f"Verified herbs: {verified_herbs}")
        
        # Filter out warnings for stopped medications
        if stopped_medications:
            logger.info(f"Filtering warnings for stopped medications: {stopped_medications}")
            
            # Filter global warnings
            filtered_warnings = []
            for warning in global_warnings:
                should_keep = True
                for stopped in stopped_medications:
                    if stopped in warning. lower():
                        should_keep = False
                        logger.info(f"   Filtered out warning about: {stopped}")
                        break
                if should_keep:
                    filtered_warnings.append(warning)
            global_warnings = filtered_warnings
            
            # Filter interaction notes from results
            for r in results:
                if r.interaction_note:
                    for stopped in stopped_medications:
                        if stopped in r.interaction_note.lower():
                            logger.info(f"   Removed interaction note for: {stopped}")
                            r.interaction_note = None
                            break
        
        # Track verified herbs in conversation context
        if CONVERSATION_ENABLED and conversation_manager and email_id and verified_herbs:
            for herb in verified_herbs:
                conversation_manager.update_context(email_id, f"recommended {herb}")
        
        # Add validation section to response
        if results:
            validation_section = trust_engine.format_validation_section(results, global_warnings)
            llm_response = llm_response + validation_section
        
        response_map['trust_engine_verified'] = True
        response_map['verified_count'] = len(verified_herbs)
        
    except Exception as e:
        logger.warning(f"Trust Engine validation failed: {e}")
        response_map['trust_engine_verified'] = False
    
    # ==========================================================================
    # STEP 10: CHRONOBIOLOGICAL CONTEXT
    # ==========================================================================
    if verified_herbs:
        try:
            logger. info("Adding chronobiological context...")
            
            from servvia2.chronobiology.engine import CircadianEngine
            
            chrono_engine = CircadianEngine()
            
            # Get seasonal context
            seasonal = chrono_engine. get_seasonal_context(latitude=20.0)
            
            # Get timing advice for remedies
            timing_advice = chrono_engine.format_timing_advice(verified_herbs[:3])
            
            # Build seasonal section
            chrono_section = f"\n\n**Seasonal Wellness ({seasonal['season_name']}):**\n"
            chrono_section += f"_{seasonal['dosha_focus']}_\n\n"
            
            # Get beneficial herbs (filter out allergies)
            beneficial = seasonal. get('beneficial_herbs', [])
            safe_beneficial = [
                h for h in beneficial
                if h. lower() not in [a.lower() for a in allergies]
            ]
            
            if safe_beneficial:
                chrono_section += f"**Beneficial this season:** {', '.join(safe_beneficial[:4])}\n"
            
            # Add diet tip
            if seasonal.get('diet_tips'):
                chrono_section += f"**Diet tip:** {seasonal['diet_tips'][0]}\n"
            
            # Append to response
            llm_response = llm_response + timing_advice + chrono_section
            
        except Exception as e:
            logger. warning(f"Chronobiology context failed: {e}")
    
    # ==========================================================================
    # FINALIZE RESPONSE
    # ==========================================================================
    response_map['generated_final_response'] = llm_response
    response_map['retrieval_start'] = retrieval_start
    response_map['retrieval_end'] = retrieval_end
    
    message_data_update = {
        'message_id': message_id,
        'query': original_query,
        'rephrased_query': rephrased_query,
        'response': llm_response,
        'chunks_retrieved': len(chunks_list),
        'current_condition': current_condition,
    }
    
    logger.info("=" * 70)
    logger.info("ServVia 2. 0 Pipeline Completed Successfully")
    logger. info("=" * 70)
    
    return response_map, message_data_update