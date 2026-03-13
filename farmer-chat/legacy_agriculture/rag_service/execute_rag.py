"""
ServVia 2.0 - Agentic RAG Pipeline (Legacy Monolith Production Build)
=====================================================================
Intelligent health assistant pipeline.
This file contains the complete orchestration logic, embedded knowledge bases,
and granular decision trees for the ServVia health agent.

Core Components:
1. Emergency Response Logic (Hardcoded Safety Layer)
2. Drug-Herb Interaction Database (Embedded)
3. Entity Extraction & Context Management
4. RAG Orchestration (Async)
5. Response Synthesis & Validation

Author: ServVia Team
Version: 2.1.0 (Extended Monolith)
Last Updated: 2025-12-16
"""

import asyncio
import logging
import time
import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union
from types import SimpleNamespace

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('servvia_pipeline.log')
    ]
)
logger = logging.getLogger("ServVia_Pipeline_Monolith")

# =============================================================================
# OPTIONAL DEPENDENCY IMPORTS (Graceful Degradation)
# =============================================================================
try:
    from legacy_agriculture.generation.generate_response import generate_query_response
    from legacy_agriculture.rag_service.content_retrieval import retrieve_content
    from legacy_agriculture.rag_service.query_rephrase import rephrase_query
    from servvia2.conversation.manager import conversation_manager
    from servvia2.trust_engine.engine import get_trust_engine
    from servvia2.chronobiology.engine import CircadianEngine
    
    # Check if conversation_manager is instantiated
    if conversation_manager is None:
        logger.warning("Conversation manager imported but is None")
        CONVERSATION_ENABLED = False
    else:
        CONVERSATION_ENABLED = True
        
    SERVICES_AVAILABLE = True
    logger.info("All core ServVia services imported successfully.")
except ImportError as e:
    logger.warning(f"⚠️ Core services missing (ImportError: {e}). Pipeline running in fallback mode.")
    SERVICES_AVAILABLE = False
    CONVERSATION_ENABLED = False
    conversation_manager = None

# =============================================================================
# SECTION 1: EMERGENCY RESPONSE SYSTEM (HARDCODED SAFETY LAYER)
# =============================================================================

class EmergencySystem:
    """
    Dedicated system for detecting and handling life-threatening situations.
    Contains hardcoded responses to prevent LLM hallucinations during crises.
    """
    
    # Detailed protocols for specific emergencies
    PROTOCOLS = {
        'cardiac_arrest': """🚨 **EMERGENCY - CARDIAC ARREST / NOT BREATHING**

**CALL 112 (India) / 911 (US) / 999 (UK) IMMEDIATELY**

**CPR Steps (Hands-Only for untrained):**

1. **CHECK** - Tap shoulders firmly, shout "Are you OK?"
2. **CALL** - If no response, call emergency services immediately.
3. **PUSH** - Start chest compressions:
   
   - Place heel of hand on center of chest (nipple line).
   - Place other hand on top and interlock fingers.
   - Push hard and fast (at least 2 inches deep).
   - Rate: 100-120 compressions per minute (beat of "Stayin' Alive").
   - Allow full chest recoil between compressions.

4. **If trained in CPR:**
   - After 30 compressions, give 2 rescue breaths.
   - Tilt head back, lift chin, pinch nose.
   - Breathe into mouth until chest rises.

5. **CONTINUE** until help arrives or person responds.

**🔴 This is a life-threatening emergency. Every second counts.**""",

        'choking': """🚨 **EMERGENCY - CHOKING**

**CALL 112 (India) / 911 (US) / 999 (UK)**

**For ADULTS - Heimlich Maneuver:**

1. Stand behind the person.
2. Make a fist with one hand.
3. Place thumb side of fist just above the belly button (below ribs).
4. Grasp fist with other hand.
5. Give quick, upward abdominal thrusts.
6. Repeat until object is expelled or person becomes unconscious.

**For INFANTS (under 1 year):**

1. Place infant face-down on your forearm, supporting head/jaw.
2. Give 5 firm back blows between shoulder blades.
3. Turn infant over (face-up).
4. Give 5 chest thrusts with two fingers (center of chest).
5. Repeat until object comes out.

**If person becomes unconscious, start CPR immediately.**

**🔴 This is a life-threatening emergency.**""",

        'cardiac': """🚨 **EMERGENCY - POSSIBLE HEART ATTACK**

**CALL 112 (India) / 911 (US) / 999 (UK) IMMEDIATELY**

**Immediate Actions:**
1. **Sit Down**: Have the person sit or lie in a comfortable position (usually half-sitting).
   
2. **Loosen Clothing**: Loosen collar, belt, or any tight clothing.
3. **Aspirin**: If available and NOT allergic, chew (don't swallow whole) one adult aspirin (325mg).
4. **Nitroglycerin**: If they have prescribed nitroglycerin, help them take it.
5. **Stay Calm**: Reassure the person. Anxiety increases heart strain.
6. **CPR Prep**: Be ready to perform CPR if they become unresponsive.

**Warning Signs:**
- Chest pain/pressure (elephant sitting on chest).
- Pain spreading to left arm, jaw, neck, or back.
- Shortness of breath.
- Cold sweat, nausea, lightheadedness.

**🔴 Do NOT let them walk. Do NOT drive yourself to the hospital.**""",

        'stroke': """🚨 **EMERGENCY - POSSIBLE STROKE**

**CALL 112 (India) / 911 (US) / 999 (UK) IMMEDIATELY**

**Perform the F.A.S.T. Check:**


[Image of FAST stroke signs infographic]


- **F**ace: Ask them to smile. Does one side of the face droop?
- **A**rms: Ask them to raise both arms. Does one arm drift downward?
- **S**peech: Ask them to repeat a simple phrase. Is speech slurred or strange?
- **T**ime: If ANY of these signs are present, call emergency immediately!

**While Waiting:**
1. **Note the Time**: Write down exactly when symptoms started (critical for clot-busting drugs).
2. **Position**: Keep them lying down comfortably with head slightly raised.
3. **Nothing by Mouth**: Do NOT give food, water, or medication (choking risk).
4. **Loosen Clothing**: Ensure easy breathing.
5. **Recovery Position**: If unconscious but breathing, turn onto side.

**🔴 "Time is Brain" - millions of neurons die per minute. Act fast.**""",

        'mental_health': """🚨 **You Are Not Alone - Help Is Available**

**Please reach out to a professional right now:**

**Crisis Helplines (24/7):**
- 🇮🇳 India: **iCall** (9152987821) | **Vandrevala Foundation** (1860-2662-345)
- 🇺🇸 USA: **988** (Suicide & Crisis Lifeline)
- 🇬🇧 UK: **116 123** (Samaritans)
- 🌍 Global: **findahelpline.com**

**If you or someone is in immediate physical danger:**
Call **112** (India) / **911** (US) / **999** (UK) now.

**Remember:**
- This intense feeling is temporary; it will pass.
- You matter, and your life has value.
- Professional help works - millions have recovered from crisis.
- Reaching out is an act of extreme courage, not weakness.

**Please talk to someone. We care about you. 💙**""",

        'poisoning': """🚨 **EMERGENCY - POISONING / OVERDOSE**

**CALL POISON CONTROL CENTER IMMEDIATELY:**
- 🇮🇳 India: **1800-11-6117** (AIIMS Poison Control)
- 🇺🇸 USA: **1-800-222-1222**
- 🇬🇧 UK: **111** (NHS)

**Immediate Do's and Don'ts:**
- **DO NOT** induce vomiting unless explicitly told to by a professional.
- **DO NOT** give anything to eat or drink (milk/water) unless instructed.
- **DO NOT** wait for symptoms to appear.

**Action Steps:**
1. **Call Immediately**: Do not guess; call the experts.
2. **Identify Substance**: Have the bottle/container ready to read the label.
3. **Assess Victim**: Know the person's approximate age and weight.
4. **Time**: Note when the exposure occurred.
5. **Skin/Eye Contact**:
   - Skin: Remove contaminated clothing, rinse with water for 15 mins.
   - Eyes: Flush gently with water for 15-20 mins.

**🔴 This is a medical emergency. Professional guidance is mandatory.**""",

        'allergic_reaction': """🚨 **EMERGENCY - ANAPHYLAXIS (SEVERE ALLERGY)**

**CALL 112 (India) / 911 (US) / 999 (UK) IMMEDIATELY**

**If the person has an EpiPen (Epinephrine):**

1. Remove the blue safety cap.
2. Swing and push the orange tip firmly into mid-outer thigh (through clothes if needed).
3. Hold for 10 seconds (or as directed on device).
4. Massage the area for 10 seconds.
5. Note the time of injection.

**While waiting for help:**
1. Have person lie flat with legs elevated (unless vomiting/difficulty breathing).
2. Loosen tight clothing.
3. If vomiting, turn them on their side.
4. Do NOT give food or drink.
5. Be prepared to start CPR if they stop breathing.

**Signs of Anaphylaxis:**
- Difficulty breathing, wheezing, throat tightness.
- Swelling of face, lips, tongue.
- Hives, rash, itching.
- Dizziness, fainting, rapid heartbeat.

**🔴 Anaphylaxis can progress rapidly to death. Do not wait.**""",

        'severe_bleeding': """🚨 **EMERGENCY - SEVERE BLEEDING**

**CALL 112 (India) / 911 (US) / 999 (UK) IMMEDIATELY**

**Immediate Steps to Stop the Bleed:**

1. **Direct Pressure**:
   
   - Cover wound with clean cloth/gauze.
   - Push HARD directly on the bleeding source with both hands.
   - Maintain continuous pressure. Do not stop to check.

2. **Don't Remove Cloths**:
   - If blood soaks through, add MORE layers on top.
   - Removing the bottom layer disrupts clotting.

3. **Elevate**:
   - Raise the injured limb above heart level if possible.

4. **Tourniquet (Life-Threatening Limb Bleeding Only)**:
   - Only use if direct pressure fails or is impossible.
   - Apply high and tight on the limb (between wound and heart).
   - Tighten until bleeding stops. This will be painful.
   - Note the time applied.

**🔴 Do NOT remove embedded objects (knife/glass) - apply pressure around them.**""",
    }

    @staticmethod
    def detect_intent(query: str) -> Optional[str]:
        """
        Scans user query for emergency keywords using robust matching.
        Returns the emergency key (e.g., 'cardiac') or None.
        """
        q = query.lower().strip()
        
        # Keyword mapping for detection
        triggers = {
            'cardiac_arrest': [
                'cpr', 'not breathing', 'stopped breathing', 'no pulse', 
                'unconscious not breathing', 'not responding and not breathing'
            ],
            'choking': [
                'choking', 'cant breathe', "can't breathe", 'stuck in throat', 
                'heimlich', 'food stuck throat', 'gasping for air'
            ],
            'cardiac': [
                'heart attack', 'chest pain', 'chest pressure', 'heart pain',
                'pain in left arm', 'crushing chest pain', 'myocardial infarction'
            ],
            'stroke': [
                'stroke', 'face drooping', 'arm weakness', 'slurred speech', 
                'sudden confusion', 'cant speak', 'can\'t speak properly',
                'one side paralyzed', 'numbness on one side'
            ],
            'mental_health': [
                'suicide', 'kill myself', 'want to die', 'end my life', 
                'self harm', 'hurt myself', 'dont want to live', 'better off dead',
                'suicidal', 'ending it all'
            ],
            'poisoning': [
                'poisoning', 'overdose', 'swallowed poison', 'took too many pills', 
                'drank bleach', 'ate rat poison', 'ingested chemical', 'pill overdose'
            ],
            'allergic_reaction': [
                'anaphylaxis', 'allergic reaction severe', 'cant breathe allergy', 
                'throat closing', 'swollen tongue', 'epipen', 'peanut allergy reaction',
                'bee sting reaction'
            ],
            'severe_bleeding': [
                'severe bleeding', 'wont stop bleeding', 'blood everywhere', 
                'arterial bleeding', 'gushing blood', 'cut artery', 'stab wound',
                'gunshot wound', 'hemorrhage'
            ],
        }
        
        # Check against triggers
        for emergency_type, keywords in triggers.items():
            for keyword in keywords:
                # Use word boundary or direct inclusion depending on length
                if len(keyword.split()) > 1:
                    if keyword in q:
                        logger.warning(f"🚨 EMERGENCY TRIGGER: '{keyword}' matched in query")
                        return emergency_type
                else:
                    # Single words need boundary check to avoid false positives (e.g., "stroke" vs "keystroke")
                    if re.search(r'\b' + re.escape(keyword) + r'\b', q):
                        logger.warning(f"🚨 EMERGENCY TRIGGER: '{keyword}' matched in query")
                        return emergency_type
                        
        return None

    @staticmethod
    def get_response(emergency_type: str) -> str:
        """Retrieves the pre-formatted markdown response for the emergency."""
        return EmergencySystem.PROTOCOLS.get(
            emergency_type,
            """🚨 **EMERGENCY DETECTED**

**CALL 112 (India) / 911 (US) / 999 (UK) IMMEDIATELY**

Please describe the emergency to the dispatcher clearly.
Stay calm, stay on the line, and follow their instructions.

**This is a medical emergency. Professional help is essential.**"""
        )

# =============================================================================
# SECTION 2: INTERACTION DATABASE (EMBEDDED KNOWLEDGE BASE)
# =============================================================================

class InteractionDatabase:
    """
    In-memory database of herb-drug interactions.
    Used for pre-generation safety checks.
    """
    
    DATA = {
        'ginger': {
            'drugs': [
                'aspirin', 'ibuprofen', 'warfarin', 'blood thinner', 'coumadin', 
                'plavix', 'clopidogrel', 'anticoagulant', 'heparin', 'enoxaparin'
            ],
            'severity': 'HIGH',
            'reason': 'Ginger inhibits platelet aggregation (blood thinning effect). Combined with anticoagulants, this significantly increases bleeding risk (bruising, internal bleeding).',
            'alternatives': ['Peppermint oil (topical)', 'Lavender aromatherapy', 'Cold compress', 'Chamomile tea'],
        },
        'turmeric': {
            'drugs': [
                'aspirin', 'warfarin', 'blood thinner', 'coumadin', 'metformin', 
                'diabetes medication', 'insulin', 'glipizide', 'glyburide'
            ],
            'severity': 'HIGH',
            'reason': 'Curcumin has antiplatelet effects (bleeding risk) and can lower blood sugar (hypoglycemia risk). Use cautiously with these medications.',
            'alternatives': ['Boswellia (for inflammation)', 'Cold compress', 'Rest and elevation', 'Omega-3 foods'],
        },
        'garlic': {
            'drugs': [
                'aspirin', 'warfarin', 'blood thinner', 'hiv medication', 
                'saquinavir', 'anticoagulant', 'antiplatelet'
            ],
            'severity': 'MODERATE',
            'reason': 'Garlic supplements have blood-thinning properties. Culinary amounts are likely safe, but therapeutic doses increase bleeding risk.',
            'alternatives': ['Onion (milder effect)', 'Oregano', 'Thyme'],
        },
        'ashwagandha': {
            'drugs': [
                'thyroid medication', 'levothyroxine', 'synthroid', 'sedative', 
                'benzodiazepine', 'immunosuppressant', 'thyronorm', 'eltroxin'
            ],
            'severity': 'HIGH',
            'reason': 'Ashwagandha stimulates thyroid hormone production (risk of thyrotoxicosis) and potentiates sedatives (excessive drowsiness).',
            'alternatives': ['Chamomile tea (for stress)', 'Lavender aromatherapy', 'Deep breathing exercises', 'Brahmi'],
        },
        'licorice': {
            'drugs': [
                'blood pressure medication', 'bp medicine', 'antihypertensive', 
                'diuretic', 'digoxin', 'heart medication', 'ace inhibitor', 'beta blocker'
            ],
            'severity': 'HIGH',
            'reason': 'Glycyrrhizin in licorice causes sodium retention and potassium loss, raising blood pressure and counteracting BP medications. Dangerous with digoxin.',
            'alternatives': ['Honey (for sore throat)', 'Slippery elm', 'Marshmallow root'],
        },
        'ginseng': {
            'drugs': [
                'warfarin', 'blood thinner', 'diabetes medication', 'metformin', 
                'insulin', 'antidepressant', 'maoi', 'stimulant'
            ],
            'severity': 'MODERATE',
            'reason': 'Ginseng can lower blood sugar and affect blood clotting. It also has stimulant properties that may interact with MAOIs or caffeine.',
            'alternatives': ['Green tea (moderate amounts)', 'Peppermint tea', 'Amla'],
        },
        'st johns wort': {
            'drugs': [
                'antidepressant', 'ssri', 'birth control', 'contraceptive', 
                'hiv medication', 'immunosuppressant', 'warfarin', 'digoxin', 'chemotherapy'
            ],
            'severity': 'CRITICAL',
            'reason': "St. John's Wort is a potent inducer of liver enzymes (CYP3A4), causing rapid metabolism of many drugs. This leads to treatment failure (e.g., organ rejection, unwanted pregnancy).",
            'alternatives': ['Lavender', 'Chamomile', 'Exercise', 'Light therapy'],
        },
        'valerian': {
            'drugs': [
                'sedative', 'benzodiazepine', 'sleep medication', 'ambien', 
                'alcohol', 'xanax', 'valium', 'ativan'
            ],
            'severity': 'HIGH',
            'reason': 'Valerian acts on GABA receptors. Combining with other CNS depressants risks severe sedation, respiratory depression, or confusion.',
            'alternatives': ['Chamomile tea', 'Warm milk', 'Lavender aromatherapy', 'Sleep hygiene practices'],
        },
        'kava': {
            'drugs': [
                'alcohol', 'sedative', 'benzodiazepine', 'antidepressant', 
                'levodopa', 'tylenol', 'acetaminophen'
            ],
            'severity': 'CRITICAL',
            'reason': 'Kava carries a risk of hepatotoxicity (liver damage). Combining with alcohol or liver-metabolized drugs amplifies this risk significantly.',
            'alternatives': ['Chamomile', 'Passionflower', 'Lavender'],
        },
        'ginkgo': {
            'drugs': [
                'aspirin', 'warfarin', 'blood thinner', 'nsaid', 'ibuprofen', 
                'anticonvulsant', 'seizure medication'
            ],
            'severity': 'HIGH',
            'reason': 'Ginkgo inhibits platelet activating factor (bleeding risk) and can lower seizure threshold, interfering with anticonvulsants.',
            'alternatives': ['Brahmi (for cognitive support)', 'Green tea', 'Omega-3 fatty acids'],
        },
        'echinacea': {
            'drugs': [
                'immunosuppressant', 'cyclosporine', 'corticosteroid', 
                'methotrexate', 'autoimmune medication'
            ],
            'severity': 'MODERATE',
            'reason': 'Echinacea stimulates immune function, theoretically counteracting immunosuppressive therapies used for organ transplants or autoimmune diseases.',
            'alternatives': ['Vitamin C foods', 'Zinc lozenges', 'Rest and hydration'],
        },
        'grapefruit': {
            'drugs': [
                'statin', 'atorvastatin', 'simvastatin', 'calcium channel blocker', 
                'blood pressure medication', 'psychiatric medication'
            ],
            'severity': 'MODERATE',
            'reason': 'While not an herb, grapefruit inhibits CYP3A4 enzymes, causing toxic accumulation of many drugs (especially statins).',
            'alternatives': ['Oranges', 'Lemons', 'Limes'],
        }
    }

    @classmethod
    def check_interactions(cls, herbs: List[str], medications: List[str]) -> List[Dict]:
        """
        Checks a list of herbs against a list of user medications.
        Returns a list of interaction warning dictionaries.
        """
        warnings = []
        if not herbs or not medications:
            return warnings

        # Normalize inputs
        meds_lower = [m.lower().strip() for m in medications]
        
        for herb in herbs:
            herb_key = herb.lower().strip()
            
            # Direct lookup
            if herb_key in cls.DATA:
                interaction_info = cls.DATA[herb_key]
                dangerous_drugs = interaction_info['drugs']
                
                # Check each user medication against dangerous list
                for user_med in meds_lower:
                    # Check if user_med contains any dangerous keyword (e.g. "aspirin" in "low dose aspirin")
                    # OR if dangerous keyword is in user_med
                    match_found = False
                    for drug_keyword in dangerous_drugs:
                        if drug_keyword in user_med or user_med in drug_keyword:
                            match_found = True
                            break
                    
                    if match_found:
                        warnings.append({
                            'herb': herb,
                            'medication': user_med,
                            'severity': interaction_info['severity'],
                            'reason': interaction_info['reason'],
                            'alternatives': interaction_info['alternatives'],
                        })
                        
        return warnings

# =============================================================================
# SECTION 3: ENTITY EXTRACTION & CONTEXT MANAGER
# =============================================================================

class ContextManager:
    """
    Handles extraction of medical entities from text and manages conversation context.
    """
    
    # Detailed keyword maps for extraction
    CONDITION_KEYWORDS = {
        'headache': ['headache', 'head hurts', 'head pain', 'head ache', 'migraine', 'cluster headache'],
        'fever': ['fever', 'temperature', 'feverish', 'high temperature', 'pyrexia', 'chills'],
        'cold': ['cold', 'runny nose', 'sneezing', 'stuffy nose', 'congestion', 'flu', 'influenza'],
        'cough': ['cough', 'coughing', 'dry cough', 'wet cough', 'phlegm', 'bronchitis'],
        'nausea': ['nausea', 'nauseous', 'feeling sick', 'queasy', 'want to vomit', 'vomiting', 'puking'],
        'indigestion': ['indigestion', 'bloating', 'gas', 'stomach upset', 'acidity', 'heartburn', 'acid reflux', 'gerd', 'stomach ache'],
        'sore_throat': ['sore throat', 'throat pain', 'throat hurts', 'scratchy throat', 'pain swallowing', 'strep'],
        'anxiety': ['anxiety', 'anxious', 'worried', 'nervous', 'panic', 'panic attack', 'gad'],
        'stress': ['stress', 'stressed', 'overwhelmed', 'tension', 'burnout', 'pressure'],
        'insomnia': ['insomnia', 'cant sleep', "can't sleep", 'trouble sleeping', 'sleepless', 'waking up'],
        'fatigue': ['fatigue', 'tired', 'exhausted', 'no energy', 'weakness', 'lethargy', 'drained'],
        'joint_pain': ['joint pain', 'arthritis', 'joints hurt', 'knee pain', 'joint ache', 'osteoarthritis', 'rheumatoid'],
        'back_pain': ['back pain', 'backache', 'back hurts', 'lower back', 'lumbago', 'sciatica'],
        'toothache': ['toothache', 'tooth pain', 'tooth hurts', 'dental pain', 'gum pain'],
        'acne': ['acne', 'pimples', 'breakout', 'zits', 'blemishes', 'spots'],
        'constipation': ['constipation', 'constipated', 'cant poop', 'hard stool'],
        'diarrhea': ['diarrhea', 'loose stools', 'upset stomach', 'runs', 'loose motions'],
        'diabetes': ['diabetes', 'high sugar', 'blood sugar', 'diabetic', 'glucose'],
        'hypertension': ['blood pressure', 'high bp', 'hypertension', 'pressure'],
        'hypothyroidism': ['thyroid', 'hypothyroid', 'hashimoto'],
        'pcos': ['pcos', 'pcod', 'polycystic'],
    }

    HERB_LIST = [
        'ginger', 'turmeric', 'peppermint', 'garlic', 'honey', 'tulsi', 'basil',
        'ashwagandha', 'chamomile', 'cinnamon', 'clove', 'licorice', 'ginseng',
        'valerian', 'neem', 'amla', 'fennel', 'cumin', 'coriander', 'fenugreek',
        'mint', 'lavender', 'eucalyptus', 'tea tree', 'aloe vera', 'coconut oil',
        'ginkgo', 'echinacea', 'elderberry', 'brahmi', 'giloy', 'triphala',
        'moringa', 'shatavari', 'ajwain', 'cardamom', 'black pepper', 'lemon balm',
        'passionflower', 'kava', 'st johns wort', 'nettle', 'dandelion', 'milk thistle'
    ]

    MEDICATION_KEYWORDS = {
        'aspirin': ['aspirin', 'disprin', 'ecosprin', 'acetylsalicylic'],
        'ibuprofen': ['ibuprofen', 'advil', 'motrin', 'brufen', 'nsaid'],
        'paracetamol': ['paracetamol', 'acetaminophen', 'tylenol', 'crocin', 'dolo', 'panadol'],
        'warfarin': ['warfarin', 'coumadin', 'jantoven'],
        'blood_thinner': ['blood thinner', 'blood thinners', 'anticoagulant', 'eliquis', 'xarelto', 'pradaxa'],
        'metformin': ['metformin', 'glycomet', 'glucophage', 'riomet'],
        'insulin': ['insulin', 'lantus', 'humalog', 'novolog'],
        'diabetes_med': ['diabetes medication', 'diabetes medicine', 'sugar medicine', 'glipizide', 'glyburide'],
        'bp_med': ['blood pressure medication', 'bp medicine', 'bp medication', 'antihypertensive', 'lisinopril', 'amlodipine', 'losartan'],
        'thyroid_med': ['thyroid', 'levothyroxine', 'synthroid', 'thyroxine', 'eltroxin', 'thyronorm'],
        'antidepressant': ['antidepressant', 'ssri', 'prozac', 'zoloft', 'lexapro', 'celexa', 'paxil', 'fluoxetine', 'sertraline'],
        'sedative': ['sedative', 'sleeping pill', 'sleep medication', 'benzodiazepine', 'xanax', 'valium', 'ativan', 'klonopin'],
        'statin': ['statin', 'atorvastatin', 'lipitor', 'rosuvastatin', 'crestor', 'cholesterol medicine'],
        'antacid': ['pan d', 'pantoprazole', 'pantop', 'ppi', 'omeprazole', 'omez', 'prilosec', 'nexium', 'antacid'],
        'antibiotic': ['antibiotic', 'amoxicillin', 'azithromycin', 'augmentin', 'cipro'],
    }

    @classmethod
    def extract_entities(cls, query: str) -> Dict[str, List[str]]:
        """
        Uses robust regex word boundary matching to extract medical entities.
        """
        q = query.lower()
        
        # 1. Conditions
        conditions = []
        for condition, keywords in cls.CONDITION_KEYWORDS.items():
            for keyword in keywords:
                # Regex check for word boundaries to avoid partial matches
                if re.search(r'\b' + re.escape(keyword) + r'\b', q):
                    if condition not in conditions:
                        conditions.append(condition)
                    break # Found this condition, move to next
        
        # 2. Herbs
        herbs = []
        for herb in cls.HERB_LIST:
            if re.search(r'\b' + re.escape(herb) + r'\b', q):
                herbs.append(herb)
                
        # 3. Medications
        medications = []
        for med_category, keywords in cls.MEDICATION_KEYWORDS.items():
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword) + r'\b', q):
                    # Store the specific keyword found, or the category?
                    # Storing category key helps with normalization, but keyword is more specific.
                    # We'll store the category key as a canonical representation.
                    if med_category not in medications:
                        medications.append(med_category)
                    break
                    
        return {
            'conditions': conditions,
            'herbs': herbs,
            'medications': medications
        }

# =============================================================================
# SECTION 4: MAIN PIPELINE EXECUTION
# =============================================================================

async def execute_rag_pipeline(
    query_in_english: str,
    input_language_detected: str,
    email_id: str,
    user_name: str = None,
    message_id: str = None,
    chat_history: List = None,
    user_profile: Dict = None,
) -> Tuple[Dict, Dict]:
    """
    Main Agentic RAG pipeline execution function.
    Orchestrates: Emergency Check -> Context Update -> Safety Check -> Retrieval -> Generation -> Verification.
    
    Args:
        query_in_english: The user's query translated to English.
        input_language_detected: Original language code.
        email_id: Unique user identifier.
        user_name: User's display name.
        message_id: Unique message ID.
        chat_history: List of previous messages.
        user_profile: Dictionary containing user health profile (meds, conditions, allergies).
        
    Returns:
        Tuple[Dict, Dict]: (response_map, message_data_update)
    """
    
    # Initialize timing and response structures
    response_map = {
        'intent': 'general',
        'trust_engine_verified': False,
        'verified_count': 0
    }
    
    original_query = query_in_english
    start_time = time.time()
    retrieval_start = datetime.now()
    retrieval_end = datetime.now()
    
    # -------------------------------------------------------------------------
    # STEP 0: LOGGING & INITIALIZATION
    # -------------------------------------------------------------------------
    logger.info("=" * 80)
    logger.info(f"🚀 ServVia 2.1 Pipeline Started | ID: {message_id}")
    logger.info(f"👤 User: {email_id} ({user_name})")
    logger.info(f"📝 Query: {original_query}")
    logger.info("=" * 80)
    
    # Extract profile data safely
    profile_allergies = []
    profile_conditions = []
    profile_medications = []
    
    if user_profile:
        profile_allergies = user_profile.get('allergies', []) or []
        profile_conditions = user_profile.get('medical_conditions', []) or []
        profile_medications = user_profile.get('current_medications', []) or []
        
    logger.info(f"📋 Profile - Meds: {profile_medications}, Allergies: {profile_allergies}")

    # -------------------------------------------------------------------------
    # STEP 1: EMERGENCY DETECTION (Safety Layer 1)
    # -------------------------------------------------------------------------
    try:
        emergency_type = EmergencySystem.detect_intent(original_query)
        
        if emergency_type:
            logger.critical(f"🚨 EMERGENCY DETECTED: {emergency_type}")
            
            # Fetch hardcoded protocol
            emergency_response = EmergencySystem.get_response(emergency_type)
            
            # Finalize immediately
            response_map['generated_final_response'] = emergency_response
            response_map['intent'] = 'emergency'
            response_map['emergency_type'] = emergency_type
            
            message_data_update = {
                'message_id': message_id,
                'query': original_query,
                'response': emergency_response,
                'intent': 'emergency',
                'processing_time': time.time() - start_time
            }
            
            return response_map, message_data_update
            
    except Exception as e:
        logger.error(f"Error in Emergency Detection: {e}")
        # Continue to normal pipeline if detection fails (fail-open)

    # -------------------------------------------------------------------------
    # STEP 2: ENTITY EXTRACTION
    # -------------------------------------------------------------------------
    current_entities = ContextManager.extract_entities(original_query)
    logger.info(f"🔍 Extracted Entities: {current_entities}")

    # -------------------------------------------------------------------------
    # STEP 3: CONTEXT MANAGEMENT (Conversation History)
    # -------------------------------------------------------------------------
    context_changes = {'added': [], 'removed': []}
    accumulated_context = {'herbs': [], 'medications': [], 'conditions': []}
    history_text = ""
    
    if CONVERSATION_ENABLED and conversation_manager and email_id:
        try:
            # Update conversational state
            context_changes = conversation_manager.update_context(email_id, original_query)
            
            # TEMPORAL: Update medication timeline if temporal keywords detected
            conversation_manager.update_medication_timeline(email_id, original_query)
            
            # Add user message to history buffer
            conversation_manager.add_message(email_id, 'user', original_query)
            
            # Retrieve formatted history for LLM
            history_text = conversation_manager.get_formatted_history(email_id)
            
            # Get accumulated medical context
            accumulated_context = conversation_manager.get_context(email_id)
            
            if context_changes.get('added'):
                logger.info(f"➕ Context Added: {context_changes['added']}")
            if context_changes.get('removed'):
                logger.info(f"➖ Context Removed: {context_changes['removed']}")
                
        except Exception as e:
            logger.error(f"Context Management Error: {e}")

    # -------------------------------------------------------------------------
    # STEP 4: MERGE CONTEXT & DETERMINE ACTIVE STATE
    # -------------------------------------------------------------------------
    # Stopped meds logic (if user says "I stopped taking aspirin")
    stopped_medications = []
    if context_changes.get('removed'):
        stopped_medications = [
            r.replace('medication: ', '').lower().strip() 
            for r in context_changes['removed'] if 'medication:' in r
        ]

    # Combine profile + history + current query entities
    # Herbs
    all_herbs = list(set(
        accumulated_context.get('herbs', []) + 
        current_entities['herbs']
    ))
    
    # Medications (Filter out stopped ones)
    raw_meds = set(
        accumulated_context.get('medications', []) + 
        current_entities['medications'] + 
        profile_medications
    )
    all_medications = [m for m in raw_meds if m.lower() not in stopped_medications]
    
    # Conditions
    all_conditions = list(set(
        accumulated_context.get('conditions', []) + 
        current_entities['conditions'] +
        profile_conditions
    ))
    
    # Determine PRIMARY condition focus
    current_condition = "general health"
    if current_entities['conditions']:
        current_condition = current_entities['conditions'][0]
    elif all_conditions:
        current_condition = all_conditions[-1] # Most recent
        
    logger.info(f"🧠 Active Context | Cond: {current_condition} | Meds: {all_medications} | Herbs: {all_herbs}")

    # -------------------------------------------------------------------------
    # STEP 5: SAFETY GRID CHECK (Pre-Generation Interactions)
    # -------------------------------------------------------------------------
    interaction_warnings = []
    safety_instructions = ""
    
    if all_herbs and all_medications:
        interaction_warnings = InteractionDatabase.check_interactions(all_herbs, all_medications)
        
        if interaction_warnings:
            logger.warning(f"⚠️ {len(interaction_warnings)} Interaction(s) Detected!")
            
            safety_instructions = "\n\n🚨 **CRITICAL SAFETY CONSTRAINTS (MUST FOLLOW):**\n"
            
            for w in interaction_warnings:
                safety_instructions += f"""
- **INTERACTION ALERT ({w['severity']})**: User takes '{w['medication']}'.
  - **DO NOT RECOMMEND**: {w['herb'].upper()}
  - **RISK**: {w['reason']}
  - **SUGGEST ALTERNATIVE**: {', '.join(w['alternatives'])} instead.
"""

    # -------------------------------------------------------------------------
    # STEP 6: QUERY REPHRASING
    # -------------------------------------------------------------------------
    rephrased_query = original_query
    if SERVICES_AVAILABLE:
        try:
            rephrased_query = await rephrase_query(original_query, chat_history or [])
            logger.info(f"🔄 Rephrased Query: {rephrased_query}")
        except Exception as e:
            logger.warning(f"Rephrasing failed: {e}")

    # -------------------------------------------------------------------------
    # STEP 7: KNOWLEDGE RETRIEVAL (RAG)
    # -------------------------------------------------------------------------
    context_chunks = ""
    chunks_list = []
    
    if SERVICES_AVAILABLE:
        try:
            retrieval_start = datetime.now()
            retrieved = retrieve_content(rephrased_query, email_id, top_k=6)
            retrieval_end = datetime.now()
            
            if retrieved:
                chunks_list = retrieved.get('chunks', [])
                # Format chunks for LLM
                chunk_texts = [
                    c.get('text', '') or c.get('content', '') or str(c) 
                    for c in chunks_list
                ]
                context_chunks = "\n\n".join(chunk_texts)
                logger.info(f"📚 Retrieved {len(chunks_list)} knowledge chunks")
                
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")

    # -------------------------------------------------------------------------
    # STEP 8: RETURN RAG CONTEXT (Multi-Agent pipeline runs in views.py)
    # -------------------------------------------------------------------------
    # The Multi-Agent pipeline (Diagnostician → Proposer → Critic) runs in
    # views.py. This function returns ONLY the raw RAG context chunks.
    # These are passed as rag_context to the Proposer — NEVER shown to user.
    llm_response = context_chunks if context_chunks else ""
    generated_meta = {}
    logger.info(f"RAG context ready: {len(llm_response)} chars from {len(chunks_list)} chunks")

    # Save user query to history (assistant response saved after multi-agent in views.py)
    if CONVERSATION_ENABLED and conversation_manager and email_id:
        conversation_manager.add_message(email_id, 'user', original_query)

    # -------------------------------------------------------------------------
    # STEP 9: FINALIZATION — return raw context for multi-agent pipeline
    # -------------------------------------------------------------------------
    response_map['generated_final_response'] = llm_response
    response_map['rag_context'] = llm_response
    response_map['retrieval_start'] = retrieval_start
    response_map['retrieval_end'] = retrieval_end
    
    # Message update payload for DB/Frontend
    message_data_update = {
        'message_id': message_id,
        'query': original_query,
        'rephrased_query': rephrased_query,
        'response': llm_response,
        'chunks_retrieved': len(chunks_list),
        'current_condition': current_condition,
        'processing_time': time.time() - start_time,
        'token_usage': generated_meta
    }
    
    logger.info(f"✅ Pipeline Complete ({time.time() - start_time:.2f}s)")
    return response_map, message_data_update

# =============================================================================
# ENTRY POINT (TEST RUNNER)
# =============================================================================
if __name__ == "__main__":
    # Simulate a run
    print("--- ServVia 2.1 Monolith Test ---")
    
    test_profile = {
        'current_medications': ['Warfarin', 'Metformin'],
        'allergies': ['Peanuts'],
        'medical_conditions': ['Diabetes']
    }
    
    test_query = "I have a bad headache and nausea. Can I take ginger?"
    
    loop = asyncio.get_event_loop()
    result_map, meta_data = loop.run_until_complete(
        execute_rag_pipeline(
            query_in_english=test_query,
            input_language_detected="en",
            email_id="test_user_123",
            user_name="Ayaan",
            message_id="msg_001",
            user_profile=test_profile
        )
    )
    
    print("\n--- FINAL RESPONSE ---")
    print(result_map['generated_final_response'])
