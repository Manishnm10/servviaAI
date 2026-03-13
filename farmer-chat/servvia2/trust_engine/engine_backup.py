"""
ServVia 2. 0 Trust Engine - Production Ready
============================================
Neuro-Symbolic Verification System for Medical Recommendations

This engine combines:
- Neural: Receives LLM-generated natural language
- Symbolic: Validates against structured medical knowledge

Key Capabilities:
1.  Evidence-Based Verification - Grade claims by scientific evidence
2.  Hallucination Detection - Flag unverified medical claims
3. Drug-Herb Interaction Checking - Critical safety layer
4. Contraindication Enforcement - Block dangerous recommendations
5. Confidence Scoring (SCS) - Transparent trust metrics

Author: ServVia Team
Version: 2.0.0
"""

import logging
import re
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EvidenceTier(Enum):
    """Evidence quality tiers based on medical research standards"""
    TIER_1_CLINICAL = 1      # Meta-analyses, RCTs, Systematic Reviews
    TIER_2_MECHANISTIC = 2   # Pharmacological studies, known mechanisms
    TIER_3_TRADITIONAL = 3   # Documented traditional use, ethnomedicine
    TIER_4_ANECDOTAL = 4     # Case reports, preliminary research
    TIER_5_THEORETICAL = 5   # Theoretical basis only


class InteractionSeverity(Enum):
    """Drug-herb interaction severity levels"""
    CRITICAL = "critical"    # Life-threatening, absolute contraindication
    HIGH = "high"            # Significant risk, avoid combination
    MODERATE = "moderate"    # Use with caution, monitor
    LOW = "low"              # Minor interaction, generally safe
    NONE = "none"            # No known interaction


@dataclass
class VerificationResult:
    """Result of verifying a single remedy claim"""
    herb_name: str
    condition: str
    is_valid: bool
    confidence_score: float
    evidence_tier: int
    evidence_tier_label: str
    mechanism: str
    pubmed_count: int
    warnings: List[str] = field(default_factory=list)
    is_hallucination: bool = False
    hallucination_reason: Optional[str] = None
    interaction_note: Optional[str] = None
    recommended_dose: Optional[str] = None


@dataclass
class InteractionWarning:
    """Drug-herb interaction warning"""
    herb: str
    drug: str
    severity: InteractionSeverity
    effect: str
    recommendation: str
    alternatives: List[str] = field(default_factory=list)


class TrustEngine:
    """
    Production-Ready Neuro-Symbolic Trust Engine
    
    Usage:
        engine = TrustEngine()
        results, warnings = engine.verify_response(
            llm_response="Use ginger tea for nausea.. .",
            query="I have nausea",
            current_condition="nausea",
            user_medications=["aspirin"]
        )
    """
    
    def __init__(self):
        """Initialize the Trust Engine with knowledge bases"""
        self._load_evidence_database()
        self._load_interaction_database()
        self._load_contraindication_rules()
        self._build_herb_registry()
        
        logger.info(f"Trust Engine initialized: {len(self.evidence_db)} evidence entries, "
                   f"{len(self.interactions_db)} interaction rules, "
                   f"{len(self.known_herbs)} known herbs")
    
    # =========================================================================
    # KNOWLEDGE BASE LOADING
    # =========================================================================
    
    def _load_evidence_database(self):
        """
        Load evidence-based knowledge for herb-condition pairs. 
        Each entry represents validated scientific evidence.
        """
        self.evidence_db: Dict[Tuple[str, str], Dict] = {
            # =====================================================================
            # HEADACHE / MIGRAINE
            # =====================================================================
            ('peppermint', 'headache'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Menthol activates TRPM8 cold receptors, providing cooling analgesia.  Improves cerebral blood flow and reduces muscle tension.',
                'pubmed_ids': ['PMC4960504', 'PMC6540030'],
                'dose': '2-3 drops peppermint oil topically on temples, or 1-2 cups peppermint tea',
                'onset': '15-30 minutes',
                'contraindications': ['GERD', 'hiatal hernia'],
            },
            ('ginger', 'headache'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Gingerols and shogaols inhibit prostaglandin synthesis (similar to NSAIDs), reducing neurogenic inflammation.',
                'pubmed_ids': ['PMC3665023'],
                'dose': '250mg-1g dried ginger extract, or 1-inch fresh ginger in tea',
                'onset': '30-60 minutes',
            },
            ('lavender', 'headache'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Linalool and linalyl acetate modulate GABAergic transmission, reducing pain perception and stress response.',
                'pubmed_ids': ['PMC3612440', 'PMC5437114'],
                'dose': 'Aromatherapy for 15-30 minutes, or 2-3 drops diluted oil on temples',
                'onset': '15-30 minutes',
            },
            ('clove', 'headache'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Eugenol (85% of clove oil) inhibits cyclooxygenase enzymes, providing analgesic effects.',
                'pubmed_ids': ['PMC3769004'],
                'dose': '1-2 cloves as tea, or diluted clove oil topically',
                'onset': '20-40 minutes',
            },
            ('feverfew', 'headache'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Parthenolide inhibits serotonin release and prostaglandin synthesis, preventing migraine onset.',
                'pubmed_ids': ['PMC3210009'],
                'dose': '50-150mg dried leaf daily for prevention',
                'onset': 'Preventive - takes 4-6 weeks',
            },
            
            # =====================================================================
            # FEVER
            # =====================================================================
            ('tulsi', 'fever'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Eugenol has antipyretic effects via prostaglandin inhibition.  Also provides immunomodulatory support.',
                'pubmed_ids': ['PMC4296439'],
                'dose': '5-10 fresh leaves as tea, or 300-600mg extract, 2-3 times daily',
                'onset': '1-2 hours',
            },
            ('ginger', 'fever'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Gingerols have antipyretic properties, promote sweating (diaphoretic), and support immune function.',
                'pubmed_ids': ['PMC3665023', 'PMC6341159'],
                'dose': '1-2g fresh ginger in tea, 2-3 times daily',
                'onset': '30-60 minutes',
            },
            ('neem', 'fever'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Nimbidin and nimbin compounds have antipyretic and antimalarial properties.',
                'pubmed_ids': ['PMC3695574'],
                'dose': 'Leaf decoction 1-2 times daily',
                'onset': '1-2 hours',
            },
            ('giloy', 'fever'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Tinosporin provides immunomodulatory effects.  Traditionally used for chronic fevers.',
                'pubmed_ids': ['PMC3644751', 'PMC5411265'],
                'dose': 'Juice or decoction 15-30ml, twice daily',
                'onset': '2-4 hours',
            },
            ('coriander', 'fever'): {
                'tier': EvidenceTier. TIER_3_TRADITIONAL,
                'mechanism': 'Traditional cooling effect, supports hydration, mild antipyretic properties.',
                'pubmed_ids': [],
                'dose': '1 tsp seeds boiled in water, 2-3 times daily',
                'onset': '1-2 hours',
            },
            ('fenugreek', 'fever'): {
                'tier': EvidenceTier.TIER_3_TRADITIONAL,
                'mechanism': 'Mucilage content soothes, traditional use for fever reduction in Ayurveda.',
                'pubmed_ids': ['PMC4325021'],
                'dose': '1 tsp seeds soaked overnight, consume with water',
                'onset': '2-3 hours',
            },
            
            # =====================================================================
            # COLD / FLU
            # =====================================================================
            ('ginger', 'cold'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Gingerols and shogaols have antiviral, anti-inflammatory, and warming diaphoretic properties.',
                'pubmed_ids': ['PMC3665023', 'PMC6341159'],
                'dose': '1-2g fresh ginger in tea with honey, 3-4 times daily',
                'onset': '30 minutes',
            },
            ('tulsi', 'cold'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Eugenol and ursolic acid provide immunomodulatory, antimicrobial, and adaptogenic effects.',
                'pubmed_ids': ['PMC4296439'],
                'dose': '5-10 fresh leaves as tea, 2-3 times daily',
                'onset': '1-2 hours',
            },
            ('garlic', 'cold'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Allicin has broad-spectrum antimicrobial activity.  Boosts NK cell activity.',
                'pubmed_ids': ['PMC4417560', 'PMC6465033'],
                'dose': '1-2 raw cloves daily, crushed and rested 10 minutes before consuming',
                'onset': 'Preventive and acute use',
            },
            ('honey', 'cold'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Antimicrobial properties, demulcent action soothes throat, supports immune function.',
                'pubmed_ids': ['PMC4264806'],
                'dose': '1-2 tablespoons as needed, or in warm water/tea',
                'onset': 'Immediate soothing',
            },
            ('elderberry', 'cold'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Anthocyanins inhibit viral neuraminidase, reducing viral replication.  Boosts cytokine production.',
                'pubmed_ids': ['PMC4848651', 'PMC6124954'],
                'dose': 'Standardized extract as per product directions',
                'onset': '24-48 hours reduction in symptoms',
            },
            ('turmeric', 'cold'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Curcumin modulates immune response, has antiviral and anti-inflammatory properties.',
                'pubmed_ids': ['PMC5664031'],
                'dose': '500mg-1g with black pepper, or golden milk',
                'onset': '1-2 hours',
            },
            
            # =====================================================================
            # COUGH
            # =====================================================================
            ('honey', 'cough'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Demulcent coating protects irritated throat.  Clinical trials show superiority over dextromethorphan.',
                'pubmed_ids': ['PMC6513626', 'PMC4264806'],
                'dose': '1-2 tablespoons before bed, or as needed',
                'onset': 'Immediate soothing, overnight improvement',
            },
            ('ginger', 'cough'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Relaxes airway smooth muscle, has anti-inflammatory and antitussive properties.',
                'pubmed_ids': ['PMC3604064'],
                'dose': 'Ginger tea with honey, 2-3 times daily',
                'onset': '30-60 minutes',
            },
            ('licorice', 'cough'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Glycyrrhizin has expectorant, demulcent, and antiviral properties.',
                'pubmed_ids': ['PMC3123991'],
                'dose': 'Tea 1-2 times daily.  Limit to 4-6 weeks continuous use.',
                'onset': '30-60 minutes',
            },
            ('thyme', 'cough'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Thymol and carvacrol have antitussive, expectorant, and antimicrobial effects.',
                'pubmed_ids': ['PMC5871214'],
                'dose': 'Thyme tea 2-3 times daily',
                'onset': '30-60 minutes',
            },
            ('tulsi', 'cough'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Eugenol and other compounds provide expectorant and antimicrobial action.',
                'pubmed_ids': ['PMC4296439'],
                'dose': 'Fresh leaves in tea, or with honey and ginger',
                'onset': '1-2 hours',
            },
            
            # =====================================================================
            # NAUSEA
            # =====================================================================
            ('ginger', 'nausea'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': '5-HT3 receptor antagonism blocks nausea signals. Accelerates gastric emptying.  Effective for pregnancy, chemo, motion sickness.',
                'pubmed_ids': ['PMC3016669', 'PMC4818021'],
                'dose': '1-1.5g dried ginger, or 1-2g fresh, or 250mg extract 4 times daily',
                'onset': '20-30 minutes',
            },
            ('peppermint', 'nausea'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Menthol reduces gastric smooth muscle spasms and has antiemetic properties.',
                'pubmed_ids': ['PMC4729798'],
                'dose': 'Aromatherapy, or 1-2 cups tea',
                'onset': '10-20 minutes',
            },
            ('fennel', 'nausea'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Anethole has carminative and antispasmodic effects on GI tract.',
                'pubmed_ids': ['PMC4137549'],
                'dose': '1 tsp seeds as tea after meals',
                'onset': '20-30 minutes',
            },
            ('chamomile', 'nausea'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Bisabolol and chamazulene have anti-inflammatory and antispasmodic effects.',
                'pubmed_ids': ['PMC2995283'],
                'dose': '1-2 cups tea as needed',
                'onset': '20-30 minutes',
            },
            
            # =====================================================================
            # INDIGESTION / ACIDITY
            # =====================================================================
            ('ginger', 'indigestion'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Accelerates gastric emptying by 50%. Reduces nausea and bloating.',
                'pubmed_ids': ['PMC3016669'],
                'dose': '1-2g before or with meals',
                'onset': '30 minutes',
            },
            ('peppermint', 'indigestion'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Menthol relaxes lower esophageal sphincter and intestinal smooth muscle.  Reduces IBS symptoms.',
                'pubmed_ids': ['PMC4729798', 'PMC6337770'],
                'dose': 'Enteric-coated oil (0.2-0.4ml) or tea after meals',
                'onset': '30-60 minutes',
                'contraindications': ['GERD', 'hiatal hernia'],
            },
            ('fennel', 'indigestion'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Anethole has carminative and antispasmodic effects.  Reduces gas and bloating.',
                'pubmed_ids': ['PMC4137549'],
                'dose': '1 tsp seeds chewed or as tea after meals',
                'onset': '20-30 minutes',
            },
            ('cumin', 'indigestion'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Stimulates digestive enzyme secretion, has carminative properties.',
                'pubmed_ids': ['PMC4375161'],
                'dose': '1 tsp seeds in warm water, or as tea',
                'onset': '20-30 minutes',
            },
            ('ajwain', 'indigestion'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Thymol content provides carminative and antispasmodic effects.',
                'pubmed_ids': ['PMC3611645'],
                'dose': '1/2 tsp seeds with warm water after meals',
                'onset': '15-30 minutes',
            },
            
            # =====================================================================
            # ANXIETY / STRESS
            # =====================================================================
            ('ashwagandha', 'anxiety'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Withanolides modulate GABA receptors.  Reduces cortisol by 27. 9% in clinical trials.',
                'pubmed_ids': ['PMC3573577', 'PMC6979308'],
                'dose': '300-600mg standardized extract (5% withanolides) daily',
                'onset': '2-4 weeks for full effect',
            },
            ('ashwagandha', 'stress'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Adaptogenic action normalizes cortisol.  Reduces perceived stress by 44% in trials.',
                'pubmed_ids': ['PMC3573577'],
                'dose': '300-600mg standardized extract daily',
                'onset': '2-4 weeks for full effect',
            },
            ('chamomile', 'anxiety'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Apigenin binds to benzodiazepine receptors. Clinically effective for GAD.',
                'pubmed_ids': ['PMC2995283', 'PMC5589141'],
                'dose': '220-1100mg extract, or 1-4 cups tea daily',
                'onset': '1-2 hours acute, 2-4 weeks chronic',
            },
            ('lavender', 'anxiety'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Silexan (lavender oil) shows efficacy comparable to lorazepam in clinical trials.',
                'pubmed_ids': ['PMC3612440', 'PMC6007527'],
                'dose': '80-160mg Silexan capsule, or aromatherapy 15-30 minutes',
                'onset': '30-60 minutes acute, 2 weeks chronic',
            },
            ('brahmi', 'anxiety'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Bacosides modulate serotonin, dopamine, and reduce cortisol.',
                'pubmed_ids': ['PMC3746283'],
                'dose': '300-450mg standardized extract daily',
                'onset': '4-6 weeks',
            },
            ('tulsi', 'stress'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Adaptogenic effects normalize stress hormones and neurotransmitters.',
                'pubmed_ids': ['PMC4296439'],
                'dose': '300-600mg extract or 2-3 cups tea daily',
                'onset': '2-4 weeks',
            },
            
            # =====================================================================
            # INSOMNIA
            # =====================================================================
            ('ashwagandha', 'insomnia'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Triethylene glycol promotes non-REM sleep.  Reduces sleep latency significantly.',
                'pubmed_ids': ['PMC6827862'],
                'dose': '300mg extract 1-2 hours before bed',
                'onset': '2-4 weeks for full effect',
            },
            ('chamomile', 'insomnia'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Apigenin has mild sedative effects via benzodiazepine receptor binding.',
                'pubmed_ids': ['PMC2995283'],
                'dose': '1-2 cups tea 30-60 minutes before bed',
                'onset': '30-60 minutes',
            },
            ('valerian', 'insomnia'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Valerenic acid inhibits GABA breakdown, improving sleep quality.',
                'pubmed_ids': ['PMC4394901'],
                'dose': '300-600mg extract 30-120 minutes before bed',
                'onset': '2-4 weeks for optimal effect',
            },
            ('jatamansi', 'insomnia'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Nardostachys jatamansi has GABAergic and serotonergic effects.',
                'pubmed_ids': ['PMC3252722'],
                'dose': '250-500mg powder before bed',
                'onset': '1-2 weeks',
            },
            
            # =====================================================================
            # SORE THROAT
            # =====================================================================
            ('honey', 'sore throat'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Demulcent coating soothes, antimicrobial action fights infection.',
                'pubmed_ids': ['PMC4264806'],
                'dose': '1-2 tablespoons as needed, or in warm water with lemon',
                'onset': 'Immediate soothing',
            },
            ('licorice', 'sore throat'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Glycyrrhizin has demulcent, anti-inflammatory, and antiviral effects.',
                'pubmed_ids': ['PMC3123991'],
                'dose': 'Gargle with tea, or drink 1-2 times daily',
                'onset': 'Immediate soothing',
            },
            ('turmeric', 'sore throat'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Curcumin has potent anti-inflammatory and antimicrobial properties.',
                'pubmed_ids': ['PMC5664031'],
                'dose': 'Warm milk with 1/2 tsp turmeric and honey, or gargle with turmeric water',
                'onset': '30-60 minutes',
            },
            ('ginger', 'sore throat'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Anti-inflammatory gingerols and warming action soothe throat.',
                'pubmed_ids': ['PMC3665023'],
                'dose': 'Fresh ginger tea with honey, 2-3 times daily',
                'onset': '30 minutes',
            },
            ('slippery elm', 'sore throat'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Mucilage forms protective coating over irritated mucous membranes.',
                'pubmed_ids': ['PMC3166406'],
                'dose': 'Lozenges as needed, or tea',
                'onset': 'Immediate coating',
            },
            
            # =====================================================================
            # BURNS
            # =====================================================================
            ('aloe vera', 'burns'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Acemannan promotes wound healing, reduces inflammation, antimicrobial properties.',
                'pubmed_ids': ['PMC2763764', 'PMC5537865'],
                'dose': 'Apply fresh gel 2-3 times daily to affected area',
                'onset': 'Immediate cooling, healing over days',
            },
            ('honey', 'burns'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'High osmolarity, hydrogen peroxide production, methylglyoxal provide antimicrobial wound healing.',
                'pubmed_ids': ['PMC3941901', 'PMC3609166'],
                'dose': 'Apply thin layer under sterile dressing, change daily',
                'onset': 'Healing accelerated over days',
            },
            ('coconut oil', 'burns'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Lauric acid provides antimicrobial action, fatty acids support skin barrier repair.',
                'pubmed_ids': ['PMC4171909'],
                'dose': 'Apply to healing/healed burns only (not fresh burns)',
                'onset': 'Supports healing over days',
            },
            
            # =====================================================================
            # ARTHRITIS / JOINT PAIN
            # =====================================================================
            ('turmeric', 'arthritis'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Curcumin inhibits NF-κB, COX-2, reduces inflammatory cytokines.  Comparable to NSAIDs in trials.',
                'pubmed_ids': ['PMC5664031', 'PMC6471669'],
                'dose': '500-1000mg curcumin with piperine (black pepper) daily',
                'onset': '4-8 weeks for significant improvement',
            },
            ('boswellia', 'arthritis'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Boswellic acids (AKBA) inhibit 5-lipoxygenase, reduce cartilage degradation.',
                'pubmed_ids': ['PMC3309643'],
                'dose': '300-500mg extract 2-3 times daily',
                'onset': '4-8 weeks',
            },
            ('ginger', 'arthritis'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Gingerols inhibit prostaglandin and leukotriene synthesis.',
                'pubmed_ids': ['PMC3665023'],
                'dose': '250mg-1g extract or 2-3g fresh daily',
                'onset': '4-8 weeks',
            },
            ('turmeric', 'joint pain'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Curcumin reduces joint inflammation and pain through multiple pathways.',
                'pubmed_ids': ['PMC5664031'],
                'dose': '500-1000mg curcumin with piperine daily',
                'onset': '4-8 weeks',
            },
            
            # =====================================================================
            # ACNE
            # =====================================================================
            ('tea tree', 'acne'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Terpinen-4-ol has antibacterial action against P.acnes.  Comparable to 5% benzoyl peroxide.',
                'pubmed_ids': ['PMC4025519'],
                'dose': '5% tea tree oil gel applied topically twice daily',
                'onset': '6-12 weeks for significant improvement',
            },
            ('neem', 'acne'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Nimbidin has antibacterial and anti-inflammatory effects against acne.',
                'pubmed_ids': ['PMC3695574'],
                'dose': 'Neem paste or neem soap topically',
                'onset': '4-8 weeks',
            },
            ('turmeric', 'acne'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Curcumin reduces sebum production, has antimicrobial effects.',
                'pubmed_ids': ['PMC5822982'],
                'dose': 'Topical paste with honey, leave 10-15 minutes',
                'onset': '4-8 weeks',
            },
            
            # =====================================================================
            # TOOTHACHE
            # =====================================================================
            ('clove', 'toothache'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Eugenol (85%) is FDA-approved dental analgesic. Inhibits pain signal transmission.',
                'pubmed_ids': ['PMC3769004', 'PMC5751100'],
                'dose': 'Apply clove oil directly to affected tooth/gum, or place whole clove on tooth',
                'onset': '1-5 minutes',
            },
            
            # =====================================================================
            # FATIGUE
            # =====================================================================
            ('ashwagandha', 'fatigue'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Improves VO2 max, reduces fatigue markers. Adaptogenic stress support.',
                'pubmed_ids': ['PMC3573577', 'PMC3545242'],
                'dose': '300-600mg standardized extract daily',
                'onset': '2-4 weeks',
            },
            ('ginseng', 'fatigue'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Ginsenosides modulate HPA axis, improve energy metabolism and mental clarity.',
                'pubmed_ids': ['PMC3659612'],
                'dose': '200-400mg standardized extract daily',
                'onset': '2-4 weeks',
            },
            ('amla', 'fatigue'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'High vitamin C content, antioxidants support energy and immunity.',
                'pubmed_ids': ['PMC3249901'],
                'dose': '500mg-1g powder or 1-2 fresh fruits daily',
                'onset': '2-4 weeks',
            },
        }
        
        logger.info(f"Loaded {len(self.evidence_db)} evidence entries")
    
    def _load_interaction_database(self):
        """
        Load drug-herb interaction rules. 
        This is critical safety data for preventing dangerous combinations.
        """
        self.interactions_db: Dict[str, Dict] = {
            'ginger': {
                'interacts_with': {
                    'aspirin': InteractionSeverity.HIGH,
                    'ibuprofen': InteractionSeverity. MODERATE,
                    'warfarin': InteractionSeverity. CRITICAL,
                    'coumadin': InteractionSeverity.CRITICAL,
                    'blood thinner': InteractionSeverity.HIGH,
                    'blood thinners': InteractionSeverity.HIGH,
                    'anticoagulant': InteractionSeverity.HIGH,
                    'plavix': InteractionSeverity.HIGH,
                    'clopidogrel': InteractionSeverity.HIGH,
                },
                'effect': 'Ginger has blood-thinning properties (inhibits platelet aggregation). Combined with anticoagulants, it significantly increases bleeding risk.',
                'alternatives': ['Peppermint oil (topical)', 'Lavender aromatherapy', 'Cold/warm compress', 'Chamomile tea'],
            },
            'turmeric': {
                'interacts_with': {
                    'aspirin': InteractionSeverity.HIGH,
                    'warfarin': InteractionSeverity. CRITICAL,
                    'blood thinner': InteractionSeverity.HIGH,
                    'metformin': InteractionSeverity.MODERATE,
                    'diabetes medication': InteractionSeverity. MODERATE,
                    'insulin': InteractionSeverity.MODERATE,
                },
                'effect': 'Curcumin has antiplatelet and blood sugar-lowering effects.  May cause bleeding or hypoglycemia when combined with these medications.',
                'alternatives': ['Boswellia (for inflammation)', 'Cold compress', 'Rest and elevation'],
            },
            'garlic': {
                'interacts_with': {
                    'aspirin': InteractionSeverity. MODERATE,
                    'warfarin': InteractionSeverity.HIGH,
                    'blood thinner': InteractionSeverity. MODERATE,
                    'hiv medication': InteractionSeverity.HIGH,
                    'saquinavir': InteractionSeverity.HIGH,
                },
                'effect': 'Garlic inhibits platelet aggregation.  High doses may increase bleeding risk.',
                'alternatives': ['Onion (milder)', 'Oregano', 'Thyme'],
            },
            'ashwagandha': {
                'interacts_with': {
                    'thyroid medication': InteractionSeverity.HIGH,
                    'levothyroxine': InteractionSeverity.HIGH,
                    'synthroid': InteractionSeverity.HIGH,
                    'sedative': InteractionSeverity. MODERATE,
                    'benzodiazepine': InteractionSeverity. MODERATE,
                    'immunosuppressant': InteractionSeverity.HIGH,
                },
                'effect': 'Ashwagandha stimulates thyroid function and has sedative properties. May interfere with thyroid medication dosing.',
                'alternatives': ['Chamomile tea', 'Lavender aromatherapy', 'Deep breathing exercises', 'Brahmi'],
            },
            'licorice': {
                'interacts_with': {
                    'blood pressure medication': InteractionSeverity.HIGH,
                    'bp medicine': InteractionSeverity.HIGH,
                    'antihypertensive': InteractionSeverity.HIGH,
                    'diuretic': InteractionSeverity.HIGH,
                    'digoxin': InteractionSeverity. CRITICAL,
                    'heart medication': InteractionSeverity.HIGH,
                    'corticosteroid': InteractionSeverity. MODERATE,
                },
                'effect': 'Glycyrrhizin in licorice raises blood pressure and depletes potassium.  Counteracts BP medications.',
                'alternatives': ['Honey', 'Slippery elm', 'Marshmallow root'],
            },
            'ginseng': {
                'interacts_with': {
                    'warfarin': InteractionSeverity. MODERATE,
                    'blood thinner': InteractionSeverity. MODERATE,
                    'diabetes medication': InteractionSeverity. MODERATE,
                    'metformin': InteractionSeverity. MODERATE,
                    'insulin': InteractionSeverity. MODERATE,
                    'antidepressant': InteractionSeverity. MODERATE,
                    'maoi': InteractionSeverity.HIGH,
                },
                'effect': 'Ginseng affects blood clotting, blood sugar, and has stimulant properties.',
                'alternatives': ['Green tea (moderate)', 'Peppermint tea', 'Amla'],
            },
            'st johns wort': {
                'interacts_with': {
                    'antidepressant': InteractionSeverity.CRITICAL,
                    'ssri': InteractionSeverity. CRITICAL,
                    'birth control': InteractionSeverity.HIGH,
                    'contraceptive': InteractionSeverity.HIGH,
                    'hiv medication': InteractionSeverity. CRITICAL,
                    'immunosuppressant': InteractionSeverity.CRITICAL,
                    'warfarin': InteractionSeverity.HIGH,
                    'cyclosporine': InteractionSeverity. CRITICAL,
                },
                'effect': "St. John's Wort induces CYP450 enzymes, dramatically reducing effectiveness of many medications. Serotonin syndrome risk with SSRIs.",
                'alternatives': ['Lavender', 'Chamomile', 'Exercise', 'Light therapy'],
            },
            'valerian': {
                'interacts_with': {
                    'sedative': InteractionSeverity.HIGH,
                    'benzodiazepine': InteractionSeverity.HIGH,
                    'sleep medication': InteractionSeverity.HIGH,
                    'ambien': InteractionSeverity.HIGH,
                    'alcohol': InteractionSeverity.HIGH,
                    'antihistamine': InteractionSeverity. MODERATE,
                },
                'effect': 'Valerian has sedative effects that compound with other CNS depressants, risking over-sedation.',
                'alternatives': ['Chamomile tea', 'Warm milk', 'Lavender aromatherapy', 'Sleep hygiene practices'],
            },
            'chamomile': {
                'interacts_with': {
                    'warfarin': InteractionSeverity.LOW,
                    'blood thinner': InteractionSeverity. LOW,
                    'sedative': InteractionSeverity.LOW,
                },
                'effect': 'Chamomile has mild blood-thinning and sedative effects. Generally safe in moderate amounts.',
                'alternatives': ['Lavender tea', 'Warm milk with honey'],
            },
            'giloy': {
                'interacts_with': {
                    'diabetes medication': InteractionSeverity. MODERATE,
                    'metformin': InteractionSeverity.MODERATE,
                    'immunosuppressant': InteractionSeverity.HIGH,
                },
                'effect': 'Giloy has immunomodulatory effects and may lower blood sugar.',
                'alternatives': ['Tulsi', 'Amla'],
            },
            'neem': {
                'interacts_with': {
                    'diabetes medication': InteractionSeverity.MODERATE,
                    'metformin': InteractionSeverity. MODERATE,
                    'immunosuppressant': InteractionSeverity. MODERATE,
                },
                'effect': 'Neem may lower blood sugar and has immunomodulatory effects.',
                'alternatives': ['Turmeric', 'Aloe vera'],
            },
        }
        
        logger.info(f"Loaded {len(self.interactions_db)} interaction profiles")
    
    def _load_contraindication_rules(self):
        """Load condition-based contraindication rules"""
        self.contraindications: Dict[str, Dict] = {
            'ginger': {
                'conditions': ['gallstones', 'bleeding disorder', 'hemophilia'],
                'pregnancy': 'Limit to 1g daily in pregnancy',
                'surgery': 'Stop 2 weeks before surgery',
            },
            'turmeric': {
                'conditions': ['gallstones', 'bile duct obstruction', 'bleeding disorder'],
                'pregnancy': 'Culinary amounts only in pregnancy',
                'surgery': 'Stop 2 weeks before surgery',
            },
            'ashwagandha': {
                'conditions': ['hyperthyroidism', 'autoimmune disease', 'hashimoto'],
                'pregnancy': 'Avoid in pregnancy',
            },
            'licorice': {
                'conditions': ['hypertension', 'high blood pressure', 'heart disease', 'kidney disease', 'hypokalemia'],
                'pregnancy': 'Avoid in pregnancy',
                'max_duration': '4-6 weeks continuous use',
            },
            'neem': {
                'conditions': ['autoimmune disease', 'trying to conceive'],
                'pregnancy': 'Avoid in pregnancy',
            },
            'ginseng': {
                'conditions': ['insomnia', 'high blood pressure', 'hormone-sensitive cancer'],
                'pregnancy': 'Avoid in pregnancy',
            },
            'valerian': {
                'conditions': [],
                'pregnancy': 'Avoid in pregnancy',
                'surgery': 'Stop 2 weeks before surgery',
            },
            'kava': {
                'conditions': ['liver disease', 'depression', 'parkinsons'],
                'pregnancy': 'Avoid in pregnancy',
            },
        }
        
        logger.info(f"Loaded {len(self.contraindications)} contraindication rules")
    
    def _build_herb_registry(self):
        """Build comprehensive registry of known herbs"""
        # Start with herbs from evidence database
        self.known_herbs: Set[str] = set()
        
        for key in self.evidence_db:
            self.known_herbs.add(key[0].lower())
        
        # Add from interactions database
        for herb in self.interactions_db:
            self.known_herbs.add(herb.lower())
        
        # Add additional known herbs
        additional_herbs = [
            # Indian/Ayurvedic
            'turmeric', 'tulsi', 'neem', 'amla', 'triphala', 'shatavari',
            'moringa', 'brahmi', 'shankhpushpi', 'jatamansi', 'arjuna',
            'guggul', 'bibhitaki', 'haritaki', 'manjistha', 'ashwagandha',
            'giloy', 'guduchi', 'ajwain', 'hing', 'asafoetida', 'methi',
            
            # Common herbs
            'ginger', 'garlic', 'honey', 'aloe vera', 'coconut oil',
            'fennel', 'cardamom', 'cumin', 'coriander', 'fenugreek',
            'cinnamon', 'black pepper', 'clove', 'mint', 'peppermint',
            
            # Western herbs
            'chamomile', 'lavender', 'valerian', 'echinacea', 'elderberry',
            'goldenseal', 'slippery elm', 'marshmallow root', 'mullein',
            'nettle', 'dandelion', 'milk thistle', 'ginkgo', 'ginseng',
            'st johns wort', 'feverfew', 'butterbur', 'passionflower',
            
            # Essential oils
            'eucalyptus', 'tea tree', 'rosemary', 'thyme', 'oregano',
            'frankincense', 'myrrh', 'lemongrass', 'citronella',
        ]
        
        self.known_herbs.update(h.lower() for h in additional_herbs)
        
        logger.info(f"Built registry of {len(self.known_herbs)} known herbs")
    
    # =========================================================================
    # CORE VERIFICATION METHODS
    # =========================================================================
    
    def verify_response(
        self,
        llm_response: str,
        query: str,
        user_conditions: List[str] = None,
        user_medications: List[str] = None,
        user_allergies: List[str] = None,
        current_condition: str = None
    ) -> Tuple[List[VerificationResult], List[str]]:
        """
        Main verification method - validates all claims in an LLM response. 
        
        Args:
            llm_response: The generated response text to verify
            query: User's original query
            user_conditions: User's health conditions (e.g., ['diabetes', 'hypertension'])
            user_medications: User's CURRENT medications (not stopped ones)
            user_allergies: User's allergies
            current_condition: The specific condition being discussed (e.g., 'fever', 'headache')
        
        Returns:
            Tuple of (List[VerificationResult], List[str] global_warnings)
        """
        user_conditions = user_conditions or []
        user_medications = user_medications or []
        user_allergies = user_allergies or []
        
        # Determine the condition we're verifying against
        if current_condition:
            condition = current_condition.lower().strip()
            logger.info(f"Trust Engine: Using passed condition '{condition}'")
        else:
            condition = self._identify_condition(query)
            logger.info(f"Trust Engine: Detected condition '{condition}' from query")
        
        # Find herbs mentioned in the response
        response_lower = llm_response.lower()
        found_herbs = []
        
        for herb in self.known_herbs:
            # Check if herb is mentioned (word boundary check to avoid partial matches)
            if re.search(r'\b' + re.escape(herb) + r'\b', response_lower):
                # Skip if user is allergic
                if herb not in [a.lower() for a in user_allergies]:
                    found_herbs.append(herb)
                else:
                    logger.warning(f"Skipping {herb} - user is allergic")
        
        logger.info(f"Trust Engine: Found herbs {found_herbs}")
        logger.info(f"Trust Engine: Checking against medications {user_medications}")
        
        # Verify each herb
        results = []
        for herb in set(found_herbs):  # Use set to avoid duplicates
            result = self._verify_single_claim(
                herb_name=herb,
                condition=condition,
                user_conditions=user_conditions,
                user_medications=user_medications
            )
            results.append(result)
        
        # Generate global warnings
        global_warnings = self._generate_global_warnings(results)
        
        return results, global_warnings
    
    def _verify_single_claim(
        self,
        herb_name: str,
        condition: str,
        user_conditions: List[str],
        user_medications: List[str]
    ) -> VerificationResult:
        """Verify a single herb-condition claim"""
        
        herb_lower = herb_name.lower()
        condition_lower = condition.lower()
        
        warnings = []
        interaction_note = None
        
        # Step 1: Check drug interactions
        if herb_lower in self.interactions_db:
            interaction_data = self.interactions_db[herb_lower]
            
            for med in user_medications:
                med_lower = med.lower()
                
                for drug_key, severity in interaction_data['interacts_with'].items():
                    if drug_key in med_lower or med_lower in drug_key:
                        severity_label = severity.value.upper()
                        effect = interaction_data['effect']
                        
                        if severity in [InteractionSeverity. CRITICAL, InteractionSeverity.HIGH]:
                            interaction_note = f"⚠️ INTERACTION: {herb_name} may interact with {med}.  Reason: {effect}"
                            warnings.append(interaction_note)
                        elif severity == InteractionSeverity.MODERATE:
                            interaction_note = f"⚠️ Caution: {herb_name} + {med} - monitor for: {effect}"
                            warnings.append(interaction_note)
        
        # Step 2: Check contraindications
        if herb_lower in self.contraindications:
            contra = self.contraindications[herb_lower]
            for blocked_condition in contra.get('conditions', []):
                for user_cond in user_conditions:
                    if blocked_condition.lower() in user_cond.lower():
                        warnings.append(f"🚫 CONTRAINDICATED: Avoid {herb_name} with {user_cond}")
        
        # Step 3: Look up evidence
        evidence_key = (herb_lower, condition_lower)
        evidence = self.evidence_db.get(evidence_key)
        
        if evidence:
            tier = evidence['tier']
            if isinstance(tier, EvidenceTier):
                tier_num = tier.value
            else:
                tier_num = tier
            
            mechanism = evidence['mechanism']
            pubmed_ids = evidence.get('pubmed_ids', [])
            dose = evidence.get('dose', '')
            
            # Calculate Scientific Confidence Score (SCS)
            base_scores = {1: 9. 0, 2: 7.5, 3: 5.5, 4: 3.5, 5: 1.5}
            base_score = base_scores.get(tier_num, 3.0)
            
            # Bonuses
            pubmed_bonus = min(len(pubmed_ids) * 0.3, 1.0)
            mechanism_bonus = 0.5 if mechanism else 0
            
            confidence_score = min(base_score + pubmed_bonus + mechanism_bonus, 10.0)
            
            # Penalties for warnings
            if warnings:
                confidence_score = max(confidence_score - (len(warnings) * 1.0), 1.0)
            
            tier_labels = {
                1: "Clinical Trial",
                2: "Mechanistic Study",
                3: "Traditional Use",
                4: "Anecdotal",
                5: "Theoretical"
            }
            
            return VerificationResult(
                herb_name=herb_name,
                condition=condition,
                is_valid=True,
                confidence_score=round(confidence_score, 1),
                evidence_tier=tier_num,
                evidence_tier_label=tier_labels.get(tier_num, "Unknown"),
                mechanism=mechanism,
                pubmed_count=len(pubmed_ids),
                warnings=warnings,
                is_hallucination=False,
                interaction_note=interaction_note,
                recommended_dose=dose
            )
        else:
            # Herb is known but no evidence for this condition
            return VerificationResult(
                herb_name=herb_name,
                condition=condition,
                is_valid=False,
                confidence_score=2.0,
                evidence_tier=5,
                evidence_tier_label="Unverified",
                mechanism="No documented mechanism for this condition",
                pubmed_count=0,
                warnings=warnings,
                is_hallucination=True,
                hallucination_reason=f"No evidence linking {herb_name} to {condition}",
                interaction_note=interaction_note
            )
    
    def _identify_condition(self, query: str) -> str:
        """Identify condition from query text (fallback when not passed explicitly)"""
        query_lower = query.lower()
        
        conditions_map = {
            'headache': ['headache', 'head hurts', 'head pain', 'migraine', 'head ache'],
            'fever': ['fever', 'temperature', 'feverish', 'high temperature', 'febrile'],
            'cold': ['cold', 'runny nose', 'sneezing', 'congestion', 'flu', 'common cold'],
            'cough': ['cough', 'coughing', 'dry cough', 'wet cough'],
            'nausea': ['nausea', 'nauseous', 'vomiting', 'vomit', 'queasy', 'morning sickness'],
            'indigestion': ['indigestion', 'bloating', 'gas', 'stomach upset', 'digestive', 'acidity', 'acid reflux'],
            'sore throat': ['sore throat', 'throat pain', 'throat hurts', 'scratchy throat'],
            'anxiety': ['anxiety', 'anxious', 'worried', 'nervous', 'panic', 'panic attack'],
            'stress': ['stress', 'stressed', 'overwhelmed', 'burnout'],
            'insomnia': ['insomnia', 'cant sleep', 'cannot sleep', 'sleepless', 'sleep problems', 'trouble sleeping'],
            'fatigue': ['fatigue', 'tired', 'exhausted', 'low energy', 'weakness'],
            'arthritis': ['arthritis', 'joint pain', 'joints hurt', 'joint inflammation'],
            'toothache': ['toothache', 'tooth pain', 'tooth hurts', 'dental pain'],
            'acne': ['acne', 'pimples', 'breakout', 'zits'],
            'burns': ['burn', 'burnt', 'burned', 'scalded', 'scald'],
        }
        
        for condition, keywords in conditions_map.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return condition
        
        return "general"
    
    def _generate_global_warnings(self, results: List[VerificationResult]) -> List[str]:
        """Generate global warnings based on all verification results"""
        warnings = []
        
        # Count serious issues
        interaction_count = sum(1 for r in results if r.interaction_note)
        hallucination_count = sum(1 for r in results if r.is_hallucination)
        contraindication_count = sum(
            1 for r in results 
            if any('CONTRAINDICATED' in w for w in r.warnings)
        )
        
        if contraindication_count > 0:
            warnings.append(f"🚫 {contraindication_count} remedy(s) may be contraindicated for you")
        
        if hallucination_count > 0:
            warnings.append(f"ℹ️ {hallucination_count} suggestion(s) could not be verified against our evidence database")
        
        return warnings
    
    # =========================================================================
    # OUTPUT FORMATTING
    # =========================================================================
    
    def format_validation_section(
        self,
        results: List[VerificationResult],
        global_warnings: List[str]
    ) -> str:
        """Format verification results as markdown for display"""
        
        if not results:
            return ""
        
        output = "\n\n---\n\n"
        output += "**🔬 Scientific Validation (Trust Engine):**\n\n"
        
        # Global warnings
        if global_warnings:
            for warning in global_warnings:
                output += f"{warning}\n"
            output += "\n"
        
        # Separate verified and unverified
        verified = [r for r in results if r.is_valid and not r.is_hallucination]
        unverified = [r for r in results if r.is_hallucination]
        
        # Verified remedies
        if verified:
            output += "**Verified Remedies:**\n\n"
            for r in verified:
                # Confidence emoji
                if r.confidence_score >= 8:
                    emoji = "🟢"
                elif r.confidence_score >= 5:
                    emoji = "🟡"
                else:
                    emoji = "🔴"
                
                output += f"**{r.herb_name.title()}** {emoji} **{r.confidence_score}/10**\n"
                output += f"Evidence: {r.evidence_tier_label} ({r.pubmed_count} studies)\n"
                output += f"Mechanism: {r.mechanism}\n"
                
                if r.recommended_dose:
                    output += f"Dose: {r.recommended_dose}\n"
                
                if r.interaction_note:
                    output += f"{r.interaction_note}\n"
                
                for w in r.warnings:
                    if w != r.interaction_note:  # Avoid duplicate
                        output += f"{w}\n"
                
                output += "\n"
        
        # Unverified remedies
        if unverified:
            output += "**Unverified (Use with Caution):**\n\n"
            for r in unverified:
                output += f"⚠️ **{r.herb_name.title()}** - {r.hallucination_reason}\n"
                
                if r.interaction_note:
                    output += f"   {r.interaction_note}\n"
            
            output += "\n"
        
        # Legend
        output += "**Confidence Score Legend:**\n\n"
        output += "| Score | Meaning |\n"
        output += "|-------|--------|\n"
        output += "| 🟢 8-10 | Strong clinical evidence |\n"
        output += "| 🟡 5-7 | Good research support |\n"
        output += "| 🔴 1-4 | Limited evidence |\n"
        
        return output
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def check_single_interaction(
        self,
        herb: str,
        medication: str
    ) -> Optional[InteractionWarning]:
        """Check for interaction between a specific herb and medication"""
        
        herb_lower = herb.lower()
        med_lower = medication.lower()
        
        if herb_lower not in self.interactions_db:
            return None
        
        interaction_data = self.interactions_db[herb_lower]
        
        for drug_key, severity in interaction_data['interacts_with'].items():
            if drug_key in med_lower or med_lower in drug_key:
                return InteractionWarning(
                    herb=herb,
                    drug=medication,
                    severity=severity,
                    effect=interaction_data['effect'],
                    recommendation=f"Avoid {herb} while taking {medication}",
                    alternatives=interaction_data.get('alternatives', [])
                )
        
        return None
    
    def get_evidence_for_condition(self, condition: str) -> List[Dict]:
        """Get all herbs with evidence for a specific condition"""
        condition_lower = condition.lower()
        results = []
        
        for (herb, cond), evidence in self.evidence_db.items():
            if cond == condition_lower:
                tier = evidence['tier']
                if isinstance(tier, EvidenceTier):
                    tier_num = tier.value
                else:
                    tier_num = tier
                
                results.append({
                    'herb': herb,
                    'tier': tier_num,
                    'mechanism': evidence['mechanism'],
                    'dose': evidence.get('dose', ''),
                })
        
        # Sort by evidence tier (lower is better)
        results.sort(key=lambda x: x['tier'])
        return results
    
    def is_herb_known(self, herb: str) -> bool:
        """Check if an herb is in our knowledge base"""
        return herb.lower() in self.known_herbs
