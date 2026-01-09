"""
ServVia Trust Engine - Knowledge Graph Schema
Neuro-Symbolic AI: Symbolic Layer

This defines the explicit relationships and rules that the symbolic
reasoning engine uses to validate LLM outputs. 
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum


class EvidenceTier(Enum):
    """Evidence hierarchy based on scientific rigor"""
    TIER_1_CLINICAL = 1      # Randomized Clinical Trials, Meta-analyses
    TIER_2_MECHANISTIC = 2   # In-vitro, animal studies, mechanism known
    TIER_3_TRADITIONAL = 3   # Documented traditional use (Ayurveda, TCM)
    TIER_4_ANECDOTAL = 4     # Case reports, user testimonials
    TIER_5_THEORETICAL = 5   # Hypothetical, no evidence
    
    @property
    def label(self):
        labels = {
            1: "Clinical Trial (Highest)",
            2: "Mechanistic Study",
            3: "Traditional Medicine",
            4: "Anecdotal",
            5: "Theoretical (Lowest)"
        }
        return labels.get(self.value, "Unknown")
    
    @property
    def weight(self):
        """Weight for SCS calculation"""
        weights = {1: 1.0, 2: 0.75, 3: 0.5, 4: 0.25, 5: 0.1}
        return weights. get(self.value, 0.1)


class SafetyLevel(Enum):
    """Safety classification for herbs"""
    SAFE = "safe"                    # Generally safe for most people
    CAUTION = "caution"              # Safe with precautions
    CONTRAINDICATED = "contraindicated"  # Dangerous for specific conditions
    TOXIC = "toxic"                  # Dangerous in general


@dataclass
class Herb:
    """Herb entity in the Knowledge Graph"""
    id: str
    name: str
    scientific_name: str
    family: str = ""
    
    # Properties
    properties: List[str] = field(default_factory=list)
    active_compounds: List[str] = field(default_factory=list)
    
    # Safety information (CRITICAL for symbolic reasoning)
    contraindications: List[str] = field(default_factory=list)
    drug_interactions: List[str] = field(default_factory=list)
    max_daily_dose: Optional[str] = None
    pregnancy_safe: bool = False
    
    # Traditional systems
    ayurveda_name: Optional[str] = None
    tcm_name: Optional[str] = None
    
    def is_safe_for(self, conditions: List[str], medications: List[str]) -> tuple:
        """
        Symbolic reasoning: Check if herb is safe for user
        Returns: (is_safe, warnings)
        """
        warnings = []
        
        # Check contraindications
        for condition in conditions:
            for contraind in self.contraindications:
                if condition. lower() in contraind.lower():
                    warnings.append(f"⚠️ {self.name} may be contraindicated with {condition}")
        
        # Check drug interactions
        for med in medications:
            for interaction in self. drug_interactions:
                if med.lower() in interaction.lower():
                    warnings.append(f"⚠️ {self.name} may interact with {med}")
        
        is_safe = len(warnings) == 0
        return is_safe, warnings


@dataclass
class Condition:
    """Health condition/disease entity"""
    id: str
    name: str
    icd_code: str = ""
    symptoms: List[str] = field(default_factory=list)
    severity_indicators: List[str] = field(default_factory=list)  # When to see doctor
    
    # Related conditions (for understanding user context)
    related_conditions: List[str] = field(default_factory=list)


@dataclass
class Evidence:
    """Evidence linking Herb to Condition"""
    herb_id: str
    condition_id: str
    
    # Evidence classification
    tier: EvidenceTier
    pubmed_ids: List[str] = field(default_factory=list)
    doi: Optional[str] = None
    
    # Mechanism of action (symbolic knowledge)
    mechanism: str = ""
    active_compound: Optional[str] = None
    
    # Dosage information (for validation)
    recommended_dose: Optional[str] = None
    preparation_method: Optional[str] = None
    
    # Validation status
    verified: bool = False
    last_verified: Optional[str] = None


@dataclass 
class ContraindicationRule:
    """
    Explicit symbolic rules for contraindications. 
    These are HARD RULES that override LLM suggestions.
    """
    herb_name: str
    condition: str
    severity: SafetyLevel
    reason: str
    source: str  # Citation for the rule


@dataclass
class DrugInteractionRule:
    """
    Explicit rules for herb-drug interactions.
    Critical for patient safety.
    """
    herb_name: str
    drug_class: str
    drugs: List[str]
    interaction_type: str  # "increases", "decreases", "potentiates"
    severity: SafetyLevel
    reason: str
    source: str


class KnowledgeGraphSchema:
    """
    Central schema manager for the Knowledge Graph. 
    Provides symbolic reasoning capabilities.
    """
    
    def __init__(self):
        self. herbs: Dict[str, Herb] = {}
        self. conditions: Dict[str, Condition] = {}
        self. evidence: List[Evidence] = []
        self.contraindication_rules: List[ContraindicationRule] = []
        self.drug_interaction_rules: List[DrugInteractionRule] = []
    
    def add_herb(self, herb: Herb):
        self.herbs[herb. id] = herb
    
    def add_condition(self, condition: Condition):
        self.conditions[condition.id] = condition
    
    def add_evidence(self, evidence: Evidence):
        self.evidence.append(evidence)
    
    def add_contraindication_rule(self, rule: ContraindicationRule):
        self. contraindication_rules.append(rule)
    
    def add_drug_interaction_rule(self, rule: DrugInteractionRule):
        self.drug_interaction_rules.append(rule)
    
    def get_evidence_for_pair(self, herb_name: str, condition_name: str) -> Optional[Evidence]:
        """Get evidence linking a specific herb to a condition"""
        herb_lower = herb_name. lower()
        cond_lower = condition_name.lower()
        
        for ev in self.evidence:
            herb = self.herbs.get(ev.herb_id)
            cond = self.conditions.get(ev. condition_id)
            
            if herb and cond:
                if herb.name.lower() == herb_lower and cond.name.lower() == cond_lower:
                    return ev
        return None
    
    def check_contraindications(self, herb_name: str, user_conditions: List[str]) -> List[str]:
        """
        Symbolic reasoning: Check if herb is contraindicated for user's conditions
        Returns list of warnings
        """
        warnings = []
        herb_lower = herb_name.lower()
        
        for rule in self.contraindication_rules:
            if rule.herb_name.lower() == herb_lower:
                for condition in user_conditions:
                    if condition.lower() in rule.condition. lower():
                        if rule.severity in [SafetyLevel.CONTRAINDICATED, SafetyLevel.TOXIC]:
                            warnings.append(f"🚫 AVOID: {herb_name} is contraindicated with {condition}.  Reason: {rule.reason}")
                        elif rule.severity == SafetyLevel. CAUTION:
                            warnings.append(f"⚠️ CAUTION: {herb_name} - use carefully with {condition}.  Reason: {rule. reason}")
        
        return warnings
    
    def check_drug_interactions(self, herb_name: str, user_medications: List[str]) -> List[str]:
        """
        Symbolic reasoning: Check for herb-drug interactions
        Returns list of warnings
        """
        warnings = []
        herb_lower = herb_name.lower()
        
        for rule in self.drug_interaction_rules:
            if rule.herb_name.lower() == herb_lower:
                for med in user_medications:
                    med_lower = med. lower()
                    if any(drug.lower() in med_lower or med_lower in drug.lower() for drug in rule.drugs):
                        if rule.severity in [SafetyLevel. CONTRAINDICATED, SafetyLevel. TOXIC]:
                            warnings.append(f"🚫 DRUG INTERACTION: {herb_name} {rule.interaction_type} {med}. {rule.reason}")
                        else:
                            warnings.append(f"⚠️ Possible interaction: {herb_name} with {med}. {rule.reason}")
        
        return warnings
