"""
Query rephrasing for better retrieval
"""
import logging
from rag_service.openai_service import make_openai_request

logger = logging.getLogger(__name__)


async def rephrase_query(original_query, chat_history=None):
    """
    Rephrase user query for better vector database retrieval
    """
    try:
        prompt = f"""Rephrase this health query for searching home remedies database:

Query: {original_query}

Rephrased (concise):"""

        response, error, retries = await make_openai_request(prompt)
        
        if response and response.choices:
            rephrased = response.choices[0].message.content.strip()
            logger.info(f"Query rephrased: '{original_query}' -> '{rephrased}'")
            return rephrased
        else:
            return original_query
    
    except Exception as e:
        logger.error(f"Query rephrase error: {e}", exc_info=True)
        return original_query
