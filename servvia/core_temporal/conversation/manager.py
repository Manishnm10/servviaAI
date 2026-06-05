"""
ServVia 2. 0 - Conversation Manager (Production Ready)
======================================================
Handles:
- Conversation history with persistence
- Context tracking (conditions, herbs, medications)
- Medication additions and removals
- Session management

Author: ServVia Team
Version: 2.0. 0
"""

import logging
import json
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict

# Async support for Django ORM
from asgiref.sync import sync_to_async

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
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str = field(default_factory=lambda: datetime. now().isoformat())
    metadata: Dict = field(default_factory=dict)


@dataclass
class UserContext:
    """Tracked context for a user"""
    conditions: List[str] = field(default_factory=list)
    herbs: List[str] = field(default_factory=list)
    medications: List[str] = field(default_factory=list)
    last_updated: str = field(default_factory=lambda: datetime.now(). isoformat())
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserContext':
        return cls(
            conditions=data.get('conditions', []),
            herbs=data.get('herbs', []),
            medications=data. get('medications', []),
            last_updated=data.get('last_updated', datetime.now().isoformat())
        )


class ConversationManager:
    """
    Production-ready conversation manager with persistence. 
    
    Features:
    - Persistent storage via Django cache (falls back to in-memory)
    - Automatic context extraction from queries
    - Medication addition and removal detection
    - Conversation history management
    - Session timeout handling
    """
    
    # Cache timeout (2 hours)
    CACHE_TIMEOUT = 7200
    
    # Maximum messages to keep in history
    MAX_HISTORY = 20
    
    # Keywords for detecting medication removal
    REMOVAL_KEYWORDS = [
        'stopped taking', 'stop taking', 'no longer take', 'not taking anymore',
        "don't take anymore", 'dont take anymore', 'stopped using', 'no longer use',
        'quit taking', 'off of', 'discontinued', 'not on anymore', 'no longer on',
        'stopped', 'quit', 'gave up', 'not anymore', 'no more'
    ]
    
    # Keywords for detecting medication addition
    ADDITION_KEYWORDS = [
        'i take', 'i am taking', "i'm taking", 'taking', 'i use', 'i am using',
        "i'm using", 'i am on', "i'm on", 'prescribed', 'started taking',
        'doctor gave', 'put me on', 'been taking'
    ]
    
    # TEMPORAL KEYWORDS - For Objective 1: Extract medication start/stop dates
    TEMPORAL_KEYWORDS = {
        'days': r'(\d+)\s*days?\s*(ago|back|since)',
        'weeks': r'(\d+)\s*weeks?\s*(ago|back|since)',
        'months': r'(\d+)\s*months?\s*(ago|back|since)',
        'yesterday': r'yesterday',
        'today': r'today',
        'last_week': r'last\s*week',
        'recently': r'recently|just\s*started|just\s*stopped',
    }
    
    # Health conditions to track
    CONDITION_KEYWORDS = {
        'headache': ['headache', 'head hurts', 'head pain', 'migraine', 'head ache'],
        'fever': ['fever', 'temperature', 'feverish', 'high temp'],
        'cold': ['cold', 'runny nose', 'sneezing', 'stuffy nose', 'congestion', 'flu'],
        'cough': ['cough', 'coughing', 'dry cough', 'wet cough', 'persistent cough'],
        'nausea': ['nausea', 'nauseous', 'queasy', 'want to vomit', 'feeling sick'],
        'indigestion': ['indigestion', 'bloating', 'gas', 'acidity', 'heartburn', 'acid reflux', 'stomach upset'],
        'sore throat': ['sore throat', 'throat pain', 'throat hurts', 'scratchy throat'],
        'anxiety': ['anxiety', 'anxious', 'worried', 'nervous', 'panic', 'stressed'],
        'stress': ['stress', 'stressed', 'overwhelmed', 'burnout', 'tension'],
        'insomnia': ['insomnia', 'cant sleep', "can't sleep", 'trouble sleeping', 'sleepless', 'sleep problem'],
        'fatigue': ['fatigue', 'tired', 'exhausted', 'no energy', 'low energy', 'weakness'],
        'joint pain': ['joint pain', 'arthritis', 'joints hurt', 'knee pain', 'joint ache'],
        'back pain': ['back pain', 'backache', 'back hurts', 'lower back pain'],
        'toothache': ['toothache', 'tooth pain', 'tooth hurts', 'dental pain'],
        'acne': ['acne', 'pimples', 'breakout', 'zits', 'skin breakout'],
        'diarrhea': ['diarrhea', 'loose stools', 'loose motions', 'upset stomach'],
        'constipation': ['constipation', 'constipated', 'irregular bowel'],
    }
    
    # Herbs to track
    HERB_KEYWORDS = [
        'ginger', 'turmeric', 'peppermint', 'mint', 'garlic', 'honey', 'tulsi', 'basil',
        'ashwagandha', 'chamomile', 'cinnamon', 'clove', 'licorice', 'ginseng', 'valerian',
        'neem', 'amla', 'fennel', 'cumin', 'coriander', 'fenugreek', 'ajwain', 'cardamom',
        'lavender', 'eucalyptus', 'tea tree', 'aloe vera', 'aloe', 'coconut oil',
        'ginkgo', 'echinacea', 'elderberry', 'brahmi', 'giloy', 'triphala', 'moringa',
        'shatavari', 'black pepper', 'cayenne', 'oregano', 'thyme', 'rosemary',
    ]
    
    # Medications to track
    MEDICATION_KEYWORDS = {
        'aspirin': ['aspirin', 'disprin', 'ecosprin'],
        'ibuprofen': ['ibuprofen', 'advil', 'motrin', 'brufen'],
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
    
    def __init__(self):
        """Initialize the conversation manager"""
        self._memory_store: Dict[str, Dict] = {}
        self._active_sessions: Dict[str, str] = {}
        logger.info(f"ConversationManager initialized (cache={'enabled' if CACHE_AVAILABLE else 'disabled'})")
    
    # =========================================================================
    # CACHE HELPERS
    # =========================================================================
    
    def _get_cache_key(self, user_id: str, key_type: str) -> str:
        """Generate a cache key for user data, scoped to session if set."""
        # Hash email for privacy in cache keys
        user_hash = hashlib.md5(user_id.encode()).hexdigest()[:12]
        session = self._active_sessions.get(user_id, "")
        if session:
            return f"servvia_v2_{user_hash}_{session[:8]}_{key_type}"
        return f"servvia_v2_{user_hash}_{key_type}"

    def set_session(self, user_id: str, session_id: str):
        """Set the active session for a user. New session = fresh conversation."""
        current = self._active_sessions.get(user_id)
        if current != session_id:
            self._active_sessions[user_id] = session_id
            logger.info(f"New session for {user_id[:20]}...: {session_id[:8]}")
    
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
                logger.warning(f"Cache read failed: {e}")
        
        # Fall back to memory
        return self._memory_store.get(cache_key, {})
    
    def _set_data(self, user_id: str, key_type: str, data: Dict):
        """Set data in cache and memory"""
        cache_key = self._get_cache_key(user_id, key_type)
        
        # Always store in memory as backup
        self._memory_store[cache_key] = data
        
        # Try to store in cache
        if CACHE_AVAILABLE and cache:
            try:
                cache.set(cache_key, json.dumps(data), self. CACHE_TIMEOUT)
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
            'timestamp': datetime.now(). isoformat(),
            'metadata': metadata or {}
        }
        
        history['messages'].append(message)
        
        # Trim to max history
        if len(history['messages']) > self.MAX_HISTORY:
            history['messages'] = history['messages'][-self.MAX_HISTORY:]
        
        self._set_data(user_id, 'history', history)
        
        logger.info(f"Added {role} message for {user_id[:20]}... (total: {len(history['messages'])})")
    
    def get_history(self, user_id: str) -> List[Dict]:
        """Get conversation history for user"""
        history = self._get_data(user_id, 'history')
        return history.get('messages', [])
    
    def get_formatted_history(self, user_id: str, max_messages: int = 10) -> str:
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
        for i, msg in enumerate(recent):
            role = "User" if msg['role'] == 'user' else "ServVia"
            content = msg['content']

            # Keep the last 2 messages (most recent exchange) at higher detail
            # since the user is most likely responding to them
            is_recent = (i >= len(recent) - 2)
            max_len = 1200 if is_recent else 400

            if len(content) > max_len:
                # For assistant messages, keep the END (where questions/offers are)
                if msg['role'] == 'assistant' and is_recent:
                    content = "..." + content[-(max_len):]
                else:
                    content = content[:max_len] + "..."

            lines.append(f"{role}: {content}")

        return "\n".join(lines)
    
    # =========================================================================
    # CONTEXT MANAGEMENT
    # =========================================================================
    
    def get_context(self, user_id: str) -> Dict[str, List[str]]:
        """
        Get tracked context for user.
        
        Returns:
            Dict with 'conditions', 'herbs', 'medications' lists
        """
        context_data = self._get_data(user_id, 'context')
        
        return {
            'conditions': context_data. get('conditions', []),
            'herbs': context_data. get('herbs', []),
            'medications': context_data. get('medications', []),
        }
    
    def update_context(self, user_id: str, query: str) -> Dict[str, List[str]]:
        """
        Update context based on user query. 
        Handles both additions and removals. 
        
        Args:
            user_id: User identifier
            query: User's query text
        
        Returns:
            Dict with 'added' and 'removed' lists
        """
        query_lower = query. lower()
        
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
                            changes['removed'].append(f"medication: {med_name}")
                            logger.info(f"🔄 Removed medication: {med_name}")
                        break
            
            # Check if removing herbs
            for herb in self.HERB_KEYWORDS:
                if herb in query_lower:
                    if herb in context.get('herbs', []):
                        context['herbs'].remove(herb)
                        changes['removed'].append(f"herb: {herb}")
                        logger.info(f"🔄 Removed herb: {herb}")
        
        # =====================================================================
        # CHECK FOR ADDITIONS (only if not in removal context)
        # =====================================================================
        if not is_removal_context:
            # Add conditions
            for condition, keywords in self. CONDITION_KEYWORDS. items():
                for keyword in keywords:
                    if keyword in query_lower:
                        if condition not in context. get('conditions', []):
                            context. setdefault('conditions', []).append(condition)
                            changes['added'].append(f"condition: {condition}")
                            logger.info(f"➕ Added condition: {condition}")
                        break
            
            # Add herbs
            for herb in self.HERB_KEYWORDS:
                if herb in query_lower:
                    if herb not in context. get('herbs', []):
                        context.setdefault('herbs', []).append(herb)
                        changes['added']. append(f"herb: {herb}")
                        logger.info(f"➕ Added herb: {herb}")
            
            # Add medications
            is_addition_context = any(kw in query_lower for kw in self. ADDITION_KEYWORDS)
            
            for med_name, keywords in self.MEDICATION_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in query_lower:
                        # Only add if in addition context or medication directly mentioned
                        if is_addition_context or len(keyword) > 3:  # Avoid short matches
                            if med_name not in context.get('medications', []):
                                context.setdefault('medications', []). append(med_name)
                                changes['added'].append(f"medication: {med_name}")
                                logger.info(f"➕ Added medication: {med_name}")
                        break
        
        # Update timestamp
        context['last_updated'] = datetime.now(). isoformat()
        
        # Save context
        self._set_data(user_id, 'context', context)
        
        if changes['added'] or changes['removed']:
            logger.info(f"Context updated for {user_id[:20]}.. .: +{len(changes['added'])} -{len(changes['removed'])}")
        
        return changes
    
    def extract_temporal_entities(self, query: str) -> Dict[str, Optional[int]]:
        """
        Extract temporal information from query (days/weeks/months ago).
        Returns dict with 'days_ago' if found.
        """
        import re
        query_lower = query.lower()
        
        # Check for days
        match = re.search(self.TEMPORAL_KEYWORDS['days'], query_lower)
        if match:
            return {'days_ago': int(match.group(1)), 'unit': 'days'}
        
        # Check for weeks
        match = re.search(self.TEMPORAL_KEYWORDS['weeks'], query_lower)
        if match:
            return {'days_ago': int(match.group(1)) * 7, 'unit': 'weeks'}
        
        # Check for months
        match = re.search(self.TEMPORAL_KEYWORDS['months'], query_lower)
        if match:
            return {'days_ago': int(match.group(1)) * 30, 'unit': 'months'}
        
        # Check for yesterday
        if re.search(self.TEMPORAL_KEYWORDS['yesterday'], query_lower):
            return {'days_ago': 1, 'unit': 'days'}
        
        # Check for today
        if re.search(self.TEMPORAL_KEYWORDS['today'], query_lower):
            return {'days_ago': 0, 'unit': 'days'}
        
        # Check for last week
        if re.search(self.TEMPORAL_KEYWORDS['last_week'], query_lower):
            return {'days_ago': 7, 'unit': 'days'}
        
        # Check for recently/just started
        if re.search(self.TEMPORAL_KEYWORDS['recently'], query_lower):
            return {'days_ago': 3, 'unit': 'days', 'approximate': True}
        
        return {}
    
    def _sync_update_medication_timeline(self, user_id: str, query: str, 
                                         is_start_context: bool, is_stop_context: bool,
                                         temporal: Dict, query_lower: str) -> Dict:
        """
        SYNC helper for medication timeline DB operations.
        This function runs in a thread pool via sync_to_async.
        """
        from user_profile.models import UserProfile, MedicationHistory
        from django.utils import timezone
        
        result = {'created': [], 'updated': []}
        
        user = UserProfile.objects.get(email=user_id)
        
        if temporal and (is_start_context or is_stop_context):
            days_ago = temporal.get('days_ago', 0)
            event_date = timezone.now() - timedelta(days=days_ago)
            
            for med_name, keywords in self.MEDICATION_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in query_lower:
                        med_display_name = keyword.title()
                        
                        if is_start_context:
                            existing = MedicationHistory.objects.filter(
                                user=user,
                                medication_name__iexact=med_display_name,
                                status='active'
                            ).first()
                            
                            if not existing:
                                MedicationHistory.objects.create(
                                    user=user,
                                    medication_name=med_display_name,
                                    generic_name=med_name,
                                    dosage='unknown',
                                    frequency='unknown',
                                    start_date=event_date,
                                    status='active'
                                )
                                result['created'].append({
                                    'medication': med_display_name,
                                    'start_date': event_date.isoformat(),
                                    'days_ago': days_ago
                                })
                        
                        elif is_stop_context:
                            active_med = MedicationHistory.objects.filter(
                                user=user,
                                medication_name__iexact=med_display_name,
                                status='active'
                            ).first()
                            
                            if active_med:
                                active_med.status = 'discontinued'
                                active_med.stop_date = event_date
                                active_med.save()
                                result['updated'].append({
                                    'medication': med_display_name,
                                    'stop_date': event_date.isoformat(),
                                    'days_ago': days_ago
                                })
                        
                        break
        
        return result
    
    async def update_medication_timeline(self, user_id: str, query: str) -> Dict:
        """
        ASYNC wrapper: Update MedicationHistory based on temporal entities in query.
        Creates new records for 'started taking' medications.
        Updates stop_date for 'stopped' medications.
        """
        result = {'created': [], 'updated': []}
        
        try:
            from user_profile.models import UserProfile, MedicationHistory
            
            query_lower = query.lower()
            
            # Check if this is a START context
            is_start_context = any(kw in query_lower for kw in ['started taking', 'started', 'began', 'prescribed'])
            
            # Check if this is a STOP context
            is_stop_context = any(kw in query_lower for kw in self.REMOVAL_KEYWORDS)
            
            # Extract temporal info (this is non-blocking regex, can stay sync)
            temporal = self.extract_temporal_entities(query)
            
            if temporal and (is_start_context or is_stop_context):
                # Run DB operations in thread pool
                result = await sync_to_async(self._sync_update_medication_timeline)(
                    user_id, query, is_start_context, is_stop_context, temporal, query_lower
                )
                
                if result['created']:
                    for item in result['created']:
                        logger.info(f"� Created MedicationHistory: {item['medication']} started {item['days_ago']} days ago for {user_id[:20]}...")
                if result['updated']:
                    for item in result['updated']:
                        logger.info(f"🛑 Updated MedicationHistory: {item['medication']} stopped {item['days_ago']} days ago for {user_id[:20]}...")
        
        except UserProfile.DoesNotExist:
            logger.warning(f"User not found for medication timeline: {user_id}")
        except ImportError as e:
            logger.error(f"Cannot import models for medication timeline: {e}")
        except Exception as e:
            logger.error(f"Error updating medication timeline: {e}")
        
        return result
    
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
        
        logger.info(f"🗑️ Cleared conversation for {user_id[:20]}...")
    
    def get_context_summary(self, user_id: str) -> str:
        """Get a human-readable summary of tracked context"""
        ctx = self.get_context(user_id)
        
        parts = []
        
        if ctx['medications']:
            parts. append(f"Medications: {', '. join(ctx['medications'])}")
        
        if ctx['conditions']:
            parts. append(f"Discussing: {', '.join(ctx['conditions'])}")
        
        if ctx['herbs']:
            parts.append(f"Remedies mentioned: {', '.join(ctx['herbs'])}")
        
        return " | ".join(parts) if parts else "No context tracked yet"
    
    def is_follow_up_question(self, query: str, user_id: str) -> bool:
        """Detect if query is a follow-up to previous conversation"""
        query_lower = query. lower()
        
        # Follow-up indicators
        follow_up_words = [
            'what about', 'how about', 'and', 'also', 'too',
            'can i', 'should i', 'is it', 'will it', 'does it',
            'how long', 'how much', 'how often', 'how do',
            'what if', 'but', 'instead', 'alternatively',
            'tell me more', 'more about', 'explain',
            'the same', 'that', 'this', 'it',
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


# Create global instance
conversation_manager = ConversationManager()
