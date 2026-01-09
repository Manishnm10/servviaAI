"""
ServVia Intent Classifier - Simplified
Detects query type but lets OpenAI handle all responses
"""
import logging
from typing import Dict, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    HOME_REMEDY = "home_remedy"
    EMERGENCY = "emergency"
    GENERAL_HEALTH = "general_health"


class IntentClassifier:
    """Simple intent classifier - OpenAI handles all responses"""
    
    def __init__(self):
        self. emergency_keywords = [
            'cpr', 'not breathing', 'no pulse', 'heart attack',
            'stroke', 'choking', 'heimlich', 'unconscious',
            'severe bleeding', 'overdose', 'poisoning',
            'seizure', 'anaphylaxis', 'cant breathe',
            'chest pain severe', 'heart stopped', 'drowning',
            'suicide', 'self harm', 'broken bone', 'fracture',
            'snake bite', 'head injury'
        ]
        
        self.remedy_conditions = [
            'headache', 'cold', 'cough', 'fever', 'sore throat',
            'indigestion', 'bloating', 'gas', 'acidity', 'constipation',
            'nausea', 'fatigue', 'tired', 'stress', 'anxiety',
            'insomnia', 'acne', 'dandruff', 'hair fall', 'joint pain',
            'back pain', 'toothache', 'skin rash', 'itching',
            'minor burn', 'sunburn', 'immunity', 'digestion'
        ]
    
    def classify(self, query: str) -> Tuple[QueryIntent, Dict]:
        """Classify query intent"""
        query_lower = query. lower(). strip()
        
        metadata = {
            'original_query': query,
            'is_emergency': False,
            'apply_trust_engine': True
        }
        
        # Check for emergencies
        for keyword in self.emergency_keywords:
            if keyword in query_lower:
                logger.info(f"EMERGENCY detected: {keyword}")
                metadata['is_emergency'] = True
                metadata['apply_trust_engine'] = False
                return QueryIntent.EMERGENCY, metadata
        
        # Check for remedy conditions
        for condition in self.remedy_conditions:
            if condition in query_lower:
                logger.info(f"Remedy condition: {condition}")
                return QueryIntent.HOME_REMEDY, metadata
        
        # Default: general health
        return QueryIntent.GENERAL_HEALTH, metadata
    
    def get_emergency_disclaimer(self) -> str:
        """Add disclaimer to emergency responses"""
        return """

---

🚨 **IMPORTANT: This is potentially a medical emergency.**

**Call emergency services immediately:**
- India: 112
- US: 911
- UK: 999

**The information above is for guidance only. Professional medical help is essential.**"""
