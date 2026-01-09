"""
Content retrieval from Farmstack vector database
"""
import logging
import requests
import urllib3
from django_core.config import Config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def _get_user_allergies(email_id):
    """Get user allergies from database"""
    try:
        from user_profile.models import UserProfile
        profile = UserProfile.objects.get(email=email_id)
        allergies = profile.get_allergies_list()
        return allergies if allergies else []
    except Exception as e:
        logger.debug(f"Could not fetch allergies for {email_id}: {e}")
        return []


def _filter_chunks_for_allergens(chunks, allergies):
    """
    Filter out chunks that contain allergen mentions.
    
    Args:
        chunks: List of content chunks
        allergies: List of allergen names (e.g., ['honey', 'peanuts'])
    
    Returns:
        Filtered list of chunks without allergen mentions
    """
    if not allergies:
        return chunks
    
    filtered_chunks = []
    filtered_count = 0
    
    for chunk in chunks:
        # Extract text from chunk
        text = chunk.get('text', '') or chunk.get('content', '') or str(chunk)
        text_lower = text.lower()
        
        # Check if any allergen is mentioned (case-insensitive)
        contains_allergen = False
        for allergen in allergies:
            allergen_lower = allergen.lower().strip()
            if allergen_lower in text_lower:
                contains_allergen = True
                logger.info(f"🛡️ Layer 1: Filtered chunk containing allergen '{allergen}'")
                filtered_count += 1
                break
        
        if not contains_allergen:
            filtered_chunks.append(chunk)
    
    if filtered_count > 0:
        logger.info(f"🛡️ Layer 1: Filtered {filtered_count} chunks containing allergens from {len(chunks)} total chunks")
    
    return filtered_chunks


def _apply_allergy_filter_and_build_result(chunks, email_id, reference=None, youtube_url=None):
    """
    Helper function to apply allergy filtering and build result dictionary.
    
    Args:
        chunks: List of content chunks
        email_id: User's email for fetching allergies
        reference: Optional reference data
        youtube_url: Optional YouTube URL data
    
    Returns:
        Dictionary with filtered chunks and metadata
    """
    # Layer 1: Filter chunks for allergens
    allergies = _get_user_allergies(email_id)
    if allergies:
        logger.info(f"🛡️ Layer 1: User allergies: {allergies}")
        chunks = _filter_chunks_for_allergens(chunks, allergies)
        logger.info(f"🛡️ Layer 1: {len(chunks)} chunks remaining after allergy filtering")
    
    return {
        'chunks': chunks,
        'reference': reference or [],
        'youtube_url': youtube_url or []
    }


def retrieve_content(query, email_id, top_k=10):
    """Retrieve relevant content chunks from Farmstack vector database"""
    try:
        base_url = Config.CONTENT_DOMAIN_URL.rstrip('/')
        endpoint = Config.CONTENT_RETRIEVAL_ENDPOINT.lstrip('/')
        retrieval_url = f"{base_url}/{endpoint}"
        
        # Use correct parameter names from original code
        payload = {
            "email": email_id,
            "query": query,
        }
        
        logger.info(f"Farmstack URL: {retrieval_url}")
        logger.info(f"Payload: {payload}")
        
        response = requests.post(
            retrieval_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
            verify=False
        )
        
        logger.info(f"Farmstack status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Farmstack response type: {type(data)}")
            
            if isinstance(data, dict):
                chunks = data.get('chunks') or data.get('results') or data.get('data') or []
                if chunks:
                    logger.info(f"✅ Retrieved {len(chunks)} chunks from Farmstack")
                    return _apply_allergy_filter_and_build_result(
                        chunks, 
                        email_id, 
                        data.get('reference', []),
                        data.get('youtube_url', [])
                    )
            elif isinstance(data, list) and data:
                logger.info(f"✅ Retrieved {len(data)} chunks")
                chunks = [{'text': item} if isinstance(item, str) else item for item in data]
                return _apply_allergy_filter_and_build_result(chunks, email_id)
            
            logger.warning(f"⚠️ No chunks found. Response: {str(data)[:300]}")
        else:
            logger.error(f"❌ Farmstack error {response.status_code}: {response.text[:300]}")
    
    except Exception as e:
        logger.error(f"❌ Retrieval failed: {e}", exc_info=True)
    
    return {'chunks': [], 'reference': [], 'youtube_url': []}