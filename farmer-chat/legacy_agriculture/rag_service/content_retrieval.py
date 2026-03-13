"""
Content retrieval from Farmstack vector database
"""
import logging
import requests
import urllib3
from django_core.config import Config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def retrieve_content(query, email_id, top_k=10):
    """Retrieve relevant content chunks from Farmstack vector database"""
    try:
        base_url = Config.CONTENT_DOMAIN_URL.rstrip('/')
        endpoint = Config.CONTENT_RETRIEVAL_ENDPOINT.lstrip('/')
        retrieval_url = f"{base_url}/{endpoint}"

        # Use the configured Farmstack retrieval email so any farmer-chat
        # user can access the shared knowledge base without being registered
        # on Farmstack. The user's real email is still used for profile,
        # chat history, allergies, and all other farmer-chat features.
        retrieval_email = Config.FARMSTACK_RETRIEVAL_EMAIL or email_id

        payload = {
            "email": retrieval_email,
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
                    return {
                        'chunks': chunks,
                        'reference': data.get('reference', []),
                        'youtube_url': data.get('youtube_url', [])
                    }
            elif isinstance(data, list) and data:
                logger.info(f"✅ Retrieved {len(data)} chunks")
                return {
                    'chunks': [{'text': item} if isinstance(item, str) else item for item in data],
                    'reference': [],
                    'youtube_url': []
                }
            
            logger.warning(f"⚠️ No chunks found. Response: {str(data)[:300]}")
        else:
            logger.error(f"❌ Farmstack error {response.status_code}: {response.text[:300]}")
    
    except Exception as e:
        logger.error(f"❌ Retrieval failed: {e}", exc_info=True)
    
    return {'chunks': [], 'reference': [], 'youtube_url': []}
