"""
ServVia Graph RAG — Healthcare Knowledge Seed Data.

Pre-populated remedy/symptom/biological-state knowledge graph that serves
as the starting point for outcome-adaptive personalization.  No external
database required — the graph is seeded into a local NetworkX graph and
persisted to a JSON file that accumulates user feedback over time.
"""

# ── Remedy node definitions ────────────────────────────────────────────────
# base_score: evidence-based initial confidence (0–1 scale)
REMEDIES = [
    {"name": "ginger",         "base_score": 0.85},
    {"name": "turmeric",       "base_score": 0.82},
    {"name": "chamomile",      "base_score": 0.78},
    {"name": "ashwagandha",    "base_score": 0.80},
    {"name": "magnesium",      "base_score": 0.83},
    {"name": "melatonin",      "base_score": 0.87},
    {"name": "probiotics",     "base_score": 0.81},
    {"name": "vitamin_d",      "base_score": 0.84},
    {"name": "omega3",         "base_score": 0.83},
    {"name": "rest",           "base_score": 0.90},
    {"name": "hydration",      "base_score": 0.88},
    {"name": "ginkgo",         "base_score": 0.72},
    {"name": "valerian_root",  "base_score": 0.75},
    {"name": "lavender",       "base_score": 0.76},
    {"name": "echinacea",      "base_score": 0.74},
    {"name": "zinc",           "base_score": 0.79},
    {"name": "vitamin_c",      "base_score": 0.82},
    {"name": "green_tea",      "base_score": 0.77},
    {"name": "peppermint",     "base_score": 0.76},
    {"name": "licorice_root",  "base_score": 0.68},
]

# ── Symptom node definitions ───────────────────────────────────────────────
SYMPTOMS = [
    "fatigue", "headache", "joint_pain", "insomnia", "nausea",
    "bloating", "anxiety", "brain_fog", "muscle_ache", "inflammation",
    "cold", "fever", "digestive_issues", "stress", "low_energy",
]

# ── Biological state nodes (circadian + seasonal) ─────────────────────────
BIO_STATES = ["morning", "afternoon", "evening", "night", "default"]

# ── TREATS edges: (remedy, symptom) ───────────────────────────────────────
TREATS_EDGES = [
    # ginger
    ("ginger",        "nausea"),
    ("ginger",        "bloating"),
    ("ginger",        "inflammation"),
    ("ginger",        "digestive_issues"),
    # turmeric
    ("turmeric",      "inflammation"),
    ("turmeric",      "joint_pain"),
    ("turmeric",      "brain_fog"),
    ("turmeric",      "muscle_ache"),
    # chamomile
    ("chamomile",     "anxiety"),
    ("chamomile",     "insomnia"),
    ("chamomile",     "digestive_issues"),
    ("chamomile",     "stress"),
    # ashwagandha
    ("ashwagandha",   "stress"),
    ("ashwagandha",   "fatigue"),
    ("ashwagandha",   "anxiety"),
    ("ashwagandha",   "brain_fog"),
    # magnesium
    ("magnesium",     "insomnia"),
    ("magnesium",     "muscle_ache"),
    ("magnesium",     "stress"),
    ("magnesium",     "headache"),
    ("magnesium",     "anxiety"),
    # melatonin
    ("melatonin",     "insomnia"),
    ("melatonin",     "fatigue"),
    # probiotics
    ("probiotics",    "bloating"),
    ("probiotics",    "digestive_issues"),
    # vitamin_d
    ("vitamin_d",     "fatigue"),
    ("vitamin_d",     "low_energy"),
    ("vitamin_d",     "brain_fog"),
    # omega3
    ("omega3",        "inflammation"),
    ("omega3",        "brain_fog"),
    ("omega3",        "joint_pain"),
    # rest
    ("rest",          "fatigue"),
    ("rest",          "muscle_ache"),
    ("rest",          "headache"),
    ("rest",          "insomnia"),
    # hydration
    ("hydration",     "headache"),
    ("hydration",     "fatigue"),
    ("hydration",     "brain_fog"),
    ("hydration",     "low_energy"),
    # ginkgo
    ("ginkgo",        "brain_fog"),
    ("ginkgo",        "fatigue"),
    ("ginkgo",        "low_energy"),
    # valerian_root
    ("valerian_root", "insomnia"),
    ("valerian_root", "anxiety"),
    ("valerian_root", "stress"),
    # lavender
    ("lavender",      "anxiety"),
    ("lavender",      "insomnia"),
    ("lavender",      "stress"),
    ("lavender",      "headache"),
    # echinacea
    ("echinacea",     "cold"),
    ("echinacea",     "fever"),
    # zinc
    ("zinc",          "cold"),
    ("zinc",          "fatigue"),
    # vitamin_c
    ("vitamin_c",     "cold"),
    ("vitamin_c",     "fever"),
    ("vitamin_c",     "fatigue"),
    # green_tea
    ("green_tea",     "brain_fog"),
    ("green_tea",     "fatigue"),
    ("green_tea",     "low_energy"),
    # peppermint
    ("peppermint",    "headache"),
    ("peppermint",    "nausea"),
    ("peppermint",    "digestive_issues"),
    # licorice_root
    ("licorice_root", "digestive_issues"),
    ("licorice_root", "inflammation"),
    ("licorice_root", "nausea"),
]

# ── ENHANCED_BY edges: (remedy, bio_state, initial_weight) ────────────────
# Weight 1.0 = neutral; >1.0 = better at this bio_state; <1.0 = less effective
ENHANCED_BY_EDGES = [
    # Sleep-support remedies — most effective in evening/night
    ("melatonin",     "evening", 1.8),
    ("melatonin",     "night",   2.0),
    ("melatonin",     "morning", 0.3),
    ("valerian_root", "evening", 1.7),
    ("valerian_root", "night",   1.9),
    ("chamomile",     "evening", 1.6),
    ("chamomile",     "night",   1.8),
    ("lavender",      "evening", 1.5),
    ("lavender",      "night",   1.7),
    # Morning energisers
    ("ashwagandha",   "morning", 1.6),
    ("green_tea",     "morning", 1.7),
    ("vitamin_d",     "morning", 1.8),
    ("ginkgo",        "morning", 1.5),
    ("ginkgo",        "afternoon", 1.4),
    # Anti-inflammatory — better after activity (afternoon)
    ("turmeric",      "morning",   1.4),
    ("turmeric",      "evening",   1.4),
    ("omega3",        "afternoon", 1.4),
    ("omega3",        "morning",   1.3),
    # Digestive — morning/after meals
    ("ginger",        "morning",   1.5),
    ("ginger",        "afternoon", 1.4),
    ("probiotics",    "morning",   1.6),
    ("peppermint",    "afternoon", 1.4),
    ("peppermint",    "evening",   1.3),
    ("licorice_root", "morning",   1.3),
    # Magnesium — evening relaxation
    ("magnesium",     "evening",   1.7),
    ("magnesium",     "night",     1.5),
    # Immune support — morning
    ("vitamin_c",     "morning",   1.5),
    ("echinacea",     "morning",   1.4),
    ("zinc",          "morning",   1.3),
    # Rest + hydration — any time (default only, no phase boost)
    ("rest",          "default",   1.0),
    ("hydration",     "default",   1.0),
]
