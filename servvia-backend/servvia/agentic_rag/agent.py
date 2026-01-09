"""
ServVia 2.0 - Agentic RAG Pipeline
"""
import logging
import json
from typing import Dict, List, Any
from dataclasses import dataclass
import openai
import os

logger = logging.getLogger(__name__)


@dataclass
class AgentStep:
    step_number: int
    action: str
    thought: str
    result: Any


class ServViaAgent:
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        self.model = "gpt-4"
        self.steps: List[AgentStep] = []
    
    def process_query(self, query: str, user_profile: Dict = None, 
                      location: Dict = None, context_chunks: str = "") -> Dict:
        from servvia.knowledge_graph.service import KnowledgeGraphService
        from servvia.trust_engine.confidence_calculator import ScientificConfidenceCalculator
        from servvia.context_engine.environmental_service import EnvironmentalService
        
        self.steps = []
        user_profile = user_profile or {}
        kg_service = KnowledgeGraphService()
        confidence_calc = ScientificConfidenceCalculator()
        env_service = EnvironmentalService()
        
        # Step 1: Analyze Query
        self._add_step(1, "analyze_query", "Understanding health concern")
        analysis = self._analyze_query(query)
        self. steps[-1].result = analysis
        
        # Step 2: Knowledge Graph Search
        self._add_step(2, "knowledge_graph", "Searching remedy database")
        kg_results = kg_service. get_remedies_for_condition(
            analysis. get('condition', query),
            exclude_ingredients=user_profile.get('allergies', [])
        )
        self.steps[-1]. result = f"Found {len(kg_results)} remedies"
        
        # Step 3: Add Confidence Scores
        self._add_step(3, "validate_evidence", "Calculating confidence scores")
        for remedy in kg_results:
            scs = confidence_calc.calculate_scs(
                evidence_tier=remedy. get('evidence_tier', 4),
                pubmed_ids=remedy. get('pubmed_ids', []),
                has_mechanism=bool(remedy.get('mechanism')),
                contraindications=remedy.get('contraindications', []),
                user_conditions=user_profile.get('medical_conditions', [])
            )
            remedy['confidence_score'] = scs
        validated = sorted(kg_results, key=lambda x: x. get('confidence_score', {}).get('score', 0), reverse=True)
        self.steps[-1]. result = f"Validated {len(validated)} remedies"
        
        # Step 4: Safety Check
        self._add_step(4, "safety_check", "Checking user safety profile")
        safe_remedies = []
        for remedy in validated:
            safety = kg_service.check_contraindications(
                remedy.get('herb_name', ''),
                user_conditions=user_profile. get('medical_conditions', []),
                user_medications=user_profile. get('current_medications', [])
            )
            if safety. get('safe', True):
                safe_remedies.append(remedy)
        self.steps[-1]. result = f"{len(safe_remedies)} safe remedies"
        
        # Step 5: Environmental Context
        env_context = {}
        if location:
            self._add_step(5, "environmental", "Checking environment")
            env_context = env_service.get_season(location.get('latitude', 0))
            self.steps[-1].result = f"Season: {env_context.get('season')}"
        
        # Step 6: Generate Response
        self._add_step(len(self.steps) + 1, "generate", "Creating response")
        response = self._generate_response(query, safe_remedies, user_profile, env_context, context_chunks)
        
        return {
            'response': response,
            'remedies': safe_remedies[:5],
            'reasoning_steps': [{'step': s.step_number, 'action': s.action, 'thought': s.thought, 'result': s.result} for s in self.steps],
            'environmental_context': env_context,
        }
    
    def _add_step(self, number: int, action: str, thought: str):
        self. steps.append(AgentStep(number, action, thought, None))
    
    def _analyze_query(self, query: str) -> Dict:
        try:
            response = self.client.chat. completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": 'Extract health condition.  Return JSON: {"condition": ".. .", "intent": "treatment|prevention|information"}'},
                    {"role": "user", "content": query}
                ],
                temperature=0, max_tokens=100
            )
            return json.loads(response.choices[0].message.content)
        except:
            return {"condition": query, "intent": "treatment"}
    
    def _generate_response(self, query: str, remedies: List[Dict], user_profile: Dict, env_context: Dict, context_chunks: str) -> str:
        remedy_text = ""
        for i, r in enumerate(remedies[:5], 1):
            scs = r.get('confidence_score', {})
            remedy_text += f"\n{i}.  **{r. get('herb_name')}** - {scs. get('confidence_emoji', '🟡')} SCS: {scs.get('score', 'N/A')}/10 | {r.get('mechanism', 'Traditional use')}"
        
        user_name = user_profile. get('first_name', 'there')
        allergies = user_profile.get('allergies', [])
        
        prompt = f"""You are ServVia 2. 0, an evidence-based health assistant. 

USER: {user_name}
QUERY: {query}
ALLERGIES: {', '. join(allergies) if allergies else 'None'}

VALIDATED REMEDIES (with Scientific Confidence Scores):
{remedy_text if remedy_text else 'No specific remedies found. '}

CONTEXT: {context_chunks[:800] if context_chunks else 'None'}
SEASON: {env_context.get('season', 'N/A'). title()}

Create a warm, personalized response that:
1.  Addresses {user_name} by name
2. Shows SCS scores for each remedy
3.  Explains why each works
4. Notes safety considerations
5. When to see a doctor
6. Uses emojis"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7, max_tokens=800
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Response error: {e}")
            return f"I encountered an error.  Please try again."
