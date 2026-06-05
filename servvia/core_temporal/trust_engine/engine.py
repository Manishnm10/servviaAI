"""
ServVia Trust Engine v2.1 (Monolith Production Build)
=====================================================
Neuro-Symbolic Verification System for Medical Recommendations

This module contains the complete logic AND the full medical knowledge base.
It is designed to be a self-contained "Drop-in" replacement.

Standards:
- Evidence-based validation (GRADE)
- PubMed citation tracking
- Interaction & Contraindication safety layers
- No external database dependencies (Data is embedded)

Author: ServVia Team
Version: 2.1.0
Last Updated: 2025-12-16
"""

import json
import logging
import re
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum
from asgiref.sync import sync_to_async

# Import temporal reasoning engine for pharmacovigilance
try:
    from core_temporal.temporal_reasoning.engine import get_temporal_engine
    TEMPORAL_ENGINE_AVAILABLE = True
except ImportError:
    TEMPORAL_ENGINE_AVAILABLE = False
    logging.warning("Temporal Reasoning Engine not available - temporal safety checks disabled")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ServVia_TrustEngine")


class EvidenceLevel(Enum):
    """Evidence quality levels based on GRADE standards"""
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    LOW_TO_MODERATE = "low_to_moderate"
    VERY_LOW = "very_low"
    INSUFFICIENT = "insufficient"


class InteractionSeverity(Enum):
    """Drug-herb interaction severity levels"""
    CRITICAL = "critical"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    NONE = "none"


@dataclass
class Citation:
    """Represents a single PubMed citation"""
    pmid: str
    title: str
    authors: str
    journal: str
    year: int
    study_type: str
    conclusion: str
    sample_size: str = ""
    
    def format(self, index: int = 1) -> str:
        """Format citation with PubMed link"""
        cite = f"{index}. {self.authors}. \"{self.title}.\" *{self.journal}* ({self.year}). "
        cite += f"[PMID: {self.pmid}](https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/)"
        if self.study_type:
            cite += f" **[{self.study_type}]**"
        return cite


@dataclass
class ValidationResult:
    """Complete validation result for a response"""
    is_safe: bool
    verified_herbs: List[str]
    unverified_herbs: List[str]
    warnings: List[str]
    contraindicated_herbs: List[str]
    interaction_warnings: List[str]
    evidence_summaries: Dict[str, str]
    formatted_output: str
    # TEMPORAL SAFETY FIELDS - Added for Objective 1
    temporal_safety_blocked: bool = False
    temporal_violations: List[str] = field(default_factory=list)
    temporal_recommendations: List[str] = field(default_factory=list)


class TrustEngine:
    """
    ServVia Trust Engine v2.1 - Monolithic Edition
    
    Provides evidence-based validation following medical communication standards.
    Contains embedded knowledge base to remove external dependencies.
    """
    
    # Uncertainty language based on evidence level
    UNCERTAINTY_LANGUAGE = {
        'high': 'Evidence from multiple high-quality studies suggests',
        'moderate': 'Some evidence from clinical studies suggests',
        'low_to_moderate': 'Some limited evidence suggests',
        'low': 'Limited evidence suggests',
        'very_low': 'Preliminary evidence suggests',
        'insufficient': 'Insufficient evidence exists to determine whether'
    }
    
    # GRADE certainty symbols
    GRADE_SYMBOLS = {
        'high': '⊕⊕⊕⊕',
        'moderate': '⊕⊕⊕○',
        'low_to_moderate': '⊕⊕⊕○',
        'low': '⊕⊕○○',
        'very_low': '⊕○○○',
        'insufficient': '○○○○'
    }
    
    def __init__(self):
        """Initialize Trust Engine and load embedded database"""
        self.evidence_data = {}
        self.known_herbs = set()
        self.condition_map = self._build_condition_map()
        
        # Load the embedded database
        self._load_embedded_database()
        self._build_herb_registry()
        
        logger.info(f"Trust Engine initialized: {len(self.evidence_data.get('evidence', []))} evidence entries, "
                    f"{len(self.known_herbs)} known herbs")

    async def validate_temporal_safety(
        self,
        user_id: str,
        herbs: List[str],
        symptom_descriptions: Optional[List[str]] = None
    ) -> Dict:
        """
        ASYNC: Validate herb recommendations against temporal safety constraints.
        
        Checks medication stabilization periods, washout periods, and symptom acuity.
        This is the neurosymbolic safety gate that runs BEFORE LLM generation.
        
        Args:
            user_id: User email identifier
            herbs: List of herbs being recommended
            symptom_descriptions: Optional list of symptoms to check acuity
            
        Returns:
            Dict with safety status and any violations
        """
        if not TEMPORAL_ENGINE_AVAILABLE:
            logger.warning("Temporal engine not available, skipping temporal validation")
            return {
                'is_safe': True,
                'blocked': False,
                'violations': [],
                'recommendations': []
            }
        
        temporal_engine = get_temporal_engine()
        all_violations = []
        all_recommendations = []
        is_blocked = False
        
        logger.info(f"Validating temporal safety for {len(herbs)} herbs for user {user_id[:20]}...")
        
        for herb in herbs:
            result = await temporal_engine.validate_safety_profile(
                user_id=user_id,
                herb_name=herb,
                symptom_descriptions=symptom_descriptions
            )
            
            # Check for violations that should block recommendations
            # ANY stabilization violation (not just critical) should block
            stabilization_violations = result.stabilization_violations
            washout_violations = result.washout_violations
            
            if stabilization_violations or washout_violations:
                is_blocked = True
                for v in stabilization_violations:
                    all_violations.append(
                        f"🚫 BLOCKED: {herb.title()} + {v['medication']} - "
                        f"Critical interaction risk. Medication started {v['days_ago']} days ago, "
                        f"requires {v['required_days']} days stabilization. {v.get('risk_description', 'Interaction risk')}"
                    )
                
                for v in washout_violations:
                    all_violations.append(
                        f"🚫 BLOCKED: {herb.title()} + {v['medication']} (stopped {v['days_since_stop']} days ago) - "
                        f"Washout violation. Requires {v['required_washout']} days. {v.get('risk_description', 'Interaction risk persists during washout')}"
                    )
            
            # Collect all warnings and recommendations
            all_violations.extend(result.warnings)
            all_recommendations.extend(result.safety_recommendations)
        
        return {
            'is_safe': len(all_violations) == 0,
            'blocked': is_blocked,
            'violations': all_violations,
            'recommendations': all_recommendations
        }

    def _build_condition_map(self) -> Dict[str, List[str]]:
        """Builds a map for identifying conditions from user queries"""
        return {
            'headache': ['headache', 'head hurts', 'head pain', 'migraine', 'migranes'],
            'fever': ['fever', 'temperature', 'feverish', 'pyrexia'],
            'cold': ['cold', 'runny nose', 'sneezing', 'flu', 'upper respiratory', 'congestion'],
            'cough': ['cough', 'coughing', 'bronchitis'],
            'nausea': ['nausea', 'nauseous', 'vomiting', 'morning sickness', 'motion sickness'],
            'indigestion': ['indigestion', 'bloating', 'gas', 'acidity', 'digestive', 'stomach ache', 'heartburn', 'gerd'],
            'sore_throat': ['sore throat', 'throat pain', 'pharyngitis', 'strep'],
            'anxiety': ['anxiety', 'anxious', 'worried', 'nervous', 'panic', 'gad'],
            'stress': ['stress', 'stressed', 'overwhelmed', 'tension'],
            'insomnia': ['insomnia', 'cant sleep', 'sleep problem', 'wake up', 'sleepless'],
            'depression': ['depression', 'depressed', 'sad', 'mood', 'dysthymia'],
            'hypertension': ['blood pressure', 'hypertension', 'bp', 'high blood pressure'],
            'burns': ['burn', 'burnt', 'scalded', 'sunburn'],
            'uti': ['uti', 'urinary', 'bladder infection', 'cystitis'],
            'arthritis': ['arthritis', 'joint pain', 'osteoarthritis', 'rheumatoid'],
            'acne': ['acne', 'pimples', 'zits', 'breakout']
        }

    def _load_embedded_database(self):
        """
        Loads the massive embedded dictionary containing all medical evidence.
        This replaces the external JSON file loader.
        """
        self.evidence_data = {
            "version": "2.1.0",
            "last_updated": "2025-12-16",
            "citation_standard": "PubMed",
            "evidence": [
                # =================================================================
                # RESPIRATORY CONDITIONS (Cough, Cold, Sore Throat)
                # =================================================================
                {
                    "herb": "honey",
                    "herb_aliases": ["raw honey", "manuka honey"],
                    "condition": "cough",
                    "condition_aliases": ["acute cough", "upper respiratory infection"],
                    "evidence_level": "moderate",
                    "summary": "May reduce cough frequency and severity in children >1 year old compared to placebo.",
                    "detailed_summary": "A Cochrane systematic review found honey probably reduces cough symptoms more than placebo and salbutamol.",
                    "limitations": ["Small sample sizes", "Not for infants <12mo", "Variable honey types"],
                    "citations": [
                        {
                            "pmid": "29633783", "title": "Honey for acute cough in children", "authors": "Oduwole O, et al.",
                            "journal": "Cochrane Database Syst Rev", "year": 2018, "study_type": "Meta-analysis",
                            "conclusion": "Honey reduces cough symptoms more than placebo."
                        },
                        {
                            "pmid": "22869830", "title": "Effect of honey on nocturnal cough", "authors": "Cohen HA, et al.",
                            "journal": "Pediatrics", "year": 2012, "study_type": "RCT",
                            "conclusion": "Honey was significantly superior to placebo."
                        }
                    ],
                    "safety_notes": ["CONTRAINDICATED in infants <12 months (botulism risk)", "Affects blood sugar"],
                    "contraindications": ["Infants under 12 months", "Diabetes (monitor)"],
                    "interactions": [],
                    "dosing": {"children": "2.5-5ml before bed", "adults": "10-15ml before bed"},
                    "recommendation_strength": "conditional",
                    "grade_assessment": "⊕⊕⊕○"
                },
                {
                    "herb": "ginger",
                    "herb_aliases": ["zingiber officinale", "ginger root"],
                    "condition": "sore_throat",
                    "evidence_level": "low",
                    "summary": "May have anti-inflammatory properties that help throat irritation, but direct clinical evidence is limited.",
                    "limitations": ["Most evidence is extrapolated from general inflammation studies", "Lack of direct RCTs"],
                    "citations": [
                        {
                            "pmid": "23123794", "title": "Anti-oxidative and anti-inflammatory effects of ginger", 
                            "authors": "Mashhadi NS, et al.", "journal": "Int J Prev Med", "year": 2013, 
                            "study_type": "Review", "conclusion": "Ginger shows potent anti-inflammatory properties."
                        }
                    ],
                    "safety_notes": ["May cause heartburn in high doses", "Blood thinning potential at high doses"],
                    "contraindications": ["Gallstones (consult doctor)", "Bleeding disorders"],
                    "interactions": [
                        {"substance": "Warfarin", "severity": "moderate", "description": "May increase bleeding risk (INR)"}
                    ],
                    "dosing": {"tea": "1-2g fresh root steeped"},
                    "recommendation_strength": "weak",
                    "grade_assessment": "⊕○○○"
                },
                {
                    "herb": "eucalyptus",
                    "herb_aliases": ["eucalyptus oil", "cineole"],
                    "condition": "cold",
                    "condition_aliases": ["congestion", "bronchitis", "sinusitis"],
                    "evidence_level": "low",
                    "summary": "Inhalation may provide symptomatic relief for congestion. Oral use is toxic unless pharmaceutical grade.",
                    "limitations": ["Safety concerns with oral use", "Small studies"],
                    "citations": [
                        {
                            "pmid": "20359267", "title": "Efficacy of cineole in acute bronchitis", "authors": "Fischer J, et al.",
                            "journal": "Cough", "year": 2013, "study_type": "RCT",
                            "conclusion": "Cineole significantly reduced cough frequency."
                        }
                    ],
                    "safety_notes": ["ORAL OIL IS TOXIC", "Do not apply near face of infants"],
                    "contraindications": ["Children <2 years", "Asthma (may trigger spasm)"],
                    "interactions": [],
                    "dosing": {"inhalation": "Steam inhalation only"},
                    "recommendation_strength": "weak",
                    "grade_assessment": "⊕○○○"
                },

                # =================================================================
                # DIGESTIVE CONDITIONS (Nausea, IBS, Indigestion)
                # =================================================================
                {
                    "herb": "ginger",
                    "herb_aliases": ["zingiber officinale"],
                    "condition": "nausea",
                    "condition_aliases": ["morning sickness", "chemotherapy nausea"],
                    "evidence_level": "high",
                    "summary": "Effective for pregnancy-induced and chemotherapy-induced nausea.",
                    "detailed_summary": "Multiple meta-analyses confirm efficacy superior to placebo for various forms of nausea.",
                    "citations": [
                        {
                            "pmid": "24390544", "title": "Ginger for nausea and vomiting in pregnancy", "authors": "Viljoen E, et al.",
                            "journal": "Nutr J", "year": 2014, "study_type": "Meta-analysis",
                            "conclusion": "Ginger is an effective non-pharmacological option."
                        }
                    ],
                    "safety_notes": ["Safe in pregnancy up to 1g/day", "Heartburn risk"],
                    "contraindications": ["Bleeding disorders", "Near surgery date"],
                    "interactions": [
                        {"substance": "Anticoagulants", "severity": "moderate", "description": "Additive bleeding risk"}
                    ],
                    "dosing": {"general": "1g daily in divided doses"},
                    "recommendation_strength": "strong",
                    "grade_assessment": "⊕⊕⊕⊕"
                },
                {
                    "herb": "peppermint",
                    "herb_aliases": ["mentha piperita", "peppermint oil"],
                    "condition": "indigestion",
                    "condition_aliases": ["ibs", "irritable bowel syndrome", "abdominal pain"],
                    "evidence_level": "moderate",
                    "summary": "Enteric-coated peppermint oil is effective for reducing IBS symptoms and abdominal pain.",
                    "limitations": ["Heartburn if not enteric-coated", "Variable study quality"],
                    "citations": [
                        {
                            "pmid": "30654773", "title": "Peppermint oil for IBS", "authors": "Alammar N, et al.",
                            "journal": "BMC Complement Altern Med", "year": 2019, "study_type": "Meta-analysis",
                            "conclusion": "Significantly more effective than placebo (NNT=3)."
                        }
                    ],
                    "safety_notes": ["Can worsen GERD/Heartburn", "Toxic in very high doses"],
                    "contraindications": ["Severe GERD", "Gallstones (caution)", "Children <8"],
                    "interactions": [
                        {"substance": "Cyclosporine", "severity": "moderate", "description": "May increase drug levels"},
                        {"substance": "Antacids", "severity": "minor", "description": "Dissolves enteric coating prematurely"}
                    ],
                    "dosing": {"ibs": "180-225mg enteric coated capsule 2x daily"},
                    "recommendation_strength": "conditional",
                    "grade_assessment": "⊕⊕⊕○"
                },

                # =================================================================
                # MENTAL HEALTH (Anxiety, Depression, Stress, Sleep)
                # =================================================================
                {
                    "herb": "ashwagandha",
                    "herb_aliases": ["withania somnifera", "indian ginseng"],
                    "condition": "stress",
                    "condition_aliases": ["anxiety", "cortisol"],
                    "evidence_level": "moderate",
                    "summary": "Standardized extracts likely reduce stress and anxiety levels compared to placebo.",
                    "detailed_summary": "RCTs show reduction in morning cortisol and HAM-A anxiety scores.",
                    "citations": [
                        {
                            "pmid": "31517876", "title": "Investigation into stress-relieving actions of ashwagandha", 
                            "authors": "Lopresti AL, et al.", "journal": "Medicine", "year": 2019, "study_type": "RCT",
                            "conclusion": "Significant reduction in cortisol and stress."
                        },
                        {
                            "pmid": "25405876", "title": "Systematic review of Withania somnifera for anxiety", 
                            "authors": "Pratte MA, et al.", "journal": "J Altern Complement Med", "year": 2014, "study_type": "Review",
                            "conclusion": "Improvement in anxiety/stress outcomes."
                        }
                    ],
                    "safety_notes": ["May cause drowsiness", "Thyroid stimulation"],
                    "contraindications": ["Pregnancy (abortifacient risk)", "Hyperthyroidism", "Autoimmune disease"],
                    "interactions": [
                        {"substance": "Thyroid medication", "severity": "major", "description": "Risk of thyrotoxicosis"},
                        {"substance": "Benzodiazepines", "severity": "moderate", "description": "Additive sedation"}
                    ],
                    "dosing": {"extract": "300-600mg standardized extract daily"},
                    "recommendation_strength": "conditional",
                    "grade_assessment": "⊕⊕⊕○"
                },
                {
                    "herb": "st johns wort",
                    "herb_aliases": ["hypericum perforatum"],
                    "condition": "depression",
                    "condition_aliases": ["mild depression", "mood"],
                    "evidence_level": "high",
                    "summary": "Effective for mild-moderate depression but has CRITICAL drug interactions.",
                    "detailed_summary": "Comparable to SSRIs for mild depression with fewer side effects, but induces CYP3A4 enzymes strongly.",
                    "limitations": ["Not for severe depression", "Dangerous interaction profile"],
                    "citations": [
                        {
                            "pmid": "18843608", "title": "St. John's wort for major depression", "authors": "Linde K, et al.",
                            "journal": "Cochrane Database Syst Rev", "year": 2008, "study_type": "Meta-analysis",
                            "conclusion": "Superior to placebo, similar to standard antidepressants."
                        }
                    ],
                    "safety_notes": ["Photosensitivity", "Serotonin syndrome risk"],
                    "contraindications": ["Severe depression", "Taking ANY prescription meds (check first)", "Bipolar"],
                    "interactions": [
                        {"substance": "SSRIs", "severity": "critical", "description": "Serotonin Syndrome risk"},
                        {"substance": "Birth Control", "severity": "major", "description": "Causes failure of contraception"},
                        {"substance": "Warfarin", "severity": "major", "description": "Reduces efficacy"},
                        {"substance": "Cyclosporine", "severity": "critical", "description": "Organ rejection risk"}
                    ],
                    "dosing": {"standard": "300mg (0.3% hypericin) 3x daily"},
                    "recommendation_strength": "conditional",
                    "grade_assessment": "⊕⊕⊕⊕"
                },
                {
                    "herb": "valerian",
                    "herb_aliases": ["valeriana officinalis"],
                    "condition": "insomnia",
                    "condition_aliases": ["sleep", "sleeplessness"],
                    "evidence_level": "low_to_moderate",
                    "summary": "May improve subjective sleep quality, but objective data is inconsistent.",
                    "citations": [
                        {
                            "pmid": "17145239", "title": "Valerian for sleep", "authors": "Bent S, et al.",
                            "journal": "Am J Med", "year": 2006, "study_type": "Meta-analysis",
                            "conclusion": "Improvement in sleep quality noted."
                        }
                    ],
                    "safety_notes": ["Morning grogginess", "Liver toxicity (rare/idiosyncratic)"],
                    "contraindications": ["Pregnancy", "Operating heavy machinery"],
                    "interactions": [
                        {"substance": "Alcohol", "severity": "moderate", "description": "Additive CNS depression"},
                        {"substance": "Sedatives", "severity": "moderate", "description": "Additive sedation"}
                    ],
                    "dosing": {"extract": "300-600mg 1 hour before bed"},
                    "recommendation_strength": "conditional",
                    "grade_assessment": "⊕⊕○○"
                },
                {
                    "herb": "chamomile",
                    "herb_aliases": ["matricaria chamomilla"],
                    "condition": "anxiety",
                    "condition_aliases": ["sleep", "relaxation"],
                    "evidence_level": "moderate",
                    "summary": "Modest evidence for Generalized Anxiety Disorder (GAD) and sleep quality.",
                    "citations": [
                        {
                            "pmid": "27912871", "title": "Long-term chamomile therapy of GAD", "authors": "Mao JJ, et al.",
                            "journal": "Phytomedicine", "year": 2016, "study_type": "RCT",
                            "conclusion": "Significantly reduced GAD symptoms."
                        }
                    ],
                    "safety_notes": ["Allergy risk (Ragweed family)"],
                    "contraindications": ["Ragweed allergy"],
                    "interactions": [
                        {"substance": "Warfarin", "severity": "minor", "description": "Theoretical bleeding risk"}
                    ],
                    "dosing": {"extract": "500mg extract or strong tea"},
                    "recommendation_strength": "weak",
                    "grade_assessment": "⊕⊕○○"
                },

                # =================================================================
                # CARDIOVASCULAR (Hypertension)
                # =================================================================
                {
                    "herb": "garlic",
                    "herb_aliases": ["allium sativum", "aged garlic extract"],
                    "condition": "hypertension",
                    "condition_aliases": ["high blood pressure"],
                    "evidence_level": "moderate",
                    "summary": "Aged garlic extract may lower systolic BP by 7-10 mmHg.",
                    "citations": [
                        {
                            "pmid": "26764326", "title": "Garlic for cardiovascular disease risk", "authors": "Varshney R, et al.",
                            "journal": "J Nutr", "year": 2016, "study_type": "Meta-analysis",
                            "conclusion": "Consistent reduction in blood pressure."
                        }
                    ],
                    "safety_notes": ["Bleeding risk", "GI upset"],
                    "contraindications": ["Surgery within 2 weeks", "Bleeding disorders"],
                    "interactions": [
                        {"substance": "Warfarin", "severity": "major", "description": "Increases INR/bleeding"},
                        {"substance": "Protease inhibitors", "severity": "moderate", "description": "Reduces drug levels"}
                    ],
                    "dosing": {"AGE": "600-1200mg daily"},
                    "recommendation_strength": "conditional",
                    "grade_assessment": "⊕⊕⊕○"
                },

                # =================================================================
                # PAIN & INFLAMMATION (Arthritis, Joint Pain)
                # =================================================================
                {
                    "herb": "turmeric",
                    "herb_aliases": ["curcuma longa", "curcumin"],
                    "condition": "arthritis",
                    "condition_aliases": ["joint pain", "inflammation", "osteoarthritis"],
                    "evidence_level": "moderate",
                    "summary": "Curcumin extracts show efficacy similar to NSAIDs for osteoarthritis pain.",
                    "limitations": ["Poor bioavailability of raw spice", "Short term studies"],
                    "citations": [
                        {
                            "pmid": "25402637", "title": "Efficacy of Turmeric for Arthritis", "authors": "Daily JW, et al.",
                            "journal": "J Med Food", "year": 2016, "study_type": "Meta-analysis",
                            "conclusion": "Reduced arthritis symptoms similar to ibuprofen."
                        }
                    ],
                    "safety_notes": ["Gallbladder contraction", "Bleeding risk"],
                    "contraindications": ["Gallstones", "Bile duct obstruction", "Surgery"],
                    "interactions": [
                        {"substance": "Warfarin", "severity": "moderate", "description": "Increases bleeding risk"},
                        {"substance": "Chemotherapy", "severity": "moderate", "description": "May interfere with some drugs"}
                    ],
                    "dosing": {"extract": "500-1000mg curcumin with piperine"},
                    "recommendation_strength": "conditional",
                    "grade_assessment": "⊕⊕⊕○"
                },

                # =================================================================
                # SKIN (Burns, Acne)
                # =================================================================
                {
                    "herb": "aloe vera",
                    "herb_aliases": ["aloe barbadensis"],
                    "condition": "burns",
                    "condition_aliases": ["sunburn", "thermal burns"],
                    "evidence_level": "moderate",
                    "summary": "Accelerates healing of first and second-degree burns.",
                    "citations": [
                        {
                            "pmid": "17314442", "title": "Aloe vera on prevention and healing of skin wounds", 
                            "authors": "Maenthaisong R, et al.", "journal": "Burns", "year": 2007, "study_type": "Systematic Review",
                            "conclusion": "Significantly reduced healing time."
                        }
                    ],
                    "safety_notes": ["Do not use on deep/infected wounds"],
                    "contraindications": ["Third degree burns"],
                    "interactions": [
                         {"substance": "Hydrocortisone", "severity": "minor", "description": "May increase absorption"}
                    ],
                    "dosing": {"topical": "Apply gel 3-4x daily"},
                    "recommendation_strength": "strong",
                    "grade_assessment": "⊕⊕⊕○"
                },
                {
                    "herb": "tea tree",
                    "herb_aliases": ["melaleuca"],
                    "condition": "acne",
                    "evidence_level": "moderate",
                    "summary": "5% gel effective for mild to moderate acne, similar to benzoyl peroxide but slower onset.",
                    "citations": [
                        {
                            "pmid": "17314442", "title": "Treatment of acne with tea tree oil", "authors": "Bassett IB, et al.",
                            "journal": "Med J Aust", "year": 1990, "study_type": "RCT",
                            "conclusion": "Effective with fewer side effects than benzoyl peroxide."
                        }
                    ],
                    "safety_notes": ["Toxic if ingested", "Skin irritation possible"],
                    "contraindications": ["Eczema (caution)"],
                    "interactions": [],
                    "dosing": {"topical": "5% gel or diluted oil"},
                    "recommendation_strength": "conditional",
                    "grade_assessment": "⊕⊕○○"
                },

                # =================================================================
                # URINARY (UTI)
                # =================================================================
                {
                    "herb": "cranberry",
                    "herb_aliases": ["vaccinium macrocarpon"],
                    "condition": "uti",
                    "condition_aliases": ["bladder infection", "cystitis"],
                    "evidence_level": "moderate",
                    "summary": "Effective for PREVENTION of recurrent UTIs, but NOT for treatment of active infections.",
                    "citations": [
                        {
                            "pmid": "37068952", "title": "Cranberries for preventing UTIs", "authors": "Williams G, et al.",
                            "journal": "Cochrane Database Syst Rev", "year": 2023, "study_type": "Meta-analysis",
                            "conclusion": "Reduces risk of recurrent UTI in women."
                        }
                    ],
                    "safety_notes": ["High sugar in juice", "Kidney stone risk (oxalates)"],
                    "contraindications": ["History of kidney stones (relative)", "Active infection (see doctor)"],
                    "interactions": [
                        {"substance": "Warfarin", "severity": "moderate", "description": "Conflicting evidence of INR increase"}
                    ],
                    "dosing": {"prevention": "Products with 36mg PACs daily"},
                    "recommendation_strength": "conditional",
                    "grade_assessment": "⊕⊕⊕○"
                },

                # =================================================================
                # MISCELLANEOUS / TRADITIONAL
                # =================================================================
                {
                    "herb": "tulsi",
                    "herb_aliases": ["holy basil", "ocimum sanctum"],
                    "condition": "stress",
                    "evidence_level": "low",
                    "summary": "Preliminary evidence suggests adaptogenic properties.",
                    "citations": [
                        {
                            "pmid": "28400848", "title": "Tulsi - A herb for all reasons", "authors": "Cohen MM",
                            "journal": "J Ayurveda Integr Med", "year": 2014, "study_type": "Review",
                            "conclusion": "Adaptogenic and metabolic effects noted."
                        }
                    ],
                    "safety_notes": ["Lowers blood sugar", " fertility concerns (animal studies)"],
                    "contraindications": ["Pregnancy", "Hypothyroidism"],
                    "interactions": [
                        {"substance": "Diabetes meds", "severity": "moderate", "description": "Additive hypoglycemia"}
                    ],
                    "dosing": {"tea": "2-3 cups daily"},
                    "recommendation_strength": "weak",
                    "grade_assessment": "⊕○○○"
                }
            ]
        }
        
    def _build_herb_registry(self):
        """Build registry of all known herbs from evidence database"""
        self.known_herbs = set()
        
        for entry in self.evidence_data.get('evidence', []):
            herb = entry.get('herb', '').lower()
            if herb: 
                self.known_herbs.add(herb)
            for alias in entry.get('herb_aliases', []):
                self.known_herbs.add(alias.lower())
        
        # Add common herbs not in database (for detection purposes)
        additional_herbs = [
            'brahmi', 'giloy', 'amla', 'triphala', 'fennel', 'cumin', 
            'coriander', 'fenugreek', 'cinnamon', 'clove', 'cardamom', 
            'black pepper', 'mint', 'basil', 'oregano', 'thyme',
            'rosemary', 'sage', 'parsley', 'dill', 'bay leaf', 'licorice'
        ]
        self.known_herbs.update(h.lower() for h in additional_herbs)
        
    def _get_canonical_name(self, herb: str) -> str:
        """Resolve an herb alias to its canonical (primary) name."""
        herb_lower = herb.lower().strip()
        for entry in self.evidence_data.get('evidence', []):
            entry_herb = entry.get('herb', '').lower()
            entry_aliases = [a.lower() for a in entry.get('herb_aliases', [])]
            if herb_lower == entry_herb or herb_lower in entry_aliases:
                return entry.get('herb', herb)
        return herb

    def _get_confidence_score(self, evidence_level: str, evidence: Dict = None) -> float:
        """
        Dynamic confidence scoring (tier-based with bonuses).

        Based on EvidenceTier system:
          Tier 1 (Clinical: meta-analyses, RCTs) = 9.0
          Tier 2 (Mechanistic: pharmacological studies) = 7.5
          Tier 3 (Traditional: documented traditional use) = 5.5
          Tier 4 (Anecdotal: case reports, preliminary) = 3.5
          Tier 5 (Theoretical: theoretical basis only) = 1.5

        Bonuses:
          +0.3 per PubMed citation (max +1.0)
          +0.5 if mechanism/summary is documented
        """
        # Map GRADE evidence levels to tier base scores
        base_scores = {
            'high': 9.0,            # Tier 1: Clinical
            'moderate': 7.5,        # Tier 2: Mechanistic
            'low_to_moderate': 5.5, # Tier 3: Traditional
            'low': 5.5,            # Tier 3: Traditional
            'very_low': 3.5,       # Tier 4: Anecdotal
            'insufficient': 1.5,   # Tier 5: Theoretical
        }
        base_score = base_scores.get(evidence_level, 3.0)

        # Dynamic bonuses from evidence quality
        pubmed_bonus = 0.0
        mechanism_bonus = 0.0

        if evidence and isinstance(evidence, dict):
            # PubMed citation bonus: +0.3 per citation, max +1.0
            citations = evidence.get('citations', [])
            pubmed_ids = [c for c in citations if c.get('pmid') and c.get('pmid') != 'N/A']
            pubmed_bonus = min(len(pubmed_ids) * 0.3, 1.0)

            # Mechanism bonus: +0.5 if summary/mechanism is documented
            if evidence.get('summary'):
                mechanism_bonus = 0.5

        confidence_score = min(base_score + pubmed_bonus + mechanism_bonus, 10.0)
        return round(confidence_score, 1)

    def _get_confidence_color(self, score: float) -> str:
        """Map confidence score to a colored circle emoji."""
        if score >= 8.0:
            return '🟢'
        elif score >= 5.0:
            return '🟡'
        return '🔴'

    def get_evidence_for_herb(self, herb: str, condition: str = None) -> Optional[Dict]:
        """Get evidence entry for a specific herb and condition"""
        herb_lower = herb.lower().strip()
        
        for entry in self.evidence_data.get('evidence', []):
            entry_herb = entry.get('herb', '').lower()
            entry_aliases = [a.lower() for a in entry.get('herb_aliases', [])]
            
            # Check herb match
            if herb_lower == entry_herb or herb_lower in entry_aliases:
                if not condition: 
                    return entry
                
                # Check condition match
                condition_lower = condition.lower().replace(' ', '_')
                entry_condition = entry.get('condition', '').lower().replace(' ', '_')
                entry_condition_aliases = [
                    c.lower().replace(' ', '_') 
                    for c in entry.get('condition_aliases', [])
                ]
                
                if (condition_lower in entry_condition or 
                    entry_condition in condition_lower or
                    condition_lower in entry_condition_aliases or
                    any(condition_lower in alias for alias in entry_condition_aliases) or
                    self._conditions_related(condition_lower, entry_condition)):
                    return entry
        
        # Fallback: if we found the herb but not the specific condition, return the herb entry
        # (Logic can be adjusted to return None if strict matching is required)
        for entry in self.evidence_data.get('evidence', []):
            if herb_lower == entry.get('herb') or herb_lower in [a.lower() for a in entry.get('herb_aliases', [])]:
                return entry
                
        return None

    def _conditions_related(self, condition1: str, condition2: str) -> bool:
        """Check if two conditions are clinically related"""
        condition_groups = {
            'respiratory': ['cough', 'cold', 'flu', 'bronchitis', 'congestion', 
                          'sore_throat', 'pharyngitis', 'sinusitis', 'respiratory'],
            'digestive': ['stomach', 'nausea', 'ibs', 'digestion', 'bloating', 
                         'indigestion', 'diarrhea', 'constipation', 'digestive',
                         'abdominal_pain', 'dyspepsia', 'acidity'],
            'pain': ['headache', 'inflammation', 'arthritis', 'muscle_pain', 
                    'joint_pain', 'pain', 'migraine'],
            'mental': ['anxiety', 'sleep', 'insomnia', 'relaxation', 'stress',
                      'depression', 'mood', 'stress_and_anxiety'],
            'skin': ['burns', 'wound', 'acne', 'rash', 'eczema', 'skin'],
            'cardiovascular': ['hypertension', 'blood_pressure', 'heart', 'cardiovascular']
        }
        
        for group, conditions in condition_groups.items():
            c1_match = condition1 in conditions or condition1 == group
            c2_match = condition2 in conditions or condition2 == group
            if c1_match and c2_match:
                return True
        
        return False

    async def verify_response(
        self,
        llm_response: str,
        query: str,
        user_id: str = None,  # TEMPORAL: Added for pharmacovigilance
        user_conditions: List[str] = None,
        user_medications: List[str] = None,
        user_allergies: List[str] = None,
        current_condition: str = None
    ) -> ValidationResult:
        """
        ASYNC Main verification method - validates all claims in an LLM response. 
        Now includes temporal safety validation for medication timing.
        """
        user_conditions = user_conditions or []
        user_medications = user_medications or []
        user_allergies = user_allergies or []
        
        # Determine condition
        if current_condition:
            condition = current_condition.lower().strip()
        else:
            condition = self._identify_condition(query)
        
        logger.info(f"Trust Engine: Verifying for condition '{condition}'")
        
        # Find herbs in response
        response_lower = llm_response.lower()
        found_herbs = []
        
        for herb in self.known_herbs:
            # Word boundary regex to ensure we don't match substrings (e.g. "tea" in "tear")
            if re.search(r'\b' + re.escape(herb) + r'\b', response_lower):
                if herb not in [a.lower() for a in user_allergies]:
                    found_herbs.append(herb)
        
        logger.info(f"Trust Engine: Found herbs {list(set(found_herbs))}")
        
        # TEMPORAL SAFETY CHECK - Added for Objective 1 (now async)
        temporal_safety_blocked = False
        temporal_violations = []
        temporal_recommendations = []
        
        if user_id and found_herbs and TEMPORAL_ENGINE_AVAILABLE:
            temporal_result = await self.validate_temporal_safety(
                user_id=user_id,
                herbs=found_herbs,
                symptom_descriptions=[condition] if condition != "general" else None
            )
            temporal_safety_blocked = temporal_result.get('blocked', False)
            temporal_violations = temporal_result.get('violations', [])
            temporal_recommendations = temporal_result.get('recommendations', [])
            
            if temporal_safety_blocked:
                logger.critical(f"🚫 TEMPORAL SAFETY BLOCK: User {user_id[:20]}... - Critical violations detected")
        
        # Verify each herb
        verified_herbs = []
        unverified_herbs = []
        warnings = []
        contraindicated_herbs = []
        interaction_warnings = []
        evidence_summaries = {}
        
        # Resolve aliases to canonical names, then deduplicate while preserving order
        canonical_herbs = list(dict.fromkeys(
            self._get_canonical_name(h) for h in found_herbs
        ))
        for herb in canonical_herbs:
            evidence = self.get_evidence_for_herb(herb, condition)

            if evidence:
                verified_herbs.append(herb)
                evidence_summaries[herb] = evidence  # Store raw dict for new compact formatter
                
                # Check contraindications
                for contra in evidence.get('contraindications', []):
                    for user_cond in user_conditions:
                        if user_cond.lower() in contra.lower():
                            contraindicated_herbs.append(herb)
                            warnings.append(
                                f"⚠️ **{herb.title()}** may be contraindicated: {contra}"
                            )
                
                # Check drug interactions
                for interaction in evidence.get('interactions', []):
                    substance = interaction.get('substance', '').lower()
                    for user_med in user_medications: 
                        if user_med.lower() in substance or substance in user_med.lower():
                            severity = interaction.get('severity', 'unknown')
                            description = interaction.get('description', '')
                            
                            if severity in ['critical', 'major']: 
                                interaction_warnings.append(
                                    f"🚫 **CRITICAL**: {herb.title()} + {user_med}: {description}"
                                )
                            elif severity == 'moderate':
                                interaction_warnings.append(
                                    f"⚠️ **Caution**: {herb.title()} + {user_med}: {description}"
                                )
                            else:
                                interaction_warnings.append(
                                    f"ℹ️ **Note**: {herb.title()} + {user_med}: {description}"
                                )
                
                # Check allergies
                herb_aliases = [a.lower() for a in evidence.get('herb_aliases', [])]
                for allergy in user_allergies:
                    if allergy.lower() in herb.lower() or any(allergy.lower() in alias for alias in herb_aliases):
                        contraindicated_herbs.append(herb)
                        warnings.append(f"🚫 **{herb.title()}** - possible allergy concern")
            else:
                unverified_herbs.append(herb)
        
        # Generate formatted output
        formatted_output = self._format_full_response(
            verified_herbs, unverified_herbs, condition, evidence_summaries,
            warnings, interaction_warnings
        )
        
        # Determine safety - now includes temporal blocking
        is_safe = (len(contraindicated_herbs) == 0 and 
                   len([w for w in interaction_warnings if 'CRITICAL' in w]) == 0 and
                   not temporal_safety_blocked)
        
        return ValidationResult(
            is_safe=is_safe,
            verified_herbs=verified_herbs,
            unverified_herbs=unverified_herbs,
            warnings=warnings,
            contraindicated_herbs=contraindicated_herbs,
            interaction_warnings=interaction_warnings,
            evidence_summaries=evidence_summaries,
            formatted_output=formatted_output,
            # TEMPORAL FIELDS
            temporal_safety_blocked=temporal_safety_blocked,
            temporal_violations=temporal_violations,
            temporal_recommendations=temporal_recommendations
        )

    def _identify_condition(self, query: str) -> str:
        """Identify condition from query text"""
        query_lower = query.lower()
        for condition, keywords in self.condition_map.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return condition
        return "general"

    def _format_evidence_citation(self, herb: str, evidence: Dict, condition: str) -> str:
        """Format evidence with proper PubMed citations and uncertainty language"""
        output_parts = []
        
        # Header
        output_parts.append(f"### {herb.title()}")
        output_parts.append("")
        
        # Evidence summary with appropriate uncertainty language
        evidence_level = evidence.get('evidence_level', 'insufficient')
        summary = evidence.get('summary', 'potential benefits, but more research is needed')
        uncertainty_prefix = self.UNCERTAINTY_LANGUAGE.get(evidence_level, 'Limited evidence suggests')
        
        output_parts.append(f"**Summary**: {uncertainty_prefix} {summary}")
        output_parts.append("")
        
        # Detailed summary if available
        detailed = evidence.get('detailed_summary', '')
        if detailed:
            output_parts.append(f"**Details**: {detailed}")
            output_parts.append("")
        
        # Limitations
        limitations = evidence.get('limitations', [])
        if limitations:
            output_parts.append("**Limitations**:")
            for limitation in limitations[:4]: 
                output_parts.append(f"- {limitation}")
            output_parts.append("")
        
        # PubMed Citations with links
        citations = evidence.get('citations', [])
        if citations:
            output_parts.append("**References (PubMed)**:")
            for i, cite in enumerate(citations[:3], 1):
                pmid = cite.get('pmid', 'N/A')
                title = cite.get('title', 'Unknown title')
                authors = cite.get('authors', 'Unknown')
                journal = cite.get('journal', '')
                year = cite.get('year', '')
                study_type = cite.get('study_type', '')
                conclusion = cite.get('conclusion', '')
                
                cite_line = f"{i}. {authors}. \"{title}.\" *{journal}* ({year}). "
                cite_line += f"[PMID: {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)"
                if study_type:
                    cite_line += f" **[{study_type}]**"
                output_parts.append(cite_line)
                
                if conclusion:
                    output_parts.append(f"   - *Conclusion*: {conclusion}")
                output_parts.append("")
        else:
            output_parts.append("**Note**: No specific PubMed citations available. Recommendation based on traditional use.")
            output_parts.append("")
        
        # Safety information
        safety_notes = evidence.get('safety_notes', [])
        if safety_notes:
            output_parts.append("**Safety Considerations**:")
            for note in safety_notes[:4]:
                output_parts.append(f"- {note}")
            output_parts.append("")
        
        # Dosing
        dosing = evidence.get('dosing', {})
        if dosing:
            output_parts.append("**Suggested Dosing** (based on studies):")
            for key, value in list(dosing.items())[:4]:
                key_formatted = key.replace('_', ' ').title()
                output_parts.append(f"- {key_formatted}: {value}")
            output_parts.append("")
        
        # Evidence assessment (GRADE-style)
        certainty = evidence.get('certainty_of_evidence', evidence_level)
        recommendation = evidence.get('recommendation_strength', 'unknown')
        grade = evidence.get('grade_assessment', self.GRADE_SYMBOLS.get(evidence_level, '○○○○'))
        
        output_parts.append("**Evidence Assessment**:")
        output_parts.append(f"- Certainty: {certainty.replace('_', ' ').title()} {grade}")
        output_parts.append(f"- Recommendation: {recommendation.replace('_', ' ').title()}")
        output_parts.append("")
        
        return "\n".join(output_parts)

    def _format_full_response(
        self,
        verified_herbs: List[str],
        unverified_herbs: List[str],
        condition: str,
        evidence_summaries: Dict,
        warnings: List[str],
        interaction_warnings: List[str]
    ) -> str:
        """Generate compact formatted response with confidence scores and PubMed links."""
        output_parts = []

        output_parts.append("\n\n---\n")
        output_parts.append("## 🔬 Scientific Validation (Trust Engine)")
        output_parts.append("")
        output_parts.append("*Evidence sourced from PubMed-indexed research. Always consult a healthcare provider.*")
        output_parts.append("")

        # Drug interaction alerts (most critical — shown first)
        if interaction_warnings:
            output_parts.append("### ⚠️ Drug Interaction Alerts")
            output_parts.append("")
            for warning in interaction_warnings:
                output_parts.append(warning)
            output_parts.append("")

        # General safety warnings
        if warnings:
            output_parts.append("### ⚠️ Safety Alerts")
            output_parts.append("")
            for warning in warnings:
                output_parts.append(warning)
            output_parts.append("")

        # Verified herbs — detailed format with study type, mechanism, dose
        if verified_herbs:
            output_parts.append("**Verified Remedies:**")
            output_parts.append("")
            for herb in verified_herbs:
                evidence = evidence_summaries.get(herb)
                if not isinstance(evidence, dict):
                    continue

                score = self._get_confidence_score(evidence.get('evidence_level', 'insufficient'), evidence)
                color = self._get_confidence_color(score)
                summary = evidence.get('summary', '')
                dosing = evidence.get('dosing', {})
                dose_str = ', '.join(
                    f"{v}" for k, v in list(dosing.items())[:2]
                ) if dosing else ''

                citations = evidence.get('citations', [])
                # Determine study type and count from citations
                study_types = [c.get('study_type', '') for c in citations if c.get('study_type')]
                num_studies = len(citations)
                primary_study_type = study_types[0] if study_types else 'Study'
                study_count_str = f"{primary_study_type} ({num_studies} {'study' if num_studies == 1 else 'studies'})"

                # PubMed citation links
                pmid_links = []
                for cite in citations[:2]:
                    pmid = cite.get('pmid', '')
                    if pmid and pmid != 'N/A':
                        pmid_links.append(
                            f"[PMID {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)"
                        )

                output_parts.append(f"**{herb.title()}** {color} {score}/10 Evidence: {study_count_str}")
                if summary:
                    output_parts.append(f"Mechanism: {summary}")
                if dose_str:
                    output_parts.append(f"Dose: {dose_str}")
                if pmid_links:
                    output_parts.append(f"PubMed: {' · '.join(pmid_links)}")
                output_parts.append("")

        # Unverified herbs — caution notice with condition
        if unverified_herbs:
            output_parts.append("**Unverified (Use with Caution):**")
            output_parts.append("")
            condition_display = condition.replace('_', ' ') if condition else 'this condition'
            for herb in unverified_herbs:
                output_parts.append(
                    f"⚠️ **{herb.title()}** — No evidence linking {herb.lower()} to {condition_display}"
                )
            output_parts.append("")

        # Confidence score legend
        output_parts.append("**Confidence Score Legend:**")
        output_parts.append("")
        output_parts.append("🟢 8-10 Strong clinical evidence<br>🟡 5-7 Good research support<br>🔴 1-4 Limited evidence")

        return "\n".join(output_parts)

    def is_herb_known(self, herb: str) -> bool:
        """Check if an herb is in our knowledge base"""
        return herb.lower() in self.known_herbs

    def _get_evidence_for_herb_via_rag(self, herb_name: str, condition: str = None) -> Optional[Dict]:
        """
        Retrieve evidence for an herb via RAG (Retrieval Augmented Generation).
        This hardcoded method calls the retrieve_content function to fetch
        evidence from the vector database.
        
        Args:
            herb_name: Name of the herb to search for
            condition: Optional health condition context
            
        Returns:
            Dict with retrieved evidence or None if not found
        """
        try:
            # Import retrieve_content here to avoid circular imports
            from rag_service.content_retrieval import retrieve_content
            
            # Construct query combining herb and condition
            if condition and condition != "general":
                query = f"{herb_name} for {condition} health benefits evidence"
            else:
                query = f"{herb_name} medicinal uses health benefits"
            
            logger.info(f"RAG lookup for herb: {herb_name}, condition: {condition}")
            
            # Call retrieve_content with the query
            # user_id is None since this is a general lookup
            result = retrieve_content(query, user_id=None, top_k=3)
            
            if result and result.get('chunks'):
                chunks = result.get('chunks', [])
                
                # Combine chunk texts for evidence
                combined_text = "\n\n".join([
                    c.get('text', '') or c.get('content', '') or str(c)
                    for c in chunks[:3]
                ])
                
                # Extract PubMed IDs if present in the chunks
                pubmed_ids = []
                for chunk in chunks:
                    text = chunk.get('text', '') or chunk.get('content', '') or str(chunk)
                    # Look for PubMed ID patterns (PMID: 12345678)
                    import re
                    pmid_matches = re.findall(r'PMID:\s*(\d+)', text, re.IGNORECASE)
                    pubmed_ids.extend(pmid_matches)
                
                return {
                    'herb': herb_name,
                    'condition': condition,
                    'source': 'rag_retrieval',
                    'chunks': chunks,
                    'combined_evidence': combined_text,
                    'pubmed_ids': list(set(pubmed_ids)),  # Remove duplicates
                    'chunk_count': len(chunks)
                }
            
            logger.warning(f"No RAG evidence found for {herb_name}")
            return None
            
        except ImportError as e:
            logger.error(f"Could not import retrieve_content: {e}")
            return None
        except Exception as e:
            logger.error(f"Error in RAG evidence retrieval: {e}")
            return None


# =================================================================
# SINGLETON INSTANCE & TEST RUNNER
# =================================================================

_trust_engine_instance = None

def get_trust_engine() -> TrustEngine:
    """Get or create Trust Engine singleton"""
    global _trust_engine_instance
    if _trust_engine_instance is None:
        _trust_engine_instance = TrustEngine()
    return _trust_engine_instance

if __name__ == "__main__":
    # Test execution
    engine = get_trust_engine()
    print("Testing ServVia Trust Engine v2.1 Monolith...")
    
    test_query = "Is ashwagandha safe for stress if I take thyroid meds?"
    test_response = "You can take ashwagandha for stress relief."
    user_meds = ["Levothyroxine"]
    
    result = engine.verify_response(
        llm_response=test_response,
        query=test_query,
        user_medications=user_meds
    )
    
    print("\nVerification Result:")
    print(f"Is Safe: {result.is_safe}")
    print(result.formatted_output)
