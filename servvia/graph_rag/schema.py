"""
ServVia Graph RAG — Neo4j Schema Constants.

Defines Node labels and Relationship types for the Outcome-Adaptive
Knowledge Graph used by the Graph RAG retrieval pipeline.
"""

# ──────────────────────────────────────────────
# Node Labels
# ──────────────────────────────────────────────
SYMPTOM = "Symptom"
REMEDY = "Remedy"
BIOLOGICAL_STATE = "BiologicalState"

# ──────────────────────────────────────────────
# Relationship Types
# ──────────────────────────────────────────────
TREATS = "TREATS"
CONTRAINDICATED_FOR = "CONTRAINDICATED_FOR"
ENHANCED_BY = "ENHANCED_BY"

# ──────────────────────────────────────────────
# Edge Weight Bounds (for ENHANCED_BY)
# ──────────────────────────────────────────────
EDGE_WEIGHT_MIN = 0.1
EDGE_WEIGHT_MAX = 5.0
EDGE_WEIGHT_DEFAULT = 1.0
