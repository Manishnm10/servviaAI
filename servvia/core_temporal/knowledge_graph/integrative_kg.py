"""
ServVia 2.0 - Integrative Knowledge Graph (iKG)
Connects: Herbs ↔ Phytochemicals ↔ Biological Targets ↔ Diseases
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EvidenceTier(Enum):
    """Evidence Grading Framework from Table 1"""
    TIER_1_CLINICAL = 1      # Systematic reviews, Meta-analyses, RCTs
    TIER_2_MECHANISTIC = 2   # Known mechanism, limited human trials
    TIER_3_TRADITIONAL = 3   # Classical texts, ethnobotanical databases
    TIER_4_ANECDOTAL = 4     # Web scrapes, no structural backing
    TIER_5_UNSAFE = 5        # Contraindicated, known adverse effects
    
    @property
    def badge(self) -> Dict:
        badges = {
            1: {"color": "green", "label": "Scientifically Proven", "icon": "✅"},
            2: {"color": "yellow", "label": "Promising Science", "icon": "🔬"},
            3: {"color": "blue", "label": "Traditional Wisdom", "icon": "📜"},
            4: {"color": "grey", "label": "Anecdotal", "icon": "⚠️"},
            5: {"color": "red", "label": "Safety Alert", "icon": "🚫"},
        }
        return badges.get(self.value, badges[4])


@dataclass
class Phytochemical:
    """Active compound in an herb"""
    name: str
    cas_number: Optional[str] = None
    molecular_formula: Optional[str] = None
    targets: List[str] = field(default_factory=list)  # Protein targets
    mechanism: Optional[str] = None


@dataclass
class HerbNode:
    """Comprehensive herb entity"""
    id: str
    common_name: str
    scientific_name: str
    
    # Traditional names
    ayurveda_name: Optional[str] = None
    tcm_name: Optional[str] = None
    
    # Active compounds
    phytochemicals: List[Phytochemical] = field(default_factory=list)
    
    # Properties
    rasa: Optional[str] = None        # Taste (Ayurveda)
    virya: Optional[str] = None       # Potency (Heating/Cooling)
    vipaka: Optional[str] = None      # Post-digestive effect
    dosha_effect: Dict[str, str] = field(default_factory=dict)  # {"vata": "decreases", ... }
    
    # Safety
    contraindications: List[str] = field(default_factory=list)
    drug_interactions: List[Dict] = field(default_factory=list)
    max_daily_dose: Optional[str] = None
    pregnancy_category: Optional[str] = None  # Safe/Caution/Avoid
    
    # Evidence
    pubmed_ids: List[str] = field(default_factory=list)
    clinical_trials: List[str] = field(default_factory=list)


@dataclass
class DiseaseNode:
    """Disease/Condition entity"""
    id: str
    name: str
    icd_code: Optional[str] = None
    
    # Symptoms
    symptoms: List[str] = field(default_factory=list)
    
    # Biological targets
    pathways: List[str] = field(default_factory=list)  # e.g., "NF-κB", "COX-2"
    
    # When to see doctor
    red_flags: List[str] = field(default_factory=list)


@dataclass
class EvidenceEdge:
    """Relationship between Herb and Disease"""
    herb_id: str
    disease_id: str
    
    # Evidence grading
    tier: EvidenceTier
    confidence_score: float  # 0-10
    
    # Mechanism
    active_compound: Optional[str] = None
    target_pathway: Optional[str] = None
    mechanism_description: str = ""
    
    # Sources
    pubmed_ids: List[str] = field(default_factory=list)
    traditional_sources: List[str] = field(default_factory=list)
    
    # Usage
    preparation_method: Optional[str] = None
    recommended_dose: Optional[str] = None
    onset_time: Optional[str] = None  # How long until effect


class IntegrativeKnowledgeGraph:
    """
    The iKG - Core of ServVia's Neuro-Symbolic reasoning
    
    Maps: Herb → Phytochemical → Protein Target → Disease Pathway → Clinical Outcome
    """
    
    def __init__(self):
        self.herbs: Dict[str, HerbNode] = {}
        self. diseases: Dict[str, DiseaseNode] = {}
        self.evidence: List[EvidenceEdge] = []
        self._load_core_data()
    
    def _load_core_data(self):
        """Load comprehensive herb-disease relationships"""
        
        # Example: Turmeric with full pathway
        turmeric = HerbNode(
            id="herb_turmeric",
            common_name="Turmeric",
            scientific_name="Curcuma longa",
            ayurveda_name="Haridra",
            tcm_name="Jiang Huang",
            phytochemicals=[
                Phytochemical(
                    name="Curcumin",
                    cas_number="458-37-7",
                    molecular_formula="C21H20O6",
                    targets=["NF-κB", "COX-2", "LOX", "TNF-α", "IL-6"],
                    mechanism="Inhibits inflammatory transcription factors"
                ),
                Phytochemical(
                    name="Turmerone",
                    targets=["Neurogenesis pathways"],
                    mechanism="Promotes neural stem cell proliferation"
                )
            ],
            rasa="Tikta (Bitter), Katu (Pungent)",
            virya="Ushna (Heating)",
            dosha_effect={"vata": "decreases", "pitta": "increases slightly", "kapha": "decreases"},
            contraindications=["gallstones", "bile duct obstruction", "bleeding disorders"],
            drug_interactions=[
                {"drug": "Warfarin", "effect": "Increases bleeding risk", "severity": "high"},
                {"drug": "Diabetes medications", "effect": "May enhance hypoglycemia", "severity": "moderate"}
            ],
            max_daily_dose="1-3g dried root or 500-1000mg curcumin extract",
            pregnancy_category="Caution - culinary amounts only",
            pubmed_ids=["PMC5664031", "PMC6471669", "PMC5822982"],
            clinical_trials=["NCT01042938", "NCT02529969"]
        )
        
        self.herbs[turmeric.id] = turmeric
        
        # Add evidence edge
        self.evidence.append(EvidenceEdge(
            herb_id="herb_turmeric",
            disease_id="disease_arthritis",
            tier=EvidenceTier.TIER_1_CLINICAL,
            confidence_score=9.2,
            active_compound="Curcumin",
            target_pathway="NF-κB / COX-2 inhibition",
            mechanism_description="Curcumin inhibits NF-κB activation and COX-2 expression, reducing inflammatory cytokines (IL-1β, IL-6, TNF-α) comparable to NSAIDs in clinical trials",
            pubmed_ids=["PMC5664031", "PMC6471669"],
            traditional_sources=["Charaka Samhita", "Sushruta Samhita"],
            preparation_method="500mg curcumin extract with 5mg piperine (black pepper) for enhanced absorption",
            recommended_dose="500-1000mg twice daily with meals",
            onset_time="2-4 weeks for noticeable effect"
        ))
        
        logger.info(f"iKG loaded: {len(self. herbs)} herbs, {len(self.evidence)} evidence edges")
    
    def get_evidence_for_condition(
        self, 
        condition: str, 
        exclude_herbs: List[str] = None,
        user_medications: List[str] = None,
        min_tier: int = 4
    ) -> List[Dict]:
        """
        Multi-hop reasoning to get safe, evidence-backed remedies
        
        Steps:
        1.  Find matching disease node
        2. Get all evidence edges for that disease
        3. Filter by evidence tier
        4.  Check contraindications against user meds
        5. Return ranked results
        """
        exclude_herbs = exclude_herbs or []
        user_medications = user_medications or []
        
        results = []
        
        for edge in self.evidence:
            # Check if matches condition
            if condition. lower() not in edge.disease_id.lower():
                continue
            
            # Check evidence tier
            if edge.tier. value > min_tier:
                continue
            
            # Get herb details
            herb = self.herbs.get(edge.herb_id)
            if not herb:
                continue
            
            # Check exclusions (allergies)
            if herb.common_name. lower() in [e.lower() for e in exclude_herbs]:
                continue
            
            # Check drug interactions
            interaction_warnings = []
            for interaction in herb.drug_interactions:
                for user_med in user_medications:
                    if interaction['drug']. lower() in user_med.lower():
                        interaction_warnings.append({
                            'drug': user_med,
                            'effect': interaction['effect'],
                            'severity': interaction['severity']
                        })
            
            results.append({
                'herb': herb,
                'evidence': edge,
                'interaction_warnings': interaction_warnings,
                'badge': edge.tier. badge
            })
        
        # Sort by confidence score
        results.sort(key=lambda x: x['evidence'].confidence_score, reverse=True)
        
        return results
    
    def calculate_scs(self, evidence: EvidenceEdge) -> Dict:
        """
        Calculate Scientific Confidence Score (SCS)
        
        Formula:
        SCS = (Tier_Weight × 0.4) + (PubMed_Count × 0.3) + (Mechanism_Clarity × 0.2) + (Traditional_Sources × 0.1)
        """
        tier_weights = {1: 10, 2: 7. 5, 3: 5, 4: 2.5, 5: 0}
        
        tier_score = tier_weights.get(evidence.tier.value, 2. 5) * 0.4
        pubmed_score = min(len(evidence.pubmed_ids) * 0.5, 3) * 0.3
        mechanism_score = (3 if evidence.mechanism_description else 0) * 0.2
        traditional_score = min(len(evidence. traditional_sources) * 0.5, 1) * 0. 1
        
        total = tier_score + pubmed_score + mechanism_score + traditional_score
        
        return {
            'score': round(total, 1),
            'tier': evidence.tier. value,
            'tier_label': evidence.tier. badge['label'],
            'badge_color': evidence.tier.badge['color'],
            'badge_icon': evidence. tier.badge['icon'],
            'pubmed_count': len(evidence. pubmed_ids),
            'has_mechanism': bool(evidence.mechanism_description)
        }
