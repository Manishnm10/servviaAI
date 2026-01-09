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
            ('jatamansi', 'insomnia'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Nardostachys jatamansi has GABAergic and serotonergic effects.',
                'pubmed_ids': ['PMC3252722'],
                'dose': '250-500mg powder before bed',
                'onset': '1-2 weeks',
            },
            ('lavender', 'insomnia'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Linalool modulates GABA receptors, promoting relaxation and sleep.',
                'pubmed_ids': ['PMC3612440'],
                'dose': 'Aromatherapy:  2-3 drops on pillow or in diffuser before bed',
                'onset': '15-30 minutes',
            },
            ('valerian', 'insomnia'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Valerenic acid increases GABA levels in the brain, promoting sleep.',
                'pubmed_ids': ['PMC4394901'],
                'dose': '300-600mg extract 30-60 minutes before bed',
                'onset': '2-4 weeks for full effect',
            },
            ('passionflower', 'insomnia'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Flavonoids bind to GABA receptors, reducing anxiety and promoting sleep.',
                'pubmed_ids': ['PMC2941540'],
                'dose': '250-500mg extract or 1-2 cups tea before bed',
                'onset': '30-60 minutes',
            },
            ('melatonin', 'insomnia'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Hormone that regulates circadian rhythm and sleep-wake cycles.',
                'pubmed_ids': ['PMC4273450'],
                'dose': '0.5-5mg 30-60 minutes before bed (start low)',
                'onset': '30-60 minutes',
            },
            ('magnesium', 'insomnia'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Regulates GABA and melatonin, promotes muscle relaxation.',
                'pubmed_ids': ['PMC5452159'],
                'dose': '200-400mg before bed',
                'onset': '1-2 weeks',
            },
            ('honey', 'insomnia'): {
                'tier': EvidenceTier.TIER_3_TRADITIONAL,
                'mechanism': 'May raise insulin slightly, allowing tryptophan to enter brain more easily.',
                'pubmed_ids': [],
                'dose': '1-2 teaspoons in warm milk before bed',
                'onset':  '30-60 minutes',
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
            # MENSTRUAL CRAMPS / DYSMENORRHEA  
            # =====================================================================
            ('ginger', 'menstrual cramps'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism':  'Gingerols inhibit prostaglandin synthesis, reducing uterine contractions.  Clinical trials show efficacy comparable to NSAIDs like ibuprofen.',
                'pubmed_ids':  ['PMC3518208', 'PMC4871956'],
                'dose': '250mg ginger powder 4 times daily, or 1-2g fresh ginger tea',
                'onset': '30-60 minutes',
            },
            ('chamomile', 'menstrual cramps'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Apigenin has antispasmodic effects on uterine smooth muscle, reducing cramping.',
                'pubmed_ids':  ['PMC2995283'],
                'dose': '2-3 cups chamomile tea daily during menstruation',
                'onset': '30-60 minutes',
            },
            ('cinnamon', 'menstrual cramps'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Cinnamaldehyde has antispasmodic and anti-inflammatory properties.  Clinical trials show significant pain reduction.',
                'pubmed_ids': ['PMC4443385'],
                'dose': '420mg extract 3 times daily, or 1/2 tsp powder in warm water',
                'onset': '1-2 hours',
            },
            ('fennel', 'menstrual cramps'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Anethole relaxes uterine smooth muscle.  Clinical trials show efficacy comparable to mefenamic acid.',
                'pubmed_ids': ['PMC4137549', 'PMC5770526'],
                'dose': '30mg fennel extract 4 times daily, or fennel seed tea',
                'onset': '30-60 minutes',
            },
            ('chasteberry', 'menstrual cramps'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Modulates dopamine receptors affecting prolactin, regulates menstrual cycle.  Clinical evidence for PMS and dysmenorrhea.',
                'pubmed_ids': ['PMC3659324', 'PMC6891434'],
                'dose':  '20-40mg standardized extract daily',
                'onset': '2-3 menstrual cycles for full effect',
            },
            ('turmeric', 'menstrual cramps'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Curcumin inhibits prostaglandin synthesis and has anti-inflammatory effects.',
                'pubmed_ids':  ['PMC5664031'],
                'dose': '500mg curcumin with black pepper, twice daily',
                'onset': '1-2 hours',
            },
            ('fenugreek', 'menstrual cramps'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Reduces prostaglandin levels, has antispasmodic properties.',
                'pubmed_ids':  ['PMC4325021'],
                'dose': '1800-2700mg seed powder daily during menstruation',
                'onset': '1-2 hours',
            },
            ('valerian', 'menstrual cramps'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Valerenic acid has antispasmodic effects on smooth muscle.',
                'pubmed_ids':  ['PMC4394901'],
                'dose': '255mg extract 3 times daily during menstruation',
                'onset': '30-60 minutes',
            },

            # =====================================================================
            # SUPPLEMENTS
            # =====================================================================
            ('magnesium', 'headache'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Magnesium deficiency is linked to migraines.  Supplementation reduces frequency and severity of tension-type and migraine headaches.',
                'pubmed_ids': ['PMC5566093', 'PMC6024559'],
                'dose': 'Adults: 400-600mg daily.  Children (6-12): 200-300mg daily.  Start low to avoid GI upset.',
                'onset': '3-4 months for preventive effect', 
            },
            ('magnesium', 'muscle pain'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Magnesium is essential for muscle relaxation.  Deficiency causes cramps and tension.',
                'pubmed_ids': ['PMC5637834'],
                'dose': '400-600mg daily',
                'onset':  '1-2 weeks',
            },
            ('ginger', 'joint pain'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Gingerols inhibit prostaglandin and leukotriene synthesis, reducing joint inflammation.',
                'pubmed_ids': ['PMC3665023'],
                'dose': '250mg-1g extract or 2-3g fresh daily',
                'onset': '4-8 weeks',
            },
            ('boswellia', 'joint pain'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Boswellic acids (AKBA) inhibit 5-lipoxygenase, reduce cartilage degradation and joint inflammation.',
                'pubmed_ids': ['PMC3309643'],
                'dose': '300-500mg extract 2-3 times daily',
                'onset': '4-8 weeks',
            },

            # =====================================================================
            # DIGESTIVE ISSUES
            # =====================================================================
            ('ginger', 'bloating'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Gingerols accelerate gastric emptying by 50%, reducing bloating and discomfort.',
                'pubmed_ids': ['PMC3016669'],
                'dose': '1-2g fresh ginger in tea, or chew small piece before meals',
                'onset': '30-60 minutes',
            },
            ('fennel', 'bloating'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Anethole has carminative and antispasmodic effects, reducing gas and bloating.',
                'pubmed_ids': ['PMC4137549'],
                'dose': '1 tsp fennel seeds chewed or as tea after meals',
                'onset': '20-30 minutes',
            },
            ('peppermint', 'bloating'): {
                'tier':  EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Menthol relaxes intestinal smooth muscle, reducing spasms and trapped gas.',
                'pubmed_ids': ['PMC4729798'],
                'dose': '1-2 cups peppermint tea after meals',
                'onset': '30 minutes',
            },
            ('ajwain', 'bloating'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Thymol content provides strong carminative effects.',
                'pubmed_ids':  ['PMC3611645'],
                'dose': '1/2 tsp seeds with warm water after meals',
                'onset': '15-30 minutes',
            },
            ('cumin', 'bloating'): {
                'tier':  EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Stimulates digestive enzymes, reduces gas formation.',
                'pubmed_ids': ['PMC4375161'],
                'dose': '1 tsp cumin seeds in warm water or as tea',
                'onset': '20-30 minutes',
            },
            ('ginger', 'constipation'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Stimulates gastric motility and promotes bowel movements.',
                'pubmed_ids': ['PMC3016669'],
                'dose':  'Ginger tea 2-3 times daily',
                'onset': '2-6 hours',
            },
            ('triphala', 'constipation'): {
                'tier':  EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Gentle laxative effect, promotes healthy bowel movements without dependency.',
                'pubmed_ids': ['PMC5567597'],
                'dose': '1-2g powder in warm water before bed',
                'onset': '6-12 hours',
            },
            ('psyllium', 'constipation'): {
                'tier':  EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Soluble fiber absorbs water, adds bulk to stool, promotes regularity.',
                'pubmed_ids': ['PMC6358997'],
                'dose': '5-10g with plenty of water, 1-2 times daily',
                'onset': '12-72 hours',
            },
            ('aloe vera', 'constipation'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Anthraquinones stimulate intestinal contractions.',
                'pubmed_ids':  ['PMC2763764'],
                'dose': '100-200ml aloe juice daily (short term only)',
                'onset': '6-12 hours',
                'contraindications': ['pregnancy', 'kidney disease'],
            },
            ('ginger', 'diarrhea'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Anti-inflammatory properties soothe gut, may reduce intestinal spasms.',
                'pubmed_ids': ['PMC3665023'],
                'dose': 'Weak ginger tea, sipped slowly',
                'onset': '1-2 hours',
            },
            ('chamomile', 'diarrhea'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Antispasmodic and anti-inflammatory effects calm intestinal irritation.',
                'pubmed_ids': ['PMC2995283'],
                'dose': '1-2 cups chamomile tea',
                'onset': '1-2 hours',
            },
        
            # =====================================================================
            # RESPIRATORY CONDITIONS
            # =====================================================================
            ('eucalyptus', 'congestion'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Eucalyptol (1,8-cineole) thins mucus and opens airways.',
                'pubmed_ids': ['PMC5206475'],
                'dose': 'Steam inhalation with 3-5 drops oil in hot water',
                'onset':  '10-15 minutes',
            },
            ('peppermint', 'congestion'): {
                'tier':  EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Menthol activates cold receptors, creating sensation of easier breathing.',
                'pubmed_ids': ['PMC4729798'],
                'dose':  'Steam inhalation or peppermint tea',
                'onset': '10-15 minutes',
            },
            ('ginger', 'congestion'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Warming effect promotes circulation, helps clear nasal passages.',
                'pubmed_ids': ['PMC3665023'],
                'dose': 'Hot ginger tea with honey and lemon',
                'onset':  '20-30 minutes',
            },
            ('tulsi', 'congestion'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Expectorant and antimicrobial properties help clear respiratory tract.',
                'pubmed_ids': ['PMC4296439'],
                'dose': 'Tulsi tea 2-3 times daily',
                'onset': '1-2 hours',
            },
            ('honey', 'congestion'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Demulcent and antimicrobial, soothes throat and may thin mucus.',
                'pubmed_ids': ['PMC4264806'],
                'dose': '1-2 tablespoons in warm water or tea',
                'onset': 'Immediate soothing',
            },
            ('thyme', 'bronchitis'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Thymol has expectorant, antimicrobial, and bronchodilator effects.',
                'pubmed_ids': ['PMC5871214'],
                'dose': 'Thyme tea 3-4 times daily',
                'onset': '1-2 hours',
            },
            ('licorice', 'bronchitis'): {
                'tier':  EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Glycyrrhizin has expectorant and anti-inflammatory properties.',
                'pubmed_ids':  ['PMC3123991'],
                'dose': 'Licorice tea 1-2 times daily (limit to 4 weeks)',
                'onset': '1-2 hours',
                'contraindications': ['hypertension', 'heart disease'],
            },
            ('mullein', 'bronchitis'): {
                'tier': EvidenceTier.TIER_3_TRADITIONAL,
                'mechanism': 'Saponins act as expectorants, mucilage soothes airways.',
                'pubmed_ids': [],
                'dose': 'Mullein tea 2-3 times daily',
                'onset': '1-2 hours',
            },
        
            # =====================================================================
            # SKIN CONDITIONS
            # =====================================================================
            ('aloe vera', 'sunburn'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Acemannan promotes healing, provides cooling relief, anti-inflammatory.',
                'pubmed_ids': ['PMC2763764'],
                'dose':  'Apply fresh gel liberally to affected area 3-4 times daily',
                'onset': 'Immediate cooling, healing over days',
            },
            ('coconut oil', 'dry skin'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Lauric acid and fatty acids restore skin barrier and moisture.',
                'pubmed_ids': ['PMC4171909'],
                'dose': 'Apply to skin after bathing while still damp',
                'onset':  'Immediate moisturizing',
            },
            ('turmeric', 'eczema'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Curcumin reduces inflammatory cytokines and oxidative stress in skin.',
                'pubmed_ids': ['PMC5822982'],
                'dose': 'Topical paste (turmeric + coconut oil) or oral supplementation',
                'onset':  '2-4 weeks',
            },
            ('neem', 'eczema'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Nimbidin has anti-inflammatory and antimicrobial properties.',
                'pubmed_ids': ['PMC3695574'],
                'dose': 'Neem oil diluted with carrier oil, applied topically',
                'onset':  '1-2 weeks',
            },
            ('oatmeal', 'eczema'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Colloidal oatmeal forms protective barrier, reduces itching and inflammation.',
                'pubmed_ids': ['PMC4499292'],
                'dose': 'Oatmeal bath (1-2 cups) or colloidal oatmeal cream',
                'onset': 'Immediate relief, improvement over days',
            },
            ('tea tree', 'fungal infection'): {
                'tier':  EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Terpinen-4-ol has potent antifungal activity.',
                'pubmed_ids': ['PMC4025519'],
                'dose': '5-10% tea tree oil applied topically twice daily',
                'onset': '2-4 weeks',
            },
            ('garlic', 'fungal infection'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Allicin and ajoene have antifungal properties.',
                'pubmed_ids': ['PMC4417560'],
                'dose': 'Crushed garlic paste applied topically (test first)',
                'onset': '1-2 weeks',
            },
        
            # =====================================================================
            # PAIN CONDITIONS
            # =====================================================================
            ('turmeric', 'back pain'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Curcumin inhibits inflammatory pathways, reduces pain mediators.',
                'pubmed_ids': ['PMC5664031'],
                'dose': '500-1000mg curcumin with black pepper daily, or turmeric milk',
                'onset': '2-4 weeks',
            },
            ('ginger', 'back pain'): {
                'tier':  EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Gingerols reduce prostaglandins, anti-inflammatory effect.',
                'pubmed_ids': ['PMC3665023'],
                'dose': 'Ginger tea 2-3 times daily, or topical ginger compress',
                'onset': '1-2 weeks',
            },
            ('capsaicin', 'back pain'): {
                'tier':  EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Depletes substance P, reducing pain signal transmission.',
                'pubmed_ids': ['PMC5222580'],
                'dose': 'Topical cream (0.025-0.075%) applied 3-4 times daily',
                'onset': '1-2 weeks of regular use',
            },
            ('clove', 'muscle pain'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Eugenol has analgesic and anti-inflammatory properties.',
                'pubmed_ids': ['PMC3769004'],
                'dose': 'Diluted clove oil massage on affected area',
                'onset': '15-30 minutes',
            },
            ('peppermint', 'muscle pain'): {
                'tier':  EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Menthol provides cooling sensation, mild analgesic effect.',
                'pubmed_ids': ['PMC4729798'],
                'dose': 'Diluted peppermint oil massage',
                'onset': '10-20 minutes',
            },
            ('arnica', 'muscle pain'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Helenalin reduces inflammation and bruising.',
                'pubmed_ids': ['PMC5843686'],
                'dose': 'Arnica gel applied topically 2-3 times daily',
                'onset': '1-3 days',
            },
            ('epsom salt', 'muscle pain'): {
                'tier': EvidenceTier.TIER_3_TRADITIONAL,
                'mechanism': 'Magnesium absorption through skin may relax muscles (debated).',
                'pubmed_ids': [],
                'dose': '1-2 cups in warm bath, soak 15-20 minutes',
                'onset': 'Immediate relaxation',
            },
        
            # =====================================================================
            # IMMUNE SUPPORT
            # =====================================================================
            ('elderberry', 'flu'): {
                'tier':  EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Anthocyanins inhibit viral neuraminidase, boost cytokine production.',
                'pubmed_ids': ['PMC4848651', 'PMC6124954'],
                'dose': 'Standardized extract as per product directions',
                'onset': '24-48 hours symptom reduction',
            },
            ('echinacea', 'cold'): {
                'tier':  EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Polysaccharides and alkamides stimulate immune cell activity.',
                'pubmed_ids': ['PMC3062766'],
                'dose': '300mg extract 3 times daily at first sign of cold',
                'onset': 'Best if started early in infection',
            },
            ('garlic', 'immune support'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Allicin boosts NK cell activity and has antimicrobial properties.',
                'pubmed_ids': ['PMC4417560', 'PMC6465033'],
                'dose': '2-3 raw cloves daily (crush and rest 10 min before eating)',
                'onset': 'Ongoing immune support',
            },
            ('amla', 'immune support'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'High vitamin C content and antioxidants support immune function.',
                'pubmed_ids':  ['PMC3249901'],
                'dose': '500mg-1g powder or 1-2 fresh fruits daily',
                'onset': 'Ongoing immune support',
            },
            ('astragalus', 'immune support'): {
                'tier':  EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Polysaccharides enhance immune cell function.',
                'pubmed_ids':  ['PMC5758356'],
                'dose': '250-500mg extract daily',
                'onset': '2-4 weeks',
            },
        
            # =====================================================================
            # ORAL HEALTH
            # =====================================================================
            ('clove', 'gum pain'): {
                'tier':  EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Eugenol is FDA-approved dental analgesic.',
                'pubmed_ids': ['PMC3769004'],
                'dose': 'Apply clove oil to affected gum with cotton swab',
                'onset': '1-5 minutes',
            },
            ('salt water', 'gum pain'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Hypertonic solution reduces swelling, antimicrobial effect.',
                'pubmed_ids': [],
                'dose': '1/2 tsp salt in warm water, swish for 30 seconds',
                'onset': 'Immediate relief',
            },
            ('turmeric', 'gum inflammation'): {
                'tier':  EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Curcumin reduces inflammatory cytokines in gum tissue.',
                'pubmed_ids': ['PMC5664031'],
                'dose': 'Turmeric paste applied to gums, or turmeric mouthwash',
                'onset': '1-2 weeks',
            },
            ('oil pulling', 'oral health'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Mechanical removal of bacteria, may reduce plaque.',
                'pubmed_ids': ['PMC5198813'],
                'dose': 'Swish 1 tbsp coconut/sesame oil for 15-20 min daily',
                'onset': '2-4 weeks',
            },
        
            # =====================================================================
            # HAIR AND SCALP
            # =====================================================================
            ('coconut oil', 'hair loss'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Lauric acid penetrates hair shaft, reduces protein loss.',
                'pubmed_ids': ['PMC4387693'],
                'dose': 'Warm oil scalp massage 1-2 times weekly',
                'onset': '4-8 weeks',
            },
            ('rosemary', 'hair loss'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Improves scalp circulation, comparable to minoxidil in one study.',
                'pubmed_ids': ['PMC4458925'],
                'dose': 'Rosemary oil diluted in carrier oil, massaged into scalp',
                'onset': '3-6 months',
            },
            ('amla', 'hair health'): {
                'tier':  EvidenceTier.TIER_3_TRADITIONAL,
                'mechanism': 'Vitamin C and antioxidants support hair follicle health.',
                'pubmed_ids': ['PMC3249901'],
                'dose': 'Amla oil scalp massage or amla powder hair mask',
                'onset': '4-8 weeks',
            },
            ('tea tree', 'dandruff'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Antifungal activity against Malassezia (dandruff-causing fungus).',
                'pubmed_ids': ['PMC4025519'],
                'dose': '5% tea tree oil shampoo or add drops to regular shampoo',
                'onset': '2-4 weeks',
            },
            ('neem', 'dandruff'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Antifungal and anti-inflammatory properties.',
                'pubmed_ids': ['PMC3695574'],
                'dose': 'Neem oil scalp treatment or neem water rinse',
                'onset':  '2-4 weeks',
            },
        
            # =====================================================================
            # WOMEN'S HEALTH (Additional)
            # =====================================================================
            ('raspberry leaf', 'menstrual cramps'): {
                'tier':  EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Fragarine has uterine tonic and antispasmodic effects.',
                'pubmed_ids': ['PMC3192906'],
                'dose':  '1-2 cups tea daily during menstruation',
                'onset': '30-60 minutes',
            },
            ('dong quai', 'menstrual cramps'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Relaxes uterine muscle, improves blood flow.',
                'pubmed_ids': ['PMC3678828'],
                'dose': '200-500mg extract daily',
                'onset': '1-2 cycles',
                'contraindications': ['pregnancy', 'heavy bleeding', 'blood thinners'],
            },
            ('black cohosh', 'menopause symptoms'): {
                'tier':  EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Triterpene glycosides have estrogen-like effects on certain receptors.',
                'pubmed_ids': ['PMC5765531'],
                'dose': '20-40mg standardized extract twice daily',
                'onset': '4-8 weeks',
                'contraindications': ['liver disease', 'hormone-sensitive cancers'],
            },
            ('evening primrose', 'pms'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Gamma-linolenic acid (GLA) modulates prostaglandins.',
                'pubmed_ids': ['PMC3033240'],
                'dose': '500-1000mg daily',
                'onset': '2-3 cycles',
            },
            ('shatavari', 'hormonal balance'): {
                'tier':  EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Phytoestrogens and saponins support female reproductive health.',
                'pubmed_ids': ['PMC3136066'],
                'dose': '500-1000mg powder or extract daily',
                'onset': '4-8 weeks',
            },
        
            # =====================================================================
            # CARDIOVASCULAR SUPPORT
            # =====================================================================
            ('garlic', 'high blood pressure'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Allicin promotes vasodilation, reduces blood pressure by 5-8 mmHg.',
                'pubmed_ids': ['PMC6465033', 'PMC4266250'],
                'dose': '600-1200mg aged garlic extract daily, or 2-3 raw cloves',
                'onset':  '8-12 weeks',
            },
            ('hibiscus', 'high blood pressure'): {
                'tier':  EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Anthocyanins act as ACE inhibitors, promote vasodilation.',
                'pubmed_ids': ['PMC5465813'],
                'dose': '1-2 cups hibiscus tea daily',
                'onset': '2-6 weeks',
            },
            ('hawthorn', 'heart health'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Flavonoids improve coronary blood flow, have mild inotropic effect.',
                'pubmed_ids': ['PMC3249900'],
                'dose': '160-900mg extract daily',
                'onset': '6-8 weeks',
            },
            ('omega 3', 'heart health'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'EPA and DHA reduce triglycerides, inflammation, and arrhythmia risk.',
                'pubmed_ids': ['PMC6566772'],
                'dose': '1-4g EPA+DHA daily',
                'onset': '4-12 weeks',
            },
            ('cinnamon', 'blood sugar'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Cinnamaldehyde improves insulin sensitivity and glucose uptake.',
                'pubmed_ids': ['PMC4003790'],
                'dose': '1-6g powder daily, or 120-500mg extract',
                'onset':  '4-8 weeks',
            },
            ('fenugreek', 'blood sugar'): {
                'tier':  EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Soluble fiber slows carbohydrate absorption, improves insulin response.',
                'pubmed_ids': ['PMC4325021'],
                'dose': '5-50g seeds soaked overnight, or 500mg extract',
                'onset': '4-8 weeks',
            },
        
            # =====================================================================
            # COGNITIVE FUNCTION
            # =====================================================================
            ('brahmi', 'memory'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Bacosides enhance synaptic transmission, improve memory consolidation.',
                'pubmed_ids': ['PMC3746283'],
                'dose': '300-450mg standardized extract daily',
                'onset': '4-12 weeks',
            },
            ('ginkgo', 'memory'): {
                'tier':  EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Flavonoids improve cerebral blood flow and antioxidant protection.',
                'pubmed_ids': ['PMC3166615'],
                'dose': '120-240mg standardized extract daily',
                'onset': '6-12 weeks',
                'contraindications': ['blood thinners', 'seizure disorders'],
            },
            ('turmeric', 'brain health'): {
                'tier':  EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Curcumin crosses blood-brain barrier, reduces neuroinflammation.',
                'pubmed_ids': ['PMC5664031'],
                'dose': '500-1000mg curcumin with piperine daily',
                'onset': '4-8 weeks',
            },
            ('ashwagandha', 'memory'): {
                'tier':  EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Withanolides reduce cortisol and oxidative stress affecting cognition.',
                'pubmed_ids': ['PMC3573577'],
                'dose': '300-600mg standardized extract daily',
                'onset': '8-12 weeks',
            },
            ('rosemary', 'concentration'): {
                'tier':  EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Carnosic acid and 1,8-cineole improve alertness and cognitive performance.',
                'pubmed_ids': ['PMC4749867'],
                'dose': 'Aromatherapy or rosemary tea',
                'onset': '20-30 minutes',
            },
        
            # =====================================================================
            # EYE HEALTH
            # =====================================================================
            ('chamomile', 'eye strain'): {
                'tier': EvidenceTier.TIER_3_TRADITIONAL,
                'mechanism': 'Anti-inflammatory properties soothe tired eyes.',
                'pubmed_ids': [],
                'dose': 'Cooled chamomile tea bags as eye compress for 10-15 minutes',
                'onset': 'Immediate relief',
            },
            ('cucumber', 'eye strain'): {
                'tier': EvidenceTier.TIER_3_TRADITIONAL,
                'mechanism':  'Cooling effect reduces puffiness and soothes eyes.',
                'pubmed_ids': [],
                'dose': 'Chilled cucumber slices on closed eyes for 10-15 minutes',
                'onset': 'Immediate relief',
            },
            ('rose water', 'eye irritation'): {
                'tier': EvidenceTier. TIER_3_TRADITIONAL,
                'mechanism': 'Anti-inflammatory and soothing properties.',
                'pubmed_ids': [],
                'dose': 'Few drops in eyes or as compress',
                'onset': 'Immediate soothing',
            },
        
            # =====================================================================
            # MOTION SICKNESS / TRAVEL
            # =====================================================================
            ('ginger', 'motion sickness'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': '5-HT3 receptor antagonism reduces nausea signals from vestibular system.',
                'pubmed_ids': ['PMC3016669'],
                'dose': '1g ginger 30 minutes before travel, then 500mg every 4 hours',
                'onset':  '30 minutes',
            },
            ('peppermint', 'motion sickness'): {
                'tier':  EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Menthol calms stomach muscles and reduces nausea sensation.',
                'pubmed_ids': ['PMC4729798'],
                'dose': 'Peppermint tea or aromatherapy during travel',
                'onset': '15-30 minutes',
            },
        
            # =====================================================================
            # HANGOVER
            # =====================================================================
            ('ginger', 'hangover'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Anti-nausea effects help with hangover symptoms.',
                'pubmed_ids': ['PMC3016669'],
                'dose': 'Ginger tea with honey',
                'onset': '30-60 minutes',
            },
            ('turmeric', 'hangover'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Supports liver detoxification, reduces inflammation.',
                'pubmed_ids': ['PMC5664031'],
                'dose':  'Turmeric milk or golden latte',
                'onset': '1-2 hours',
            },
            ('peppermint', 'hangover'): {
                'tier':  EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Relieves nausea and headache symptoms.',
                'pubmed_ids': ['PMC4729798'],
                'dose': 'Peppermint tea',
                'onset': '20-30 minutes',
            },
        
            # =====================================================================
            # ENERGY / VITALITY
            # =====================================================================
            ('maca', 'energy'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Adaptogenic effects support adrenal function and energy levels.',
                'pubmed_ids': ['PMC3184420'],
                'dose': '1. 5-3g powder daily',
                'onset': '2-4 weeks',
            },
            ('green tea', 'energy'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'L-theanine + caffeine provides calm, focused energy.',
                'pubmed_ids': ['PMC3518171'],
                'dose': '2-3 cups daily',
                'onset': '30-60 minutes',
            },
            ('moringa', 'energy'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Rich in nutrients, antioxidants, and iron that combat fatigue.',
                'pubmed_ids': ['PMC5745501'],
                'dose': '1-2 tsp powder daily in smoothie or water',
                'onset': '1-2 weeks',
            },
        

            # =====================================================================
            # ADDITIONAL FATIGUE/ENERGY ENTRIES
            # =====================================================================
            ('green tea', 'fatigue'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'L-theanine + caffeine provides calm, focused energy without jitters.',
                'pubmed_ids': ['PMC3518171'],
                'dose': '2-3 cups daily',
                'onset': '30-60 minutes',
            },
            ('moringa', 'fatigue'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Rich in iron, vitamins, and antioxidants that combat fatigue.',
                'pubmed_ids': ['PMC5745501'],
                'dose': '1-2 tsp powder daily',
                'onset': '1-2 weeks',
            },

            # =====================================================================
            # ADDITIONAL MEMORY/COGNITIVE ENTRIES
            # =====================================================================
            ('rosemary', 'memory'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Carnosic acid and 1,8-cineole improve alertness and cognitive performance via acetylcholinesterase inhibition.',
                'pubmed_ids': ['PMC4749867'],
                'dose': 'Aromatherapy or rosemary tea',
                'onset': '20-30 minutes',
            },
            ('omega 3', 'memory'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'DHA is essential for brain structure and cognitive function.',
                'pubmed_ids': ['PMC6566772'],
                'dose': '1-2g EPA+DHA daily',
                'onset': '8-12 weeks',
            },
            ('fish oil', 'memory'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism':  'EPA and DHA support neuronal membrane health and reduce neuroinflammation.',
                'pubmed_ids': ['PMC6566772'],
                'dose': '1-2g EPA+DHA daily',
                'onset': '8-12 weeks',
            },

            # =====================================================================
            # ADDITIONAL MUSCLE PAIN ENTRIES
            # =====================================================================
            ('turmeric', 'muscle pain'): {
                'tier': EvidenceTier. TIER_2_MECHANISTIC,
                'mechanism': 'Curcumin inhibits inflammatory pathways and reduces delayed onset muscle soreness (DOMS).',
                'pubmed_ids': ['PMC5664031'],
                'dose': '500-1000mg curcumin with black pepper daily',
                'onset': '2-4 days',
            },
            ('ginger', 'muscle pain'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Gingerols reduce prostaglandins, providing anti-inflammatory relief for sore muscles.',
                'pubmed_ids': ['PMC3665023'],
                'dose': '2g fresh ginger or ginger tea daily',
                'onset': '24-48 hours',
            },

            # =====================================================================
            # ADDITIONAL DANDRUFF/SCALP ENTRIES
            # =====================================================================
            ('coconut oil', 'dandruff'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Lauric acid has antifungal properties and moisturizes dry scalp.',
                'pubmed_ids': ['PMC4171909'],
                'dose': 'Warm oil scalp massage 1-2 times weekly before washing',
                'onset': '2-4 weeks',
            },
            ('aloe vera', 'dandruff'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Anti-inflammatory and antifungal properties soothe scalp and reduce flaking.',
                'pubmed_ids': ['PMC2763764'],
                'dose': 'Apply fresh gel to scalp, leave 30 minutes, rinse',
                'onset': '2-4 weeks',
            },

            # =====================================================================
            # ADDITIONAL CONSTIPATION ENTRIES
            # =====================================================================
            ('prunes', 'constipation'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Sorbitol and fiber content provide natural laxative effect.',
                'pubmed_ids': ['PMC4291444'],
                'dose': '50g (about 5-6 prunes) daily',
                'onset': '6-12 hours',
            },
            ('flaxseed', 'constipation'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Soluble and insoluble fiber adds bulk and promotes bowel movements.',
                'pubmed_ids': ['PMC6124790'],
                'dose': '1-2 tablespoons ground flaxseed with water daily',
                'onset':  '12-24 hours',
            },
            ('senna', 'constipation'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Sennosides stimulate intestinal contractions.',
                'pubmed_ids':  ['PMC4027800'],
                'dose': 'Senna tea before bed (short-term use only)',
                'onset': '6-12 hours',
            },

            # =====================================================================
            # WOUNDS / CUTS / BLEEDING
            # =====================================================================
            ('salt water', 'wound'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Hypertonic saline solution has antiseptic properties, helps clean wounds and promotes healing.',
                'pubmed_ids': ['PMC4158441'],
                'dose': '1/2 tsp salt in 1 cup warm water, rinse or clean wound 2-3 times daily',
                'onset': 'Immediate cleansing, healing over days',
            },
            ('salt water', 'bleeding'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Salt water rinse helps clean oral wounds and has mild antiseptic properties.',
                'pubmed_ids': ['PMC4158441'],
                'dose': 'Gentle rinse 2-3 times daily',
                'onset': 'Immediate cleansing',
            },
            ('turmeric', 'wound'): {
                'tier': EvidenceTier.TIER_2_MECHANISTIC,
                'mechanism': 'Curcumin has antimicrobial, anti-inflammatory properties and promotes wound healing by enhancing collagen deposition.',
                'pubmed_ids': ['PMC5664031', 'PMC2929771'],
                'dose': 'Turmeric paste applied topically to wound',
                'onset': '2-5 days for healing improvement',
            },
            ('turmeric', 'bleeding'): {
                'tier': EvidenceTier.TIER_3_TRADITIONAL,
                'mechanism': 'Traditional use as hemostatic agent; curcumin may help with wound closure.',
                'pubmed_ids':  ['PMC2929771'],
                'dose':  'Turmeric paste applied to minor cuts',
                'onset': 'Minutes to hours',
            },
            ('aloe vera', 'wound'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Acemannan and other compounds promote wound healing, reduce inflammation, and have antimicrobial effects.',
                'pubmed_ids': ['PMC2763764', 'PMC5537865'],
                'dose': 'Apply fresh gel 2-3 times daily to affected area',
                'onset': 'Healing accelerated over days',
            },
            ('honey', 'wound'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'High osmolarity, hydrogen peroxide production, and methylglyoxal provide antimicrobial wound healing properties.',
                'pubmed_ids': ['PMC3941901', 'PMC3609166'],
                'dose': 'Apply thin layer under sterile dressing',
                'onset': 'Healing accelerated over days',
            },
            ('ice', 'bruise'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Cold therapy constricts blood vessels, reduces swelling, inflammation, and numbs pain.',
                'pubmed_ids': ['PMC3781860'],
                'dose': 'Apply ice pack wrapped in cloth for 10-15 minutes',
                'onset': 'Immediate pain relief, reduced swelling over hours',
            },
            ('ice', 'injury'): {
                'tier': EvidenceTier.TIER_1_CLINICAL,
                'mechanism': 'Cryotherapy reduces blood flow to injured area, minimizing swelling and bruising.',
                'pubmed_ids': ['PMC3781860'],
                'dose': '10-15 minutes every 1-2 hours for first 48 hours',
                'onset':  'Immediate',
            },
            ('arnica', 'bruise'): {
                'tier': EvidenceTier. TIER_1_CLINICAL,
                'mechanism': 'Helenalin reduces inflammation and bruising, speeds healing of soft tissue injuries.',
                'pubmed_ids': ['PMC5843686'],
                'dose': 'Arnica gel applied topically 2-3 times daily',
                'onset': '1-3 days',
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
        self.known_herbs:  Set[str] = set()
    
        for key in self.evidence_db:
            self.known_herbs.add(key[0]. lower())
    
        for herb in self.interactions_db:
            self.known_herbs.add(herb.lower())
    
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
        
            # Women's health herbs
            'chasteberry', 'vitex', 'evening primrose', 'dong quai',
            'black cohosh', 'red raspberry leaf', 'cramp bark', 'motherwort',
            'raspberry leaf', 'wild yam', 'maca', 'saffron', 'rose',
        
            # Additional herbs
            'hibiscus', 'lemon balm', 'boswellia', 'devils claw',
            'white willow', 'willow bark', 'meadowsweet', 'cats claw', 
            'astragalus', 'hawthorn', 'arnica', 'capsaicin', 'cayenne',
            'psyllium', 'oatmeal', 'cucumber', 'rose water',
        
            # Supplements & minerals
            'magnesium', 'zinc', 'vitamin c', 'vitamin d', 'iron', 'calcium',
            'omega 3', 'fish oil', 'probiotics', 'melatonin', 'b complex',
            'vitamin b12', 'folate', 'potassium', 'selenium', 'coq10',
            'green tea', 'epsom salt', 'oil pulling', 'salt water',
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
            base_scores = {1: 9.0, 2: 7.5, 3: 5.5, 4: 3.5, 5: 1.5}
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
    
    def _identify_condition(self, query:  str) -> str:
        """Identify condition from query text (fallback when not passed explicitly)"""
        query_lower = query.lower()
    
        condition_map = {
            'headache':  ['headache', 'head pain', 'migraine', 'head hurts'],
            'fever': ['fever', 'temperature', 'feverish'],
            'cold': ['cold', 'runny nose', 'congestion', 'stuffy'],
            'cough': ['cough', 'coughing'],
            'nausea': ['nausea', 'nauseous', 'vomit', 'queasy'],
            'sore throat': ['sore throat', 'throat pain', 'throat hurts'],
            'indigestion': ['indigestion', 'bloating', 'gas', 'acidity', 'heartburn'],
            'anxiety': ['anxiety', 'anxious', 'nervous', 'panic'],
            'stress': ['stress', 'stressed', 'tension'],
            'insomnia': ['insomnia', 'sleep', 'sleepless'],
            'fatigue': ['fatigue', 'tired', 'exhausted', 'energy'],
            'joint pain': ['joint pain', 'arthritis', 'joints'],
            'back pain': ['back pain', 'backache'],
            'constipation': ['constipation', 'constipated'],
            'diarrhea':  ['diarrhea', 'loose stool'],
            'motion sickness': ['motion sickness', 'car sick', 'carsick', 'travel sickness', 'sea sick', 'seasick'],
        
            # NEW CONDITIONS
            'menstrual cramps':  ['menstrual', 'period pain', 'period cramps', 'cramps', 'dysmenorrhea'],
            'muscle pain': ['muscle pain', 'muscle ache', 'sore muscles'],
            'inflammation': ['inflammation', 'swelling', 'inflamed'],
            'skin issues': ['rash', 'eczema', 'skin', 'acne', 'pimples'],
            'burns':  ['burn', 'burnt', 'scalded'],
            'sinus': ['sinus', 'sinusitis'],
            'ear pain': ['ear pain', 'earache'],
            'eye strain': ['eye strain', 'tired eyes'],
            'diabetes': ['diabetes', 'blood sugar'],
            'high blood pressure': ['blood pressure', 'hypertension'],
            'immunity': ['immunity', 'immune'],
            'hair loss': ['hair loss', 'hair fall'],
            'weight loss': ['weight loss', 'lose weight'],
            'depression': ['depression', 'depressed'],
            'uti': ['uti', 'urinary', 'bladder'],

            # In engine.py, find _identify_condition method and add: 

            'wound': ['wound', 'cut', 'bleeding', 'injury', 'punched', 'hit', 'bruise'],
            'bruise': ['bruise', 'bruised', 'swelling', 'black eye'],
            'burns': ['burn', 'burnt', 'scalded'],

        }
    
        for condition, keywords in condition_map.items():
            for keyword in keywords: 
                if keyword in query_lower: 
                    return condition
    
        return 'general health'

    
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
