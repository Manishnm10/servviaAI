"""
ServVia 2.0 - Conversation Manager (Production Ready)
======================================================
Handles: 
- Conversation history with persistence
- Context tracking (conditions, herbs, medications)
- Medication additions and removals
- Session management
- Subject context (asking for child, parent, etc.)

Author: ServVia Team
Version: 2.1.0
"""

import logging
import json
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# Try to use Django cache for persistence
try:
    from django.core.cache import cache
    CACHE_AVAILABLE = True
except ImportError:
    cache = None
    CACHE_AVAILABLE = False
    logger.warning("Django cache not available - using in-memory storage")


@dataclass
class ConversationMessage:
    """Single message in conversation"""
    role:  str  # 'user' or 'assistant'
    content: str
    timestamp: str = field(default_factory=lambda:  datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)


@dataclass
class UserContext:
    """Tracked context for a user"""
    conditions: List[str] = field(default_factory=list)
    herbs: List[str] = field(default_factory=list)
    medications: List[str] = field(default_factory=list)
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserContext':
        return cls(
            conditions=data.get('conditions', []),
            herbs=data.get('herbs', []),
            medications=data.get('medications', []),
            last_updated=data.get('last_updated', datetime.now().isoformat())
        )


@dataclass
class SubjectContext:
    """Context for when user is asking about someone else (child, parent, etc.)"""
    asking_for_other: bool = False
    query_subject: str = None  # e.g., "8-year-old child"
    subject_age: int = None
    subject_age_group: str = None  # e.g., "child", "infant", "senior"
    subject_sex: str = None
    relationship:  str = None  # e.g., "child", "son", "mother"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SubjectContext':
        return cls(
            asking_for_other=data.get('asking_for_other', False),
            query_subject=data.get('query_subject'),
            subject_age=data.get('subject_age'),
            subject_age_group=data.get('subject_age_group'),
            subject_sex=data.get('subject_sex'),
            relationship=data.get('relationship'),
            timestamp=data.get('timestamp', datetime.now().isoformat())
        )
    
    def is_expired(self, timeout_minutes: int = 10) -> bool:
        """Check if subject context has expired"""
        if not self. timestamp:
            return True
        try:
            ts = datetime.fromisoformat(self.timestamp)
            age_seconds = (datetime.now() - ts).total_seconds()
            return age_seconds > (timeout_minutes * 60)
        except:
            return True


class ConversationManager:
    """
    Production-ready conversation manager with persistence. 
    
    Features:
    - Persistent storage via Django cache (falls back to in-memory)
    - Automatic context extraction from queries
    - Medication addition and removal detection
    - Conversation history management
    - Session timeout handling
    - Subject context tracking (asking for child, parent, etc.)
    """
    
    # Cache timeout (2 hours)
    CACHE_TIMEOUT = 7200
    
    # Subject context timeout (10 minutes)
    SUBJECT_CONTEXT_TIMEOUT = 10
    
    # Maximum messages to keep in history
    MAX_HISTORY = 20
    
    # Keywords for detecting medication removal
    REMOVAL_KEYWORDS = [
        'stopped taking', 'stop taking', 'no longer take', 'not taking anymore',
        'dont take anymore', 'stopped using', 'no longer use',
        'quit taking', 'off of', 'discontinued', 'not on anymore', 'no longer on',
        'stopped', 'quit', 'gave up', 'not anymore', 'no more'
    ]
    
    # Keywords for detecting medication addition
    ADDITION_KEYWORDS = [
        'i take', 'i am taking', 'im taking', 'taking', 'i use', 'i am using',
        'im using', 'i am on', 'im on', 'prescribed', 'started taking',
        'doctor gave', 'put me on', 'been taking'
    ]
    
    # Health conditions to track
    CONDITION_KEYWORDS = {
        'headache':  ['headache', 'head hurts', 'head pain', 'migraine', 'head ache'],
        'fever':  ['fever', 'temperature', 'feverish', 'high temp'],
        'cold': ['cold', 'runny nose', 'sneezing', 'stuffy nose', 'congestion', 'flu'],
        'cough': ['cough', 'coughing', 'dry cough', 'wet cough', 'persistent cough'],
        'nausea': ['nausea', 'nauseous', 'queasy', 'want to vomit', 'feeling sick'],
        'indigestion': ['indigestion', 'bloating', 'gas', 'acidity', 'heartburn', 'acid reflux', 'stomach upset'],
        'sore throat': ['sore throat', 'throat pain', 'throat hurts', 'scratchy throat'],
        'anxiety': ['anxiety', 'anxious', 'worried', 'nervous', 'panic', 'stressed'],
        'stress': ['stress', 'stressed', 'overwhelmed', 'burnout', 'tension'],
        'insomnia': ['insomnia', 'cant sleep', 'cannot sleep', 'trouble sleeping', 'sleepless', 'sleep problem'],
        'fatigue': ['fatigue', 'tired', 'exhausted', 'no energy', 'low energy', 'weakness'],
        'joint pain': ['joint pain', 'arthritis', 'joints hurt', 'knee pain', 'joint ache'],
        'back pain': ['back pain', 'backache', 'back hurts', 'lower back pain'],
        'toothache': ['toothache', 'tooth pain', 'tooth hurts', 'dental pain'],
        'acne': ['acne', 'pimples', 'breakout', 'zits', 'skin breakout'],
        'diarrhea': ['diarrhea', 'loose stools', 'loose motions', 'upset stomach'],
        'constipation': ['constipation', 'constipated', 'irregular bowel'],
        'menstrual cramps': ['menstrual cramps', 'period pain', 'period cramps', 'menstrual pain', 'dysmenorrhea'],
        'pms': ['pms', 'premenstrual', 'pre-menstrual', 'before period'],
    }
    
    # Herbs to track
    HERB_KEYWORDS = [
        'ginger', 'turmeric', 'peppermint', 'mint', 'garlic', 'honey', 'tulsi', 'basil',
        'ashwagandha', 'chamomile', 'cinnamon', 'clove', 'licorice', 'ginseng', 'valerian',
        'neem', 'amla', 'fennel', 'cumin', 'coriander', 'fenugreek', 'ajwain', 'cardamom',
        'lavender', 'eucalyptus', 'tea tree', 'aloe vera', 'aloe', 'coconut oil',
        'ginkgo', 'echinacea', 'elderberry', 'brahmi', 'giloy', 'triphala', 'moringa',
        'shatavari', 'black pepper', 'cayenne', 'oregano', 'thyme', 'rosemary',
        'chasteberry', 'vitex', 'evening primrose', 'boswellia', 'devils claw',
        'magnesium', 'zinc', 'vitamin c', 'vitamin d',
    ]
    
    # Medications to track
    MEDICATION_KEYWORDS = {
        'aspirin': ['aspirin', 'disprin', 'ecosprin'],
        'ibuprofen':  ['ibuprofen', 'advil', 'motrin', 'brufen'],
        'paracetamol': ['paracetamol', 'acetaminophen', 'tylenol', 'crocin', 'dolo'],
        'warfarin': ['warfarin', 'coumadin'],
        'blood thinner': ['blood thinner', 'blood thinners', 'anticoagulant'],
        'metformin': ['metformin', 'glycomet', 'glucophage'],
        'insulin': ['insulin'],
        'blood pressure medication': ['blood pressure', 'bp medicine', 'bp medication', 'bp med', 'antihypertensive', 'amlodipine', 'lisinopril'],
        'thyroid medication': ['thyroid', 'levothyroxine', 'synthroid', 'thyroxine', 'eltroxin'],
        'antidepressant': ['antidepressant', 'ssri', 'prozac', 'zoloft', 'lexapro', 'sertraline', 'fluoxetine'],
        'sedative': ['sedative', 'sleeping pill', 'sleep medication', 'benzodiazepine', 'alprazolam', 'xanax'],
        'statin': ['statin', 'atorvastatin', 'cholesterol medicine', 'lipitor'],
        'pan d': ['pan d', 'pan-d'],
        'pantoprazole': ['pantoprazole', 'pantop', 'protonix'],
        'omeprazole': ['omeprazole', 'omez', 'prilosec'],
        'metoprolol': ['metoprolol', 'beta blocker'],
        'prednisone': ['prednisone', 'steroid', 'corticosteroid'],
        'antibiotic': ['antibiotic', 'amoxicillin', 'azithromycin', 'ciprofloxacin'],
    }
    
    # Keywords that indicate user is switching to asking about themselves
    SELF_REFERENCE_KEYWORDS = [
        'i have', 'i am', 'im having', 'i feel', 'my head', 'my stomach',
        'i need', 'i want', 'for me', 'help me', 'i got'
    ]
    
    def __init__(self):
        """Initialize the conversation manager"""
        self._memory_store: Dict[str, Dict] = {}
        logger.info(f"ConversationManager initialized (cache={'enabled' if CACHE_AVAILABLE else 'disabled'})")
    
    # =========================================================================
    # CACHE HELPERS
    # =========================================================================
    
    def _get_cache_key(self, user_id: str, key_type:  str) -> str:
        """Generate a cache key for user data"""
        # Hash email for privacy in cache keys
        user_hash = hashlib.md5(user_id. encode()).hexdigest()[:12]
        return f"servvia_v2_{user_hash}_{key_type}"
    
    def _get_data(self, user_id: str, key_type: str) -> Dict:
        """Get data from cache or memory"""
        cache_key = self._get_cache_key(user_id, key_type)
        
        # Try cache first
        if CACHE_AVAILABLE and cache: 
            try:
                data = cache.get(cache_key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Cache read failed:  {e}")
        
        # Fall back to memory
        return self._memory_store.get(cache_key, {})
    
    def _set_data(self, user_id: str, key_type:  str, data: Dict):
        """Set data in cache and memory"""
        cache_key = self._get_cache_key(user_id, key_type)
        
        # Always store in memory as backup
        self._memory_store[cache_key] = data
        
        # Try to store in cache
        if CACHE_AVAILABLE and cache: 
            try:
                cache. set(cache_key, json. dumps(data), self.CACHE_TIMEOUT)
            except Exception as e:
                logger.warning(f"Cache write failed: {e}")
    
    # =========================================================================
    # MESSAGE MANAGEMENT
    # =========================================================================
    
    def add_message(self, user_id: str, role: str, content: str, metadata: Dict = None):
        """
        Add a message to conversation history. 
        
        Args:
            user_id: User identifier (email)
            role: 'user' or 'assistant'
            content: Message content
            metadata: Optional metadata
        """
        history = self._get_data(user_id, 'history')
        
        if 'messages' not in history: 
            history['messages'] = []
        
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata':  metadata or {}
        }
        
        history['messages'].append(message)
        
        # Trim to max history
        if len(history['messages']) > self.MAX_HISTORY:
            history['messages'] = history['messages'][-self. MAX_HISTORY:]
        
        self._set_data(user_id, 'history', history)
        
        logger.info(f"Added {role} message for {user_id[: 20]}...  (total: {len(history['messages'])})")
    
    def get_history(self, user_id: str) -> List[Dict]:
        """Get conversation history for user"""
        history = self._get_data(user_id, 'history')
        return history.get('messages', [])
    
    def get_formatted_history(self, user_id:  str, max_messages: int = 10) -> str:
        """
        Get conversation history formatted as a string.
        
        Args:
            user_id: User identifier
            max_messages: Maximum messages to include
        
        Returns:
            Formatted conversation history
        """
        messages = self.get_history(user_id)
        
        if not messages:
            return ""
        
        # Get last N messages
        recent = messages[-max_messages:]
        
        lines = []
        for msg in recent:
            role = "User" if msg['role'] == 'user' else "ServVia"
            content = msg['content']
            
            # Truncate very long messages
            if len(content) > 500:
                content = content[:500] + "..."
            
            lines.append(f"{role}:  {content}")
        
        return "\n".join(lines)
    
    # =========================================================================
    # SUBJECT CONTEXT MANAGEMENT (Asking for Child, Parent, etc.)
    # =========================================================================
    
    def update_subject_context(
        self,
        user_id: str,
        asking_for_other:  bool = False,
        query_subject: str = None,
        subject_age: int = None,
        subject_age_group:  str = None,
        subject_sex: str = None,
        relationship: str = None
    ):
        """
        Store context about who the user is asking for (child, parent, etc.)
        
        This allows follow-up questions to maintain the same subject context.
        For example, if user says "my 8 year old child has headache" and then
        asks "what about fever? ", we know they are still asking about the child.
        
        Args:
            user_id: User identifier
            asking_for_other: True if asking for someone else
            query_subject: Description like "8-year-old child"
            subject_age: Age of the subject
            subject_age_group:  Age group (infant, child, senior, etc.)
            subject_sex: Sex of the subject if known
            relationship: Relationship (child, son, daughter, mother, etc.)
        """
        subject_data = {
            'asking_for_other': asking_for_other,
            'query_subject': query_subject,
            'subject_age': subject_age,
            'subject_age_group': subject_age_group,
            'subject_sex': subject_sex,
            'relationship': relationship,
            'timestamp': datetime.now().isoformat()
        }
        
        self._set_data(user_id, 'subject_context', subject_data)
        
        logger.info(f"Updated subject context for {user_id[: 20]}.. .:  {query_subject} (age: {subject_age}, rel: {relationship})")
    
    def get_subject_context(self, user_id: str) -> Dict:
        """
        Get the stored subject context for follow-up queries.
        
        Returns empty dict if: 
        - No subject context exists
        - Subject context has expired (> 10 minutes old)
        - User has switched to asking about themselves
        
        Returns:
            Dict with subject context or empty dict
        """
        subject_data = self._get_data(user_id, 'subject_context')
        
        if not subject_data:
            return {}
        
        if not subject_data.get('asking_for_other'):
            return {}
        
        # Check if context is still fresh
        timestamp = subject_data.get('timestamp')
        if timestamp: 
            try:
                ts = datetime.fromisoformat(timestamp)
                age_seconds = (datetime.now() - ts).total_seconds()
                if age_seconds > (self. SUBJECT_CONTEXT_TIMEOUT * 60):
                    logger. info(f"Subject context expired for {user_id[:20]}...  (age: {age_seconds}s)")
                    return {}
            except:
                pass
        
        return subject_data
    
    def clear_subject_context(self, user_id: str):
        """Clear subject context (when user asks about themselves)"""
        cache_key = self._get_cache_key(user_id, 'subject')
        
        # Instead of completely clearing, mark as inactive but preserve the data
        current_context = self._get_data(user_id, 'subject')
        if current_context:
            # Store as "previous" context before clearing
            self._set_data(user_id, 'previous_subject', current_context)
        
        self._set_data(user_id, 'subject', {})
        
        logger.info(f"Cleared subject context for {user_id[: 20]}...  (preserved as previous)")
    
    def get_previous_subject_context(self, user_id:  str) -> Dict:
        """
        Get the PREVIOUS subject context (before it was cleared).
        This allows us to restore context when user asks about the same person again. 
        """
        return self._get_data(user_id, 'previous_subject')

    
    def should_clear_subject_context(self, query:  str) -> bool:
        """
        Check if the query indicates user is now asking about themselves.
    
        Args:
            query: User's query text
    
        Returns:
            True if user appears to be asking about themselves now
        """
        query_lower = query.lower()
    
        # Strong self-reference indicators (user is asking about themselves)
        self_reference_patterns = [
            # Direct self-reference
            'i have', 'i am', 'i feel', 'i got', 'i need', 'i want',
            'im having', 'im feeling', 'ive got', 'ive been',
            # Body part ownership
            'my head', 'my stomach', 'my back', 'my throat', 'my chest',
            'my knee', 'my leg', 'my arm', 'my skin', 'my eyes',
            'my body', 'my joints', 'my muscles', 'my tooth', 'my teeth',
            # Personal requests
            'help me', 'for me', 'give me', 'tell me what i',
            'what should i', 'what can i', 'how can i', 'how do i',
            # Symptoms about self
            'i cant sleep', 'i cannot sleep', 'i dont feel', 
            'i woke up with', 'i started having', 'i keep getting',
            'makes me', 'giving me', 'causing me',
        ]
    
        for pattern in self_reference_patterns: 
            if pattern in query_lower:
                return True
    
        return False

    
    # =========================================================================
    # CONTEXT MANAGEMENT
    # =========================================================================
    
    def get_context(self, user_id: str) -> Dict[str, any]:
        """
        Get tracked context for user, including subject context. 
        
        Returns: 
            Dict with 'conditions', 'herbs', 'medications' lists
            and subject context fields if asking for someone else
        """
        context_data = self._get_data(user_id, 'context')
        subject_data = self. get_subject_context(user_id)
        
        result = {
            'conditions': context_data.get('conditions', []),
            'herbs': context_data.get('herbs', []),
            'medications': context_data.get('medications', []),
        }
        
        # Merge subject context if present and not expired
        if subject_data. get('asking_for_other'):
            result['asking_for_other'] = True
            result['query_subject'] = subject_data. get('query_subject')
            result['subject_age'] = subject_data.get('subject_age')
            result['subject_age_group'] = subject_data. get('subject_age_group')
            result['subject_sex'] = subject_data.get('subject_sex')
            result['relationship'] = subject_data.get('relationship')
        
        return result
    
    def update_context(self, user_id: str, query: str) -> Dict[str, List[str]]:
        """
        Update context based on user query.
        Handles both additions and removals.
        
        Args:
            user_id:  User identifier
            query: User's query text
        
        Returns: 
            Dict with 'added' and 'removed' lists
        """
        query_lower = query.lower()
        
        # Check if user is now asking about themselves (clear subject context)
        if self.should_clear_subject_context(query):
            existing_subject = self.get_subject_context(user_id)
            if existing_subject. get('asking_for_other'):
                logger.info(f"User switched to asking about themselves, clearing subject context")
                self. clear_subject_context(user_id)
        
        # Get existing context
        context = self._get_data(user_id, 'context')
        if not context:
            context = {'conditions': [], 'herbs': [], 'medications': []}
        
        changes = {'added': [], 'removed': []}
        
        # =====================================================================
        # CHECK FOR REMOVALS FIRST
        # =====================================================================
        is_removal_context = any(kw in query_lower for kw in self.REMOVAL_KEYWORDS)
        
        if is_removal_context:
            # Check which medications are being removed
            for med_name, keywords in self.MEDICATION_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in query_lower:
                        # User is saying they stopped this medication
                        if med_name in context. get('medications', []):
                            context['medications'].remove(med_name)
                            changes['removed']. append(f"medication:  {med_name}")
                            logger.info(f"Removed medication: {med_name}")
                        break
            
            # Check if removing herbs
            for herb in self.HERB_KEYWORDS: 
                if herb in query_lower: 
                    if herb in context.get('herbs', []):
                        context['herbs'].remove(herb)
                        changes['removed'].append(f"herb: {herb}")
                        logger.info(f"Removed herb: {herb}")
        
        # =====================================================================
        # CHECK FOR ADDITIONS (only if not in removal context)
        # =====================================================================
        if not is_removal_context:
            # Add conditions
            for condition, keywords in self.CONDITION_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in query_lower:
                        if condition not in context.get('conditions', []):
                            context. setdefault('conditions', []).append(condition)
                            changes['added'].append(f"condition: {condition}")
                            logger.info(f"Added condition: {condition}")
                        break
            
            # Add herbs
            for herb in self. HERB_KEYWORDS:
                if herb in query_lower:
                    if herb not in context.get('herbs', []):
                        context.setdefault('herbs', []).append(herb)
                        changes['added'].append(f"herb: {herb}")
                        logger.info(f"Added herb: {herb}")
            
            # Add medications
            is_addition_context = any(kw in query_lower for kw in self.ADDITION_KEYWORDS)
            
            for med_name, keywords in self. MEDICATION_KEYWORDS.items():
                for keyword in keywords: 
                    if keyword in query_lower:
                        # Only add if in addition context or medication directly mentioned
                        if is_addition_context or len(keyword) > 3:  # Avoid short matches
                            if med_name not in context.get('medications', []):
                                context.setdefault('medications', []).append(med_name)
                                changes['added'].append(f"medication: {med_name}")
                                logger.info(f"Added medication: {med_name}")
                        break
        
        # Update timestamp
        context['last_updated'] = datetime.now().isoformat()
        
        # Save context
        self._set_data(user_id, 'context', context)
        
        if changes['added'] or changes['removed']:
            logger.info(f"Context updated for {user_id[:20]}.. .: +{len(changes['added'])} -{len(changes['removed'])}")
        
        return changes
    
    def get_current_condition(self, user_id: str) -> Optional[str]:
        """Get the most recently discussed condition"""
        context = self. get_context(user_id)
        conditions = context.get('conditions', [])
        
        if conditions:
            return conditions[-1]  # Most recent
        return None
    
    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================
    
    def clear_conversation(self, user_id: str):
        """Clear all conversation data for a user"""
        self._set_data(user_id, 'history', {})
        self._set_data(user_id, 'context', {})
        self._set_data(user_id, 'subject_context', {})
        
        logger.info(f"Cleared conversation for {user_id[: 20]}...")
    
    def get_context_summary(self, user_id: str) -> str:
        """Get a human-readable summary of tracked context"""
        ctx = self.get_context(user_id)
        
        parts = []
        
        # Subject context
        if ctx.get('asking_for_other'):
            parts.append(f"Asking for:  {ctx. get('query_subject', 'someone else')}")
        
        if ctx.get('medications'):
            parts.append(f"Medications: {', '.join(ctx['medications'])}")
        
        if ctx.get('conditions'):
            parts.append(f"Discussing: {', '.join(ctx['conditions'])}")
        
        if ctx.get('herbs'):
            parts.append(f"Remedies mentioned: {', '.join(ctx['herbs'])}")
        
        return " | ".join(parts) if parts else "No context tracked yet"
    
    def is_follow_up_question(self, query: str, user_id: str) -> bool:
        """Detect if query is a follow-up to previous conversation"""
        query_lower = query.lower()
        
        # Follow-up indicators
        follow_up_words = [
            'what about', 'how about', 'and', 'also', 'too',
            'can i', 'should i', 'is it', 'will it', 'does it',
            'how long', 'how much', 'how often', 'how do',
            'what if', 'but', 'instead', 'alternatively',
            'tell me more', 'more about', 'explain',
            'the same', 'that', 'this', 'it',
            'simpler', 'easier', 'another', 'different',
        ]
        
        for word in follow_up_words:
            if word in query_lower: 
                return True
        
        # Short queries after conversation are usually follow-ups
        if len(query. split()) <= 6:
            history = self.get_history(user_id)
            if len(history) > 0:
                return True
        
        return False
    
    def get_full_context_for_query(self, user_id: str, query: str) -> Dict:
        """
        Get complete context for processing a query.
        
        This is a convenience method that: 
        1. Checks if it's a follow-up question
        2. Gets subject context if asking for someone else
        3. Gets conversation context (conditions, herbs, medications)
        4. Returns everything needed for response generation
        
        Args: 
            user_id: User identifier
            query: Current query
        
        Returns:
            Dict with all context information
        """
        is_follow_up = self.is_follow_up_question(query, user_id)
        context = self.get_context(user_id)
        subject_context = self.get_subject_context(user_id)
        
        return {
            'is_follow_up': is_follow_up,
            'conditions': context.get('conditions', []),
            'herbs': context. get('herbs', []),
            'medications': context.get('medications', []),
            'asking_for_other': subject_context.get('asking_for_other', False),
            'query_subject': subject_context.get('query_subject'),
            'subject_age': subject_context.get('subject_age'),
            'subject_age_group': subject_context.get('subject_age_group'),
            'subject_sex':  subject_context.get('subject_sex'),
            'relationship': subject_context.get('relationship'),
        }


# Create global instance
conversation_manager = ConversationManager()