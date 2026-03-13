"""
ServVia 2.0 - Knowledge Graph Service
"""
import logging
from typing import List, Dict
from . models import Neo4jConnection, Herb, Disease, HerbDiseaseEvidence, EvidenceTier

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    def __init__(self):
        self. neo4j = Neo4jConnection()
    
    def get_remedies_for_condition(self, condition: str, min_evidence_tier: int = 4, exclude_ingredients: List[str] = None) -> List[Dict]:
        exclude_ingredients = [i.lower() for i in (exclude_ingredients or [])]
        
        if self.neo4j. driver:
            query = """
            MATCH (h:Herb)-[r:TREATS]->(d:Disease)
            WHERE toLower(d.name) CONTAINS toLower($condition) AND r.evidence_tier <= $min_tier
            RETURN h. name as herb_name, h.scientific_name as scientific_name, h.description as description,
                   h.contraindications as contraindications, r.evidence_tier as evidence_tier,
                   r.pubmed_ids as pubmed_ids, r.mechanism as mechanism
            ORDER BY r.evidence_tier ASC LIMIT 10
            """
            results = self.neo4j.execute_query(query, {'condition': condition, 'min_tier': min_evidence_tier})
        else:
            results = []
            evidences = HerbDiseaseEvidence.objects.filter(
                disease__name__icontains=condition, evidence_tier__lte=min_evidence_tier
            ). select_related('herb', 'disease'). order_by('evidence_tier')[:10]
            
            for ev in evidences:
                results.append({
                    'herb_name': ev.herb. name,
                    'scientific_name': ev.herb.scientific_name,
                    'description': ev.herb.description,
                    'contraindications': ev.herb. contraindications,
                    'evidence_tier': ev.evidence_tier,
                    'pubmed_ids': ev.pubmed_ids,
                    'mechanism': ev.mechanism_of_action,
                })
        
        filtered = []
        for r in results:
            herb_lower = r. get('herb_name', '').lower()
            is_safe = not any(allergen in herb_lower for allergen in exclude_ingredients)
            if is_safe:
                tier = r. get('evidence_tier', 4)
                pubmed_count = len(r.get('pubmed_ids', []))
                base_score = EvidenceTier. TIER_WEIGHTS.get(tier, 0.25)
                r['scientific_confidence_score'] = round((base_score + min(pubmed_count * 0.05, 0.2)) * 10, 1)
                r['evidence_tier_label'] = dict(EvidenceTier.TIER_CHOICES). get(tier, 'Unknown')
                filtered.append(r)
        
        return filtered
    
    def check_contraindications(self, herb_name: str, user_conditions: List[str] = None, user_medications: List[str] = None) -> Dict:
        try:
            herb = Herb.objects.get(name__iexact=herb_name)
        except Herb.DoesNotExist:
            return {'safe': True, 'warnings': [], 'herb_found': False}
        
        warnings = []
        is_safe = True
        
        if user_conditions:
            for condition in user_conditions:
                for contraind in herb.contraindications:
                    if condition. lower() in contraind.lower():
                        warnings.append(f"⚠️ {herb_name} may not be suitable for {condition}")
                        is_safe = False
        
        if user_medications:
            for med in user_medications:
                for interaction in herb.drug_interactions:
                    if med.lower() in interaction.lower():
                        warnings. append(f"💊 {herb_name} may interact with {med}")
                        is_safe = False
        
        return {
            'safe': is_safe,
            'warnings': warnings,
            'herb_found': True,
            'contraindications': herb.contraindications,
            'drug_interactions': herb. drug_interactions,
        }
