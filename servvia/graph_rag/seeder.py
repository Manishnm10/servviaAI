"""
ServVia Graph RAG — Neo4j Seeder.

Idempotently seeds the AuraDB knowledge graph with healthcare remedy,
symptom, and biological-state nodes plus their relationships.

Run once via Django management command:
    python manage.py seed_graph_rag

Safe to re-run: uses MERGE so existing data is not duplicated.
"""

import logging
from typing import Optional

from graph_rag.client import KnowledgeGraphClient, _neo4j_env
from graph_rag.seed_data import (
    BIO_STATES,
    ENHANCED_BY_EDGES,
    REMEDIES,
    SYMPTOMS,
    TREATS_EDGES,
)
from graph_rag.schema import BIOLOGICAL_STATE, ENHANCED_BY, REMEDY, SYMPTOM, TREATS

logger = logging.getLogger(__name__)


def seed_graph(uri: Optional[str] = None,
               user: Optional[str] = None,
               password: Optional[str] = None) -> dict:
    """
    Seed (or re-seed) the Neo4j knowledge graph.
    Returns a dict with counts of what was created.
    """
    uri = uri or _neo4j_env("NEO4J_URI")
    user = user or _neo4j_env("NEO4J_USERNAME")
    password = password or _neo4j_env("NEO4J_PASSWORD")

    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(uri, auth=(user, password))

    stats = {
        "remedies": 0,
        "symptoms": 0,
        "bio_states": 0,
        "treats_edges": 0,
        "enhanced_by_edges": 0,
    }

    with driver.session() as session:
        # ── Indexes (idempotent) ─────────────────────────────────────────
        session.run(f"CREATE INDEX IF NOT EXISTS FOR (n:{REMEDY}) ON (n.name)")
        session.run(f"CREATE INDEX IF NOT EXISTS FOR (n:{SYMPTOM}) ON (n.name)")
        session.run(f"CREATE INDEX IF NOT EXISTS FOR (n:{BIOLOGICAL_STATE}) ON (n.name)")

        # ── Remedy nodes ─────────────────────────────────────────────────
        for r in REMEDIES:
            session.run(
                f"MERGE (n:{REMEDY} {{name: $name}}) "
                "SET n.base_score = $base_score",
                name=r["name"],
                base_score=r["base_score"],
            )
            stats["remedies"] += 1

        # ── Symptom nodes ────────────────────────────────────────────────
        for s in SYMPTOMS:
            session.run(
                f"MERGE (n:{SYMPTOM} {{name: $name}})",
                name=s,
            )
            stats["symptoms"] += 1

        # ── BiologicalState nodes ────────────────────────────────────────
        for b in BIO_STATES:
            session.run(
                f"MERGE (n:{BIOLOGICAL_STATE} {{name: $name}})",
                name=b,
            )
            stats["bio_states"] += 1

        # ── TREATS relationships ─────────────────────────────────────────
        for remedy_name, symptom_name in TREATS_EDGES:
            session.run(
                f"MATCH (r:{REMEDY} {{name: $remedy}}) "
                f"MATCH (s:{SYMPTOM} {{name: $symptom}}) "
                f"MERGE (r)-[:{TREATS}]->(s)",
                remedy=remedy_name,
                symptom=symptom_name,
            )
            stats["treats_edges"] += 1

        # ── ENHANCED_BY relationships (with adaptive weights) ────────────
        for remedy_name, bio_state_name, weight in ENHANCED_BY_EDGES:
            session.run(
                f"MATCH (r:{REMEDY} {{name: $remedy}}) "
                f"MATCH (b:{BIOLOGICAL_STATE} {{name: $bio_state}}) "
                f"MERGE (r)-[e:{ENHANCED_BY}]->(b) "
                "ON CREATE SET e.weight = $weight "
                "ON MATCH SET e.weight = CASE WHEN e.weight IS NULL "
                "             THEN $weight ELSE e.weight END",
                remedy=remedy_name,
                bio_state=bio_state_name,
                weight=weight,
            )
            stats["enhanced_by_edges"] += 1

    driver.close()
    logger.info("Graph RAG seed complete: %s", stats)
    return stats
