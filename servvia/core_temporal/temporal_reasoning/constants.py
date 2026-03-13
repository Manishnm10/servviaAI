"""
ServVia Temporal Reasoning Constants

Clinical temporal rules for pharmacovigilance.
These constants define safety windows, washout periods, and acuity thresholds
used in temporal neurosymbolic reasoning.

Sources:
- Medication stabilization: Clinical pharmacology guidelines (typically 5 half-lives)
- Herb washout: FDA dietary supplement guidelines, clinical herb-drug interaction literature
- Symptom acuity: Medical diagnosis standards (ICD-11, DSM-5)
"""

from enum import Enum


class InteractionTiming(Enum):
    """
    Timing classification for drug-herb interactions.
    Defines when interactions occur relative to administration.
    """
    IMMEDIATE = "immediate"              # Within 1 hour
    DELAYED_1HR = "delayed_1hr"          # 1-4 hours
    DELAYED_4HR = "delayed_4hr"          # 4-12 hours
    DELAYED_12HR = "delayed_12hr"        # 12-24 hours
    CUMULATIVE = "cumulative"            # Builds up over days/weeks
    TIME_DEPENDENT = "time_dependent"    # Specific time of day (e.g., morning)


class AcuityClassification(Enum):
    """Standard medical acuity classifications based on duration."""
    ACUTE = "acute"                      # < 7 days
    SUBACUTE = "subacute"                # 7-30 days
    CHRONIC = "chronic"                  # > 30 days


# =============================================================================
# MEDICATION STABILIZATION PERIODS (in days)
# =============================================================================
# Time required for medication to reach steady-state and stable therapeutic effect
# Before introducing herbs that may interact

MEDICATION_STABILIZATION_PERIODS = {
    # Cardiovascular medications
    'warfarin': 14,                      # INR stabilization critical
    'blood_thinner': 14,
    'anticoagulant': 14,
    'aspirin': 7,                        # Platelet turnover
    'bp_medication': 14,                 # Blood pressure stabilization
    'antihypertensive': 14,
    'lisinopril': 14,
    'amlodipine': 14,
    'metoprolol': 7,
    'statin': 14,                        # Cholesterol effects take time
    'atorvastatin': 14,
    
    # Diabetes medications
    'insulin': 7,                        # Dose titration period
    'metformin': 7,
    'diabetes_medication': 14,
    'glipizide': 7,
    'glyburide': 7,
    
    # Psychiatric medications
    'ssri': 21,                          # Serotonin system adaptation
    'antidepressant': 21,
    'prozac': 21,
    'zoloft': 14,
    'sertraline': 14,
    'fluoxetine': 28,                    # Long half-life
    'benzodiazepine': 7,
    'sedative': 7,
    'xanax': 7,
    'valium': 7,
    'antipsychotic': 14,
    
    # Thyroid medications
    'levothyroxine': 42,                 # TSH normalization takes 6 weeks
    'thyroid_medication': 42,
    'synthroid': 42,
    
    # Immune/Autoimmune medications
    'immunosuppressant': 14,
    'cyclosporine': 14,
    'methotrexate': 14,
    'corticosteroid': 7,
    'prednisone': 7,
    
    # Default for unspecified medications
    'default': 14,
}


# =============================================================================
# HERB WASHOUT PERIODS (in days)
# =============================================================================
# Time herbs must be cleared from system before starting contraindicated meds
# Critical for preventing dangerous interactions

HERB_WASHOUT_PERIODS = {
    # Critical interactions - Serotonin syndrome risk
    'st_johns_wort': 14,                 # CYP3A4 induction persists
    'hypericum': 14,
    
    # Blood thinning herbs
    'ginkgo': 7,                         # Platelet effects
    'ginger': 3,                        # Mild antiplatelet
    'turmeric': 7,                       # Curcumin half-life + safety margin
    'curcumin': 7,
    'garlic': 7,                         # Allicin compounds
    'ginseng': 3,
    'kava': 7,                          # Hepatotoxicity concerns
    
    # Thyroid-affecting herbs
    'ashwagandha': 7,                    # Thyroid hormone effects
    'withania': 7,
    
    # Immune modulators
    'echinacea': 3,
    
    # Sedative herbs
    'valerian': 3,                       # GABA effects clear quickly
    'kava_kava': 7,
    
    # Default washout period
    'default': 3,
}


# =============================================================================
# SYMPTOM ACUITY THRESHOLDS (in days)
# =============================================================================
# Defines acute vs subacute vs chronic based on symptom duration
# Influences remedy eligibility and safety protocols

SYMPTOM_ACUITY_THRESHOLDS = {
    'acute': {
        'max_days': 7,
        'description': 'Rapid onset, short duration',
        'clinical_implications': [
            'Higher priority for immediate relief',
            'May indicate acute infection or injury',
            'Herbs for acute symptoms only',
            'Monitor for worsening',
        ]
    },
    'subacute': {
        'min_days': 7,
        'max_days': 30,
        'description': 'Persistent but not chronic',
        'clinical_implications': [
            'Transition phase - monitor closely',
            'May respond to moderate interventions',
            'Evaluate for underlying causes',
        ]
    },
    'chronic': {
        'min_days': 30,
        'description': 'Long-standing condition',
        'clinical_implications': [
            'Requires sustained management approach',
            'May need combination therapies',
            'Monitor for medication accumulation',
            'Consider drug-herb cumulative effects',
        ]
    },
}


# =============================================================================
# INTERACTION TIME WINDOWS
# =============================================================================
# Specific time windows for dangerous interactions
# Format: (herb_category, medication_category, timing_type, window_description)

INTERACTION_TIME_WINDOWS = {
    # St. John's Wort + SSRIs = Serotonin Syndrome
    ('st_johns_wort', 'ssri'): {
        'timing': InteractionTiming.CUMULATIVE,
        'danger_window': 'Concurrent use or within 14 days of SJW discontinuation',
        'severity': 'CRITICAL',
        'mechanism': 'Dual serotonin enhancement + CYP450 induction',
    },
    
    # Blood thinners + antiplatelet herbs
    ('warfarin', 'ginger'): {
        'timing': InteractionTiming.CUMULATIVE,
        'danger_window': 'Ongoing concurrent use',
        'severity': 'HIGH',
        'mechanism': 'Additive anticoagulant effects',
    },
    ('warfarin', 'turmeric'): {
        'timing': InteractionTiming.CUMULATIVE,
        'danger_window': 'Ongoing concurrent use',
        'severity': 'HIGH',
        'mechanism': 'Curcumin affects platelet function and may alter INR',
    },
    ('warfarin', 'ginkgo'): {
        'timing': InteractionTiming.IMMEDIATE,
        'danger_window': 'Within 4 hours of dose',
        'severity': 'CRITICAL',
        'mechanism': 'Platelet activating factor inhibition',
    },
    
    # Thyroid medications + ashwagandha
    ('levothyroxine', 'ashwagandha'): {
        'timing': InteractionTiming.TIME_DEPENDENT,
        'danger_window': 'Morning dosing interaction',
        'severity': 'HIGH',
        'mechanism': 'Ashwagandha stimulates T3/T4 production',
        'recommendation': 'Separate by 4+ hours',
    },
    
    # Sedatives + valerian/kava
    ('benzodiazepine', 'valerian'): {
        'timing': InteractionTiming.IMMEDIATE,
        'danger_window': 'Concurrent CNS depression',
        'severity': 'HIGH',
        'mechanism': 'Additive GABAergic effects',
    },
    ('benzodiazepine', 'kava'): {
        'timing': InteractionTiming.IMMEDIATE,
        'danger_window': 'Concurrent CNS depression',
        'severity': 'CRITICAL',
        'mechanism': 'Dual GABA modulation + hepatotoxicity risk',
    },
}


# =============================================================================
# CROSS-REACTIVITY WINDOWS (in days)
# =============================================================================
# Time windows for related allergen cross-reactivity concerns

CROSS_REACTIVITY_WINDOWS = {
    # Food allergies
    'ragweed': {
        'cross_reactive': ['chamomile', 'echinacea', 'milk_thistle'],
        'window_days': 30,
        'mechanism': 'Shared Asteraceae family proteins',
    },
    'mugwort': {
        'cross_reactive': ['chamomile', 'yarrow', 'tansy'],
        'window_days': 30,
        'mechanism': 'Shared Artemisia family compounds',
    },
    'birch_pollen': {
        'cross_reactive': ['apple', 'carrot', 'celery', 'hazelnut'],
        'window_days': 30,
        'mechanism': 'Oral allergy syndrome (Birch-fruit cross-reactivity)',
    },
    'latex': {
        'cross_reactive': ['banana', 'avocado', 'kiwi', 'chestnut'],
        'window_days': 365,  # Lifelong caution
        'mechanism': 'Hevein protein cross-reactivity',
    },
}


# =============================================================================
# MINIMUM SAFETY INTERVALS (in hours)
# =============================================================================
# Minimum time separation between incompatible substances

MINIMUM_SAFETY_INTERVALS = {
    # Herb-medication timing separations
    'thyroid_meds_herbs': 4,             # Hours between levothyroxine and herbs
    'iron_calcium': 2,                   # Iron and calcium compete for absorption
    'antibiotics_probiotics': 2,         # Antibiotics kill probiotic bacteria
    
    # Default safety buffer
    'default_separation': 2,
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_stabilization_period(medication_name: str) -> int:
    """Get the required stabilization period for a medication in days."""
    med_lower = medication_name.lower().replace(' ', '_')
    return MEDICATION_STABILIZATION_PERIODS.get(
        med_lower, 
        MEDICATION_STABILIZATION_PERIODS['default']
    )


def get_washout_period(herb_name: str) -> int:
    """Get the required washout period for an herb in days."""
    herb_lower = herb_name.lower().replace(' ', '_').replace('-', '_')
    return HERB_WASHOUT_PERIODS.get(
        herb_lower,
        HERB_WASHOUT_PERIODS['default']
    )


def classify_acuity(days: int) -> str:
    """Classify symptom acuity based on duration in days."""
    if days < SYMPTOM_ACUITY_THRESHOLDS['acute']['max_days']:
        return AcuityClassification.ACUTE.value
    elif days <= SYMPTOM_ACUITY_THRESHOLDS['subacute']['max_days']:
        return AcuityClassification.SUBACUTE.value
    else:
        return AcuityClassification.CHRONIC.value


def get_interaction_timing(herb: str, medication: str) -> dict:
    """Get timing information for a specific herb-drug interaction."""
    herb_lower = herb.lower().replace(' ', '_')
    med_lower = medication.lower().replace(' ', '_')
    
    # Check direct match
    key = (herb_lower, med_lower)
    if key in INTERACTION_TIME_WINDOWS:
        return INTERACTION_TIME_WINDOWS[key]
    
    # Check reverse (medication, herb)
    reverse_key = (med_lower, herb_lower)
    if reverse_key in INTERACTION_TIME_WINDOWS:
        return INTERACTION_TIME_WINDOWS[reverse_key]
    
    return None


def get_cross_reactive_allergens(allergen: str) -> dict:
    """Get cross-reactive herbs/allergens for a given allergen."""
    allergen_lower = allergen.lower().replace(' ', '_')
    return CROSS_REACTIVITY_WINDOWS.get(allergen_lower, None)
