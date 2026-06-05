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


class KnowledgeGraphClient:
    """Neo4j AuraDB client for outcome-adaptive remedy retrieval."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self._uri = uri or os.environ["NEO4J_URI"]
        self._user = user or os.environ["NEO4J_USER"]
        self._password = password or os.environ["NEO4J_PASSWORD"]
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
