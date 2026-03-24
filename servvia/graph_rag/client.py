"""
ServVia Graph RAG — Knowledge Graph Client.

Connects to Neo4j AuraDB (cloud) and retrieves remedies ranked by
outcome-adaptive edge weights tied to the user's biological state.
"""

import logging
import os
from typing import Dict, List, Optional

from neo4j import GraphDatabase

from graph_rag.schema import (
    BIOLOGICAL_STATE,
    ENHANCED_BY,
    REMEDY,
    SYMPTOM,
    TREATS,
)

logger = logging.getLogger(__name__)


def _neo4j_env(key: str) -> str:
    """Read Neo4j credential from os.environ first, then django_core ENV_CONFIG."""
    val = os.environ.get(key)
    if val:
        return val
    try:
        from django_core.config import ENV_CONFIG
        val = ENV_CONFIG.get(key)
    except Exception:
        pass
    if not val:
        raise KeyError(f"{key} not set in environment or .env file")
    return val


class KnowledgeGraphClient:
    """Neo4j AuraDB client for outcome-adaptive remedy retrieval."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self._uri = uri or _neo4j_env("NEO4J_URI")
        self._user = user or _neo4j_env("NEO4J_USERNAME")
        self._password = password or _neo4j_env("NEO4J_PASSWORD")
        self._driver = GraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )
        logger.info("KnowledgeGraphClient connected to %s", self._uri)

    # ── public API ───────────────────────────────────────────

    def retrieve_ranked_remedies(
        self, symptoms: List[str], bio_state: str
    ) -> List[Dict]:
        """Return remedies ranked by base_score * ENHANCED_BY weight.

        Cypher logic:
        1. MATCH remedies that TREATS any of the supplied symptoms.
        2. OPTIONAL MATCH an ENHANCED_BY edge to the user's BiologicalState.
        3. Rank = remedy.base_score * coalesce(edge.weight, 1.0).
        4. Return descending by rank.
        """
        query = (
            f"MATCH (s:{SYMPTOM})<-[:{TREATS}]-(r:{REMEDY}) "
            f"WHERE s.name IN $symptoms "
            f"WITH DISTINCT r "
            f"OPTIONAL MATCH (r)-[e:{ENHANCED_BY}]->(b:{BIOLOGICAL_STATE}) "
            f"WHERE b.name = $bio_state "
            "RETURN r.name AS remedy, "
            "       r.base_score AS base_score, "
            "       coalesce(e.weight, 1.0) AS enhancement, "
            "       r.base_score * coalesce(e.weight, 1.0) AS rank "
            "ORDER BY rank DESC"
        )

        with self._driver.session() as session:
            result = session.run(
                query, symptoms=symptoms, bio_state=bio_state
            )
            records = [
                {
                    "remedy": rec["remedy"],
                    "base_score": rec["base_score"],
                    "enhancement": rec["enhancement"],
                    "rank": rec["rank"],
                }
                for rec in result
            ]

        logger.info(
            "Retrieved %d remedies for symptoms=%s, bio_state=%s",
            len(records),
            symptoms,
            bio_state,
        )
        return records

    # ── lifecycle ────────────────────────────────────────────

    def close(self) -> None:
        self._driver.close()
        logger.info("KnowledgeGraphClient connection closed.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ── Singleton instance (reuses TCP/TLS connection across requests) ────────

_singleton_client: "KnowledgeGraphClient | None" = None


def get_graph_client() -> "KnowledgeGraphClient":
    """Return a module-level singleton client, creating it on first call."""
    global _singleton_client
    if _singleton_client is None:
        _singleton_client = KnowledgeGraphClient()
    return _singleton_client
