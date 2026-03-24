"""
ServVia Graph RAG — Adaptive Feedback Engine.

Updates ENHANCED_BY edge weights in Neo4j based on user outcome
feedback, enabling the knowledge graph to learn which remedies
work best for specific biological states over time.
"""

import logging
import os
from typing import Optional

from neo4j import GraphDatabase

from graph_rag.schema import (
    BIOLOGICAL_STATE,
    EDGE_WEIGHT_MAX,
    EDGE_WEIGHT_MIN,
    ENHANCED_BY,
    REMEDY,
)
from graph_rag.client import _neo4j_env

logger = logging.getLogger(__name__)


class AdaptiveFeedbackEngine:
    """Adjusts ENHANCED_BY edge weights based on patient outcome feedback."""

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
        logger.info("AdaptiveFeedbackEngine connected to %s", self._uri)

    def update_edge_weight(
        self, remedy: str, bio_state: str, outcome_score: int
    ) -> Optional[float]:
        """Increment or decrement the ENHANCED_BY edge weight.

        Args:
            remedy:        Name of the remedy node.
            bio_state:     Name of the BiologicalState node.
            outcome_score: +1 (positive outcome) or -1 (negative outcome).

        Returns:
            The new clamped weight, or None if the edge was not found.
        """
        if outcome_score not in (1, -1):
            raise ValueError("outcome_score must be +1 or -1")

        # MERGE creates the edge if it doesn't exist, so any remedy can
        # accumulate personalised feedback for any bio-state over time.
        query = (
            f"MATCH (r:{REMEDY} {{name: $remedy}}) "
            f"MATCH (b:{BIOLOGICAL_STATE} {{name: $bio_state}}) "
            f"MERGE (r)-[e:{ENHANCED_BY}]->(b) "
            f"ON CREATE SET e.weight = CASE "
            f"  WHEN $default_weight + $delta > {EDGE_WEIGHT_MAX} THEN {EDGE_WEIGHT_MAX} "
            f"  WHEN $default_weight + $delta < {EDGE_WEIGHT_MIN} THEN {EDGE_WEIGHT_MIN} "
            f"  ELSE $default_weight + $delta END "
            f"ON MATCH  SET e.weight = CASE "
            f"  WHEN e.weight + $delta > {EDGE_WEIGHT_MAX} THEN {EDGE_WEIGHT_MAX} "
            f"  WHEN e.weight + $delta < {EDGE_WEIGHT_MIN} THEN {EDGE_WEIGHT_MIN} "
            f"  ELSE e.weight + $delta "
            f"END "
            "RETURN e.weight AS new_weight"
        )

        from graph_rag.schema import EDGE_WEIGHT_DEFAULT

        with self._driver.session() as session:
            result = session.run(
                query,
                remedy=remedy,
                bio_state=bio_state,
                delta=float(outcome_score),
                default_weight=EDGE_WEIGHT_DEFAULT,
            )
            record = result.single()

        if record is None:
            logger.warning(
                "Remedy=%s or BiologicalState=%s node not found in graph",
                remedy,
                bio_state,
            )
            return None

        new_weight = record["new_weight"]
        logger.info(
            "Updated edge weight: remedy=%s, bio_state=%s, delta=%+d, new_weight=%.1f",
            remedy,
            bio_state,
            outcome_score,
            new_weight,
        )
        return new_weight

    # ── lifecycle ────────────────────────────────────────────

    def close(self) -> None:
        self._driver.close()
        logger.info("AdaptiveFeedbackEngine connection closed.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
