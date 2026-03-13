from django.db import models
from neo4j import GraphDatabase
import os
import logging

logger = logging. getLogger(__name__)


class EvidenceTier:
    TIER_1_RCT = 1
    TIER_2_MECHANISTIC = 2
    TIER_3_TRADITIONAL = 3
    TIER_4_ANECDOTAL = 4
    TIER_5_UNSAFE = 5
    
    TIER_CHOICES = [
        (TIER_1_RCT, 'Tier 1: RCT/Meta-analysis'),
        (TIER_2_MECHANISTIC, 'Tier 2: Mechanistic'),
        (TIER_3_TRADITIONAL, 'Tier 3: Traditional Use'),
        (TIER_4_ANECDOTAL, 'Tier 4: Anecdotal'),
        (TIER_5_UNSAFE, 'Tier 5: Unsafe'),
    ]
    
    TIER_WEIGHTS = {
        TIER_1_RCT: 1.0,
        TIER_2_MECHANISTIC: 0.75,
        TIER_3_TRADITIONAL: 0.5,
        TIER_4_ANECDOTAL: 0.25,
        TIER_5_UNSAFE: 0.0,
    }


class Neo4jConnection:
    _instance = None
    _driver = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._driver is None:
            uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
            user = os.environ. get('NEO4J_USER', 'neo4j')
            password = os.environ.get('NEO4J_PASSWORD', 'password')
            try:
                self._driver = GraphDatabase. driver(uri, auth=(user, password))
                logger.info(f"Connected to Neo4j at {uri}")
            except Exception as e:
                logger.warning(f"Neo4j not available: {e}")
                self._driver = None
    
    @property
    def driver(self):
        return self._driver
    
    def execute_query(self, query, parameters=None):
        if not self._driver:
            return []
        try:
            with self._driver.session() as session:
                result = session. run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger. error(f"Neo4j query error: {e}")
            return []


class Herb(models. Model):
    name = models.CharField(max_length=200, unique=True)
    scientific_name = models.CharField(max_length=300, blank=True)
    common_names = models. JSONField(default=list)
    description = models.TextField(blank=True)
    bioactive_compounds = models. JSONField(default=list)
    traditional_uses = models. JSONField(default=list)
    contraindications = models. JSONField(default=list)
    drug_interactions = models. JSONField(default=list)
    created_at = models. DateTimeField(auto_now_add=True)
    updated_at = models. DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'servvia_herbs'
    
    def __str__(self):
        return f"{self.name} ({self.scientific_name})"


class Disease(models.Model):
    name = models.CharField(max_length=200, unique=True)
    icd_code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    symptoms = models.JSONField(default=list)
    affected_systems = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'servvia_diseases'
    
    def __str__(self):
        return self.name


class HerbDiseaseEvidence(models.Model):
    herb = models.ForeignKey(Herb, on_delete=models. CASCADE, related_name='disease_evidence')
    disease = models.ForeignKey(Disease, on_delete=models.CASCADE, related_name='herb_evidence')
    evidence_tier = models.IntegerField(choices=EvidenceTier.TIER_CHOICES, default=4)
    pubmed_ids = models. JSONField(default=list)
    mechanism_of_action = models.TextField(blank=True)
    efficacy_summary = models.TextField(blank=True)
    scientific_confidence_score = models.FloatField(default=0. 0)
    created_at = models. DateTimeField(auto_now_add=True)
    updated_at = models. DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'servvia_herb_disease_evidence'
        unique_together = ['herb', 'disease']
    
    def calculate_confidence_score(self):
        base_score = EvidenceTier. TIER_WEIGHTS.get(self. evidence_tier, 0.25)
        pubmed_boost = min(len(self.pubmed_ids) * 0.05, 0.2)
        contraindication_penalty = 0.1 if self.herb.contraindications else 0
        score = (base_score + pubmed_boost - contraindication_penalty)
        self.scientific_confidence_score = max(0, min(1, score)) * 10
        return self.scientific_confidence_score


class Compound(models.Model):
    name = models.CharField(max_length=200, unique=True)
    chemical_formula = models. CharField(max_length=100, blank=True)
    mechanism = models.TextField(blank=True)
    found_in_herbs = models.ManyToManyField(Herb, related_name='compounds')
    therapeutic_effects = models.JSONField(default=list)
    
    class Meta:
        db_table = 'servvia_compounds'
    
    def __str__(self):
        return self.name
