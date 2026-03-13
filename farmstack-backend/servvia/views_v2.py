"""
ServVia 2.0 - Enhanced API Views with Agentic RAG
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework. permissions import IsAuthenticated, AllowAny
from rest_framework. response import Response
import logging

logger = logging. getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def agentic_chat(request):
    """
    ServVia 2. 0 Agentic RAG Endpoint
    
    POST /api/servvia/v2/chat/
    {
        "query": "I have a headache, what home remedies can help? ",
        "user_profile": {
            "first_name": "John",
            "allergies": ["honey"],
            "medical_conditions": ["diabetes"],
            "current_medications": ["metformin"]
        },
        "location": {"latitude": 28.6139, "longitude": 77.2090}
    }
    """
    try:
        from servvia.agentic_rag. agent import ServViaAgent
        
        query = request.data. get('query', '')
        user_profile = request.data.get('user_profile', {})
        location = request. data.get('location', None)
        context_chunks = request.data.get('context', '')
        
        if not query:
            return Response({'error': 'Query is required'}, status=400)
        
        agent = ServViaAgent()
        result = agent.process_query(
            query=query,
            user_profile=user_profile,
            location=location,
            context_chunks=context_chunks
        )
        
        return Response({
            'success': True,
            'response': result. get('response'),
            'remedies': result.get('remedies', []),
            'reasoning_steps': result. get('reasoning_steps', []),
            'environmental_context': result.get('environmental_context', {}),
        })
        
    except Exception as e:
        logger.error(f"Agentic chat error: {e}", exc_info=True)
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_remedies(request):
    """
    Get remedies for a condition with confidence scores
    
    GET /api/servvia/v2/remedies/? condition=headache&allergies=honey,peanuts
    """
    try:
        from servvia.knowledge_graph.service import KnowledgeGraphService
        
        condition = request.query_params.get('condition', '')
        allergies = request.query_params.get('allergies', '').split(',') if request.query_params.get('allergies') else []
        
        if not condition:
            return Response({'error': 'Condition is required'}, status=400)
        
        kg_service = KnowledgeGraphService()
        remedies = kg_service.get_remedies_for_condition(
            condition=condition,
            exclude_ingredients=[a.strip() for a in allergies if a.strip()]
        )
        
        return Response({
            'success': True,
            'condition': condition,
            'remedies_count': len(remedies),
            'remedies': remedies,
        })
        
    except Exception as e:
        logger.error(f"Get remedies error: {e}", exc_info=True)
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def check_safety(request):
    """
    Check herb safety for user profile
    
    POST /api/servvia/v2/safety/
    {
        "herb": "Ginger",
        "conditions": ["diabetes"],
        "medications": ["metformin"]
    }
    """
    try:
        from servvia.knowledge_graph.service import KnowledgeGraphService
        
        herb = request.data.get('herb', '')
        conditions = request.data.get('conditions', [])
        medications = request.data.get('medications', [])
        
        if not herb:
            return Response({'error': 'Herb name is required'}, status=400)
        
        kg_service = KnowledgeGraphService()
        safety = kg_service.check_contraindications(
            herb_name=herb,
            user_conditions=conditions,
            user_medications=medications
        )
        
        return Response({
            'success': True,
            'herb': herb,
            'safety': safety,
        })
        
    except Exception as e:
        logger.error(f"Safety check error: {e}", exc_info=True)
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_environmental_context(request):
    """
    Get environmental recommendations
    
    GET /api/servvia/v2/environment/? latitude=28.6139&longitude=77. 2090
    """
    try:
        from servvia. context_engine.environmental_service import EnvironmentalService
        import asyncio
        
        lat = float(request.query_params.get('latitude', 0))
        lng = float(request.query_params.get('longitude', 0))
        
        env_service = EnvironmentalService()
        season_info = env_service. get_season(lat)
        recommendations = env_service. get_environmental_recommendations(season=season_info. get('season'))
        
        return Response({
            'success': True,
            'season': season_info,
            'recommendations': recommendations,
        })
        
    except Exception as e:
        logger.error(f"Environment error: {e}", exc_info=True)
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def knowledge_graph_stats(request):
    """Get knowledge graph statistics"""
    try:
        from servvia.knowledge_graph.models import Herb, Disease, HerbDiseaseEvidence
        
        return Response({
            'success': True,
            'stats': {
                'herbs': Herb. objects.count(),
                'diseases': Disease.objects.count(),
                'evidence_links': HerbDiseaseEvidence. objects.count(),
                'tier_1_evidence': HerbDiseaseEvidence.objects.filter(evidence_tier=1). count(),
                'tier_2_evidence': HerbDiseaseEvidence.objects.filter(evidence_tier=2).count(),
            }
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)
