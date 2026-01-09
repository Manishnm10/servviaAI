"""
ServVia 2.0 - Scientific Confidence Score (SCS) Calculator
"""
import logging
from typing import Dict, List
from servvia.knowledge_graph.models import EvidenceTier

logger = logging.getLogger(__name__)


class ScientificConfidenceCalculator:
    """
    SCS = (Evidence_Weight * 0.4) + (PubMed_Score * 0.3) + (Mechanism_Score * 0.2) + (Safety_Score * 0.1)
    Scale: 0-10
    """
    
    def calculate_scs(self, evidence_tier: int, pubmed_ids: List[str] = None,
                      has_mechanism: bool = False, contraindications: List[str] = None,
                      user_conditions: List[str] = None) -> Dict:
        
        pubmed_ids = pubmed_ids or []
        contraindications = contraindications or []
        user_conditions = user_conditions or []
        
        # Evidence Weight (40%)
        evidence_weight = EvidenceTier. TIER_WEIGHTS.get(evidence_tier, 0. 25)
        evidence_score = evidence_weight * 0.4
        
        # PubMed Score (30%)
        pubmed_count = len(pubmed_ids)
        if pubmed_count >= 5:
            pubmed_score = 1.0 * 0.3
        elif pubmed_count >= 3:
            pubmed_score = 0.75 * 0. 3
        elif pubmed_count >= 1:
            pubmed_score = 0.5 * 0.3
        else:
            pubmed_score = 0.1 * 0. 3
        
        # Mechanism Score (20%)
        mechanism_score = 0.2 if has_mechanism else 0.05
        
        # Safety Score (10%)
        safety_penalty = 0
        safety_warnings = []
        for condition in user_conditions:
            for contraind in contraindications:
                if condition.lower() in contraind.lower():
                    safety_penalty += 0.03
                    safety_warnings.append(f"Caution: {contraind}")
        
        safety_score = max(0, 0.1 - safety_penalty)
        
        # Total
        total_score = (evidence_score + pubmed_score + mechanism_score + safety_score) * 10
        total_score = round(min(10, max(0, total_score)), 1)
        
        if total_score >= 8:
            confidence_level, confidence_emoji = "High", "🟢"
        elif total_score >= 5:
            confidence_level, confidence_emoji = "Moderate", "🟡"
        else:
            confidence_level, confidence_emoji = "Low", "🔴"
        
        return {
            'score': total_score,
            'confidence_level': confidence_level,
            'confidence_emoji': confidence_emoji,
            'breakdown': {
                'evidence_tier': evidence_tier,
                'evidence_tier_label': dict(EvidenceTier.TIER_CHOICES). get(evidence_tier, 'Unknown'),
                'pubmed_count': pubmed_count,
            },
            'safety_warnings': safety_warnings,
            'pubmed_ids': pubmed_ids,
        }
    
    def format_score_display(self, scs_result: Dict) -> str:
        score = scs_result['score']
        level = scs_result['confidence_level']
        emoji = scs_result['confidence_emoji']
        tier_label = scs_result['breakdown']['evidence_tier_label']
        pubmed_count = scs_result['breakdown']['pubmed_count']
        
        return f"{emoji} **SCS: {score}/10** ({level}) | Evidence: {tier_label} | PubMed: {pubmed_count}"
