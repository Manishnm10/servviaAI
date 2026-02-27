"""
VectorDB Adapter for Symptom Diagnosis Engine
===============================================
Connects to the remote Farmstack VectorDB server via REST API.

This reuses the same Farmstack endpoint your existing RAG pipeline uses
(CONTENT_DOMAIN_URL + CONTENT_RETRIEVAL_ENDPOINT), but wraps it for
the diagnosis engine's async interface.

The textbook you uploaded to Farmstack IS the knowledge base —
the diagnosis engine queries it to find disease information matching
the user's symptom combination.
"""
import logging
import requests
import urllib3
from typing import List

from django_core.config import Config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def _call_farmstack(query: str, email: str, top_k: int = 5) -> List[str]:
    """
    Internal helper — makes the actual HTTP POST to Farmstack.
    
    This is the same API call your existing content_retrieval.py makes:
        POST {CONTENT_DOMAIN_URL}/{CONTENT_RETRIEVAL_ENDPOINT}
        Body: {"email": ..., "query": ...}
    
    Returns plain text strings instead of chunk dicts.
    """
    try:
        base_url = Config.CONTENT_DOMAIN_URL
        if not base_url:
            logger.error("CONTENT_DOMAIN_URL not configured")
            return []

        base_url = base_url.rstrip('/')
        endpoint = (Config.CONTENT_RETRIEVAL_ENDPOINT or '').lstrip('/')
        retrieval_url = f"{base_url}/{endpoint}"

        payload = {
            "email": email,
            "query": query,
        }

        logger.info(f"🩺 Diagnosis VectorDB query: {query[:80]}...")

        response = requests.post(
            retrieval_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
            verify=False,
        )

        if response.status_code != 200:
            logger.error(
                f"❌ Farmstack error {response.status_code}: "
                f"{response.text[:300]}"
            )
            return []

        data = response.json()

        # Extract raw chunks — handle all response formats Farmstack returns
        chunks_raw = []
        if isinstance(data, dict):
            chunks_raw = (
                data.get('chunks')
                or data.get('results')
                or data.get('data')
                or []
            )
        elif isinstance(data, list):
            chunks_raw = data

        # Convert to plain text strings
        text_results = []
        for chunk in chunks_raw[:top_k]:
            if isinstance(chunk, str):
                text = chunk
            elif isinstance(chunk, dict):
                text = (
                    chunk.get('text', '')
                    or chunk.get('content', '')
                    or chunk.get('document', '')
                    or str(chunk)
                )
            else:
                text = str(chunk)

            if text.strip():
                text_results.append(text.strip())

        logger.info(f"   ✅ Retrieved {len(text_results)} chunks for diagnosis")
        return text_results

    except requests.exceptions.Timeout:
        logger.error("❌ Farmstack timed out for diagnosis query")
        return []
    except requests.exceptions.ConnectionError:
        logger.error("❌ Cannot connect to Farmstack for diagnosis")
        return []
    except Exception as e:
        logger.error(f"❌ Diagnosis retrieval failed: {e}", exc_info=True)
        return []


async def retrieve_from_farmstack(query: str, top_k: int = 5) -> List[str]:
    """
    Retrieve chunks from Farmstack using a system email.
    
    Use this when you don't have the user's email (e.g., background
    diagnosis queries that aren't tied to a specific user session).
    """
    return _call_farmstack(query, email="system@servvia.health", top_k=top_k)


async def retrieve_from_farmstack_with_email(
    query: str,
    email_id: str,
    top_k: int = 5,
) -> List[str]:
    """
    Retrieve chunks from Farmstack using the actual user's email.
    
    Use this when you have the user's email so Farmstack can apply
    any user-specific filtering on its end.
    """
    return _call_farmstack(query, email=email_id, top_k=top_k)