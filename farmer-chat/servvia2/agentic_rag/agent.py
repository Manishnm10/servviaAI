"""
ServVia - Agentic RAG Agent
"""
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class ServViaAgent:
    
    def __init__(self):
        from servvia2.knowledge_graph.models import EvidenceRepository, HerbRepository
        from servvia2.trust_engine.confidence_calculator import ScientificConfidenceCalculator
        from servvia2.context_engine.environmental_service import EnvironmentalService
        from servvia2.response_formatter import ResponseFormatter
        
        self.evidence_repo = EvidenceRepository
        self.herb_repo = HerbRepository
        self.confidence_calc = ScientificConfidenceCalculator()
        self.env_service = EnvironmentalService()
        self.formatter = ResponseFormatter()
    
    def enhance_response(self, query: str, user_profile: Dict = None, 
                         location: Dict = None, base_response: str = "") -> Dict:
        user_profile = user_profile or {}
        user_name = user_profile. get('first_name', 'there')
        allergies = user_profile.get('allergies', [])
        conditions = user_profile. get('medical_conditions', [])
        
        # Extract condition from query
        condition = self._extract_condition(query)
        logger.info(f"Extracted condition: '{condition}' from query: '{query}'")
        
        # Get remedies from knowledge graph
        remedies = self. evidence_repo.get_remedies_for_condition(
            condition=condition,
            exclude_ingredients=allergies
        )
        logger.info(f"Found {len(remedies)} remedies for '{condition}'")
        
        # Calculate confidence scores
        enhanced_remedies = []
        for remedy in remedies[:5]:
            scs = self.confidence_calc.calculate_scs(
                evidence_tier=remedy.get('evidence_tier', 4),
                pubmed_ids=remedy.get('pubmed_ids', []),
                has_mechanism=bool(remedy.get('mechanism')),
                contraindications=remedy. get('contraindications', []),
                user_conditions=conditions
            )
            remedy['confidence_score'] = scs
            
            # Only include safe remedies
            if not any(w for w in scs. get('safety_warnings', [])):
                enhanced_remedies.append(remedy)
        
        logger.info(f"Enhanced remedies after safety check: {len(enhanced_remedies)}")
        
        # Get environmental context
        env_context = {}
        if location:
            lat = location.get('latitude', 0)
            env_context = self.env_service. get_season(lat)
            env_context['recommendations'] = self.env_service.get_recommendations(
                season=env_context. get('season')
            )
        
        # Format response
        if enhanced_remedies:
            formatted_response = self. formatter.format_full_response(
                user_name=user_name,
                condition=condition,
                remedies=enhanced_remedies,
                env_context=env_context,
                allergies=allergies if allergies else None,
                base_response=base_response
            )
        else:
            formatted_response = base_response
        
        return {
            'response': formatted_response,
            'validated_remedies': enhanced_remedies,
            'environmental_context': env_context,
            'condition_detected': condition,
            'allergies_excluded': allergies,
        }
    
    def _extract_condition(self, query: str) -> str:
        """Extract health condition from query"""
        conditions_map = {
            'headache': ['headache', 'head hurts', 'head pain', 'head ache', 'migraine'],
            'cold': ['cold', 'runny nose', 'sneezing', 'congestion'],
            'cough': ['cough', 'coughing'],
            'fever': ['fever', 'temperature', 'feverish'],
            'nausea': ['nausea', 'nauseous', 'vomit', 'sick to stomach'],
            'anxiety': ['anxiety', 'anxious', 'worried', 'nervous', 'panic'],
            'insomnia': ['insomnia', 'cant sleep', 'cannot sleep', 'sleepless', 'trouble sleeping'],
            'indigestion': ['indigestion', 'bloating', 'gas', 'stomach ache', 'digestion'],
            'sore throat': ['sore throat', 'throat pain', 'throat hurts'],
            'stress': ['stress', 'stressed', 'overwhelmed', 'tense'],
            'toothache': ['toothache', 'tooth pain', 'tooth hurts'],
            'fatigue': ['fatigue', 'tired', 'exhausted', 'no energy'],
            'arthritis': ['arthritis', 'joint pain', 'joints hurt'],
            'acne': ['acne', 'pimples', 'breakout'],
            'burns': ['burn', 'burned', 'burnt'],
        }
        
        query_lower = query. lower()
        
        for condition, keywords in conditions_map. items():
            for keyword in keywords:
                if keyword in query_lower:
                    return condition
        
        return query[:50]
    
    def get_remedy_details(self, herb_name: str, user_conditions: List[str] = None) -> Dict:
        herb = self.herb_repo.get_by_name(herb_name)
        if not herb:
            return {'found': False, 'message': f'Herb {herb_name} not found'}
        
        warnings = []
        if user_conditions:
            for condition in user_conditions:
                for contraind in herb.get('contraindications', []):
                    if condition. lower() in contraind.lower():
                        warnings.append(f"Caution with {condition}: {contraind}")
        
        return {
            'found': True,
            'herb': herb,
            'safe': len(warnings) == 0,
            'warnings': warnings,
        }
