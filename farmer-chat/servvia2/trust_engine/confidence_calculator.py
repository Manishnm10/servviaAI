"""
ServVia 2.0 - Scientific Confidence Score Calculator
"""
from typing import Dict, List
from servvia2.knowledge_graph.models import EvidenceTier


class ScientificConfidenceCalculator:
    
    def calculate_scs(self, evidence_tier: int, pubmed_ids: List[str] = None,
                      has_mechanism: bool = False, contraindications: List[str] = None,
                      user_conditions: List[str] = None) -> Dict:
        
        pubmed_ids = pubmed_ids or []
        contraindications = contraindications or []
        user_conditions = user_conditions or []
        
        evidence_score = EvidenceTier. TIER_WEIGHTS.get(evidence_tier, 0.25) * 0.4
        
        pubmed_count = len(pubmed_ids)
        if pubmed_count >= 5:
            pubmed_score = 1.0 * 0.3
        elif pubmed_count >= 3:
            pubmed_score = 0.75 * 0.3
        elif pubmed_count >= 1:
            pubmed_score = 0.5 * 0.3
        else:
            pubmed_score = 0.1 * 0.3
        
        mechanism_score = 0.2 if has_mechanism else 0.05
        
        safety_penalty = 0
        safety_warnings = []
        for condition in user_conditions:
            for contraind in contraindications:
                if condition. lower() in contraind.lower():
                    safety_penalty += 0.03
                    safety_warnings.append(f"Caution: {contraind}")
        
        safety_score = max(0, 0.1 - safety_penalty)
        
        total_score = round((evidence_score + pubmed_score + mechanism_score + safety_score) * 10, 1)
        total_score = min(10, max(0, total_score))
        
        if total_score >= 8:
            level, emoji = "High", "🟢"
        elif total_score >= 5:
            level, emoji = "Moderate", "🟡"
        else:
            level, emoji = "Low", "🔴"
        
        return {
            'score': total_score,
            'confidence_level': level,
            'confidence_emoji': emoji,
            'evidence_tier': evidence_tier,
            'evidence_tier_label': EvidenceTier.TIER_CHOICES. get(evidence_tier, 'Unknown'),
            'pubmed_count': pubmed_count,
            'safety_warnings': safety_warnings,
        }
    
    def format_display(self, scs: Dict) -> str:
        return f"{scs['confidence_emoji']} SCS: {scs['score']}/10 ({scs['confidence_level']}) | {scs['evidence_tier_label']} | PubMed: {scs['pubmed_count']}"
