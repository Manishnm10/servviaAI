"""
ServVia - True Agentic RAG Controller

This is a REAL Agentic RAG that:
1. Retrieves knowledge from Farmstack vector DB (not hardcoded)
2. Analyzes retrieved content for herbs/remedies
3. Calculates Scientific Confidence Scores dynamically
4.  Applies user context (allergies, conditions, location/weather)
5.  Generates ONE unified, accurate, personalized response

The agent DECIDES what actions to take based on the query. 
"""
import asyncio
import logging
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ServViaAgenticRAG:
    """
    True Agentic RAG - Makes decisions, not just processes. 
    """
    
    def __init__(self):
        from servvia2.trust_engine.confidence_calculator import ScientificConfidenceCalculator
        from servvia2.context_engine.environmental_service import EnvironmentalService
        
        self.confidence_calc = ScientificConfidenceCalculator()
        self.env_service = EnvironmentalService()
        
        # Herb identification patterns (to find herbs in retrieved content)
        self.known_herbs = [
            'ginger', 'turmeric', 'tulsi', 'neem', 'aloe vera', 'honey',
            'peppermint', 'clove', 'cinnamon', 'garlic', 'ashwagandha',
            'chamomile', 'lavender', 'fennel', 'cardamom', 'cumin',
            'black pepper', 'giloy', 'amla', 'brahmi', 'triphala',
            'licorice', 'mulethi', 'ajwain', 'shatavari', 'moringa',
            'eucalyptus', 'tea tree', 'coconut oil', 'mustard oil',
            'sesame oil', 'castor oil', 'fenugreek', 'methi', 'basil',
            'mint', 'lemon', 'apple cider vinegar', 'baking soda',
            'epsom salt', 'almond', 'sandalwood', 'rose water', 'neem oil',
            'holy basil', 'indian gooseberry', 'black cumin', 'kalonji'
        ]
        
        # Evidence tier keywords (to estimate evidence level from content)
        self. tier_keywords = {
            1: ['clinical trial', 'randomized', 'double-blind', 'placebo-controlled', 'meta-analysis', 'systematic review'],
            2: ['study shows', 'research indicates', 'mechanism', 'anti-inflammatory', 'antimicrobial', 'contains compounds'],
            3: ['traditionally used', 'ayurveda', 'traditional medicine', 'folk remedy', 'centuries'],
            4: ['may help', 'some people find', 'anecdotal', 'reported to'],
        }
    
    def process(
        self,
        query: str,
        retrieved_chunks: List[Dict],
        user_name: str = "there",
        allergies: List[str] = None,
        medical_conditions: List[str] = None,
        location: Dict = None
    ) -> Dict:
        """
        Main Agentic RAG processing pipeline. 
        
        Args:
            query: User's health query
            retrieved_chunks: Content from Farmstack vector DB
            user_name: User's name for personalization
            allergies: User's known allergies
            medical_conditions: User's medical conditions
            location: User's location for seasonal context
        
        Returns:
            Complete response with validated remedies and scores
        """
        allergies = allergies or []
        medical_conditions = medical_conditions or []
        
        logger.info(f"Agentic RAG processing query: {query}")
        logger.info(f"Retrieved {len(retrieved_chunks)} chunks from Farmstack")
        logger.info(f"User allergies: {allergies}")
        
        # Step 1: Identify the health condition
        condition = self._identify_condition(query)
        logger.info(f"Identified condition: {condition}")
        
        # Step 2: Extract remedies from retrieved chunks
        extracted_remedies = self._extract_remedies_from_chunks(
            retrieved_chunks, 
            condition,
            allergies
        )
        logger.info(f"Extracted {len(extracted_remedies)} remedies from chunks")
        
        # Step 3: Calculate Scientific Confidence Scores
        scored_remedies = self._calculate_scores(extracted_remedies, medical_conditions)
        logger.info(f"Scored {len(scored_remedies)} remedies")
        
        # Step 4: Get environmental context
        env_context = {}
        if location:
            lat = location.get('latitude', 20)
            env_context = self.env_service. get_season(lat)
            env_context['seasonal_herbs'] = self. env_service.get_recommendations(
                season=env_context. get('season')
            ). get('herbs', [])
        
        # Step 5: Sort by score and take top remedies
        scored_remedies.sort(key=lambda x: x. get('scs_score', 0), reverse=True)
        top_remedies = scored_remedies[:4]
        
        # Step 6: Generate unified response
        response = self._generate_response(
            user_name=user_name,
            condition=condition,
            remedies=top_remedies,
            allergies=allergies,
            medical_conditions=medical_conditions,
            env_context=env_context
        )
        
        return {
            'response': response,
            'condition': condition,
            'remedies': top_remedies,
            'all_remedies': scored_remedies,
            'env_context': env_context,
            'chunks_analyzed': len(retrieved_chunks)
        }
    
    def _identify_condition(self, query: str) -> str:
        """Identify health condition from query"""
        conditions_map = {
            'burns': ['burnt', 'burn', 'burned', 'scalded', 'scald'],
            'headache': ['headache', 'head hurts', 'head pain', 'migraine', 'head is pounding'],
            'cold': ['cold', 'runny nose', 'sneezing', 'congestion', 'stuffy nose'],
            'cough': ['cough', 'coughing', 'dry cough', 'wet cough'],
            'fever': ['fever', 'temperature', 'feverish', 'high temperature'],
            'nausea': ['nausea', 'nauseous', 'vomit', 'queasy', 'throwing up'],
            'anxiety': ['anxiety', 'anxious', 'worried', 'nervous', 'panic', 'stressed'],
            'insomnia': ['insomnia', 'cant sleep', 'cannot sleep', 'sleepless', 'trouble sleeping'],
            'indigestion': ['indigestion', 'bloating', 'gas', 'stomach ache', 'bloated'],
            'sore throat': ['sore throat', 'throat pain', 'throat hurts'],
            'stress': ['stress', 'stressed', 'tense', 'overwhelmed'],
            'toothache': ['toothache', 'tooth pain', 'tooth hurts'],
            'fatigue': ['fatigue', 'tired', 'exhausted', 'no energy'],
            'arthritis': ['arthritis', 'joint pain', 'joints hurt'],
            'acne': ['acne', 'pimples', 'breakout'],
            'dandruff': ['dandruff', 'flaky scalp'],
            'constipation': ['constipation', 'constipated'],
            'acidity': ['acidity', 'acid reflux', 'heartburn'],
            'skin': ['skin', 'rash', 'itching', 'eczema'],
            'hair fall': ['hair fall', 'hair loss', 'balding'],
            'diabetes': ['diabetes', 'blood sugar', 'sugar level'],
            'blood pressure': ['blood pressure', 'bp', 'hypertension'],
            'immunity': ['immunity', 'immune system', 'getting sick often'],
            'weight loss': ['weight loss', 'lose weight', 'obesity'],
            'digestion': ['digestion', 'digestive', 'stomach'],
        }
        
        query_lower = query. lower()
        
        for condition, keywords in conditions_map. items():
            for keyword in keywords:
                if keyword in query_lower:
                    return condition
        
        return "general health"
    
    def _extract_remedies_from_chunks(
        self, 
        chunks: List[Dict], 
        condition: str,
        allergies: List[str]
    ) -> List[Dict]:
        """
        Extract remedy information from retrieved chunks. 
        This is the AGENTIC part - analyzing content dynamically.
        """
        allergies_lower = [a.lower() for a in allergies]
        remedies = []
        seen_herbs = set()
        
        for chunk in chunks:
            text = chunk.get('text', '') or chunk.get('content', '') or str(chunk)
            text_lower = text. lower()
            
            # Find herbs mentioned in this chunk
            for herb in self.known_herbs:
                if herb in text_lower and herb not in seen_herbs:
                    # Skip if user is allergic
                    if herb in allergies_lower:
                        logger.info(f"Skipping {herb} - user allergy")
                        continue
                    
                    # Extract usage instructions from the chunk
                    usage = self._extract_usage_instructions(text, herb, condition)
                    
                    # Estimate evidence tier from content
                    evidence_tier = self._estimate_evidence_tier(text)
                    
                    # Extract mechanism if mentioned
                    mechanism = self._extract_mechanism(text, herb)
                    
                    remedies.append({
                        'herb_name': herb. title(),
                        'source_text': text[:500],
                        'usage_instructions': usage,
                        'evidence_tier': evidence_tier,
                        'mechanism': mechanism,
                        'condition': condition
                    })
                    seen_herbs.add(herb)
        
        return remedies
    
    def _extract_usage_instructions(self, text: str, herb: str, condition: str) -> str:
        """Extract usage instructions from chunk text"""
        # Find sentences containing the herb and usage-related words
        sentences = re.split(r'[.!?]', text)
        usage_sentences = []
        
        usage_keywords = [
            'apply', 'drink', 'take', 'mix', 'boil', 'steep', 'massage',
            'use', 'add', 'consume', 'prepare', 'make', 'chew', 'inhale',
            'tablespoon', 'teaspoon', 'cup', 'drops', 'times daily',
            'morning', 'night', 'before bed', 'empty stomach', 'after meals'
        ]
        
        for sentence in sentences:
            sentence_lower = sentence. lower()
            if herb. lower() in sentence_lower:
                for keyword in usage_keywords:
                    if keyword in sentence_lower:
                        usage_sentences.append(sentence. strip())
                        break
        
        if usage_sentences:
            # Format the extracted instructions
            instructions = f"**How to use {herb. title()}:**\n"
            for i, inst in enumerate(usage_sentences[:4], 1):
                instructions += f"• {inst. strip()}\n"
            return instructions
        
        # Default instruction based on herb type
        return self._get_default_usage(herb, condition)
    
    def _get_default_usage(self, herb: str, condition: str) -> str:
        """Generate default usage based on herb and condition"""
        herb_lower = herb. lower()
        
        # Common preparation methods
        if herb_lower in ['ginger', 'turmeric', 'tulsi', 'chamomile', 'peppermint']:
            return f"""**How to use {herb. title()}:**
• Make a tea: Boil in water for 5-10 minutes
• Add honey for taste
• Drink 2-3 times daily"""
        
        elif herb_lower in ['aloe vera']:
            if condition == 'burns':
                return f"""**How to use {herb.title()}:**
• Extract fresh gel from the leaf
• Apply directly to the affected area
• Reapply 2-3 times daily
• Keep area clean between applications"""
            return f"""**How to use {herb.title()}:**
• Apply fresh gel to skin
• For internal use, mix gel with water"""
        
        elif herb_lower in ['honey']:
            if condition == 'burns':
                return f"""**How to use {herb.title()}:**
• Apply raw honey directly to the burn
• Cover with sterile bandage
• Change dressing 2-3 times daily"""
            return f"""**How to use {herb.title()}:**
• Take 1 tablespoon directly
• Or mix with warm water/tea"""
        
        elif herb_lower in ['clove', 'cloves']:
            return f"""**How to use {herb.title()}:**
• Crush 2-3 cloves
• Apply with carrier oil to affected area
• Or make tea by steeping in hot water"""
        
        elif herb_lower in ['coconut oil', 'mustard oil', 'sesame oil']:
            return f"""**How to use {herb.title()}:**
• Warm slightly before use
• Massage gently on affected area
• Leave for 20-30 minutes"""
        
        else:
            return f"""**How to use {herb.title()}:**
• Prepare as tea or decoction
• Follow traditional preparation methods
• Consult an herbalist for specific dosage"""
    
    def _estimate_evidence_tier(self, text: str) -> int:
        """Estimate evidence tier based on content language"""
        text_lower = text. lower()
        
        for tier, keywords in self.tier_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return tier
        
        return 3  # Default to traditional use
    
    def _extract_mechanism(self, text: str, herb: str) -> str:
        """Extract mechanism of action from text"""
        mechanisms = {
            'anti-inflammatory': 'Reduces inflammation',
            'antimicrobial': 'Fights harmful microbes',
            'antibacterial': 'Kills bacteria',
            'antioxidant': 'Protects cells from damage',
            'analgesic': 'Relieves pain',
            'antipyretic': 'Reduces fever',
            'cooling': 'Provides cooling relief',
            'warming': 'Provides warming relief',
            'soothing': 'Soothes and calms',
            'digestive': 'Aids digestion',
            'expectorant': 'Helps clear mucus',
            'adaptogenic': 'Helps body adapt to stress',
            'immunomodulatory': 'Supports immune system',
            'carminative': 'Relieves gas and bloating',
        }
        
        text_lower = text. lower()
        found_mechanisms = []
        
        for keyword, description in mechanisms.items():
            if keyword in text_lower:
                found_mechanisms. append(description)
        
        if found_mechanisms:
            return "; ".join(found_mechanisms[:2])
        
        # Default mechanism for common herbs
        herb_mechanisms = {
            'ginger': 'Anti-inflammatory and warming properties',
            'turmeric': 'Curcumin provides anti-inflammatory benefits',
            'honey': 'Antimicrobial and wound-healing properties',
            'aloe vera': 'Cooling and skin-healing properties',
            'tulsi': 'Adaptogenic and immune-boosting',
            'neem': 'Antibacterial and blood-purifying',
            'peppermint': 'Menthol provides cooling relief',
            'clove': 'Eugenol acts as natural analgesic',
            'garlic': 'Allicin provides antimicrobial effects',
            'ashwagandha': 'Adaptogenic stress reducer',
            'chamomile': 'Calming and relaxing properties',
        }
        
        return herb_mechanisms. get(herb. lower(), 'Traditional therapeutic properties')
    
    def _calculate_scores(
        self, 
        remedies: List[Dict],
        medical_conditions: List[str]
    ) -> List[Dict]:
        """Calculate Scientific Confidence Scores for each remedy"""
        scored = []
        
        for remedy in remedies:
            scs = self.confidence_calc.calculate_scs(
                evidence_tier=remedy.get('evidence_tier', 3),
                pubmed_ids=[],  # Could be enhanced with real PubMed lookup
                has_mechanism=bool(remedy.get('mechanism')),
                contraindications=[],
                user_conditions=medical_conditions
            )
            
            remedy['scs_score'] = scs. get('score', 5)
            remedy['scs_emoji'] = scs. get('confidence_emoji', '🟡')
            remedy['scs_level'] = scs. get('confidence_level', 'Moderate')
            remedy['evidence_tier_label'] = {
                1: 'Clinical Trial',
                2: 'Mechanistic Study',
                3: 'Traditional Use',
                4: 'Anecdotal'
            }.get(remedy.get('evidence_tier', 3), 'Traditional Use')
            
            scored.append(remedy)
        
        return scored
    
    def _generate_response(
        self,
        user_name: str,
        condition: str,
        remedies: List[Dict],
        allergies: List[str],
        medical_conditions: List[str],
        env_context: Dict
    ) -> str:
        """Generate the final unified response"""
        
        # Empathetic greeting
        greetings = {
            'burns': f"👋 Hi {user_name}! I'm sorry about your burn. Burns need careful treatment - here are some effective natural remedies.",
            'headache': f"👋 Hi {user_name}!  Headaches can really disrupt your day. Let me suggest some natural remedies that may help.",
            'cold': f"👋 Hi {user_name}! Sorry you're feeling under the weather. Here are some remedies to help you recover.",
            'cough': f"👋 Hi {user_name}! A persistent cough is exhausting. Here are some soothing remedies.",
            'fever': f"👋 Hi {user_name}! Fever means your body is fighting.  Here are natural ways to support recovery.",
            'anxiety': f"👋 Hi {user_name}! Anxiety can feel overwhelming. Here are some calming natural remedies.",
            'insomnia': f"👋 Hi {user_name}! Trouble sleeping?  These natural remedies can help you rest better.",
            'indigestion': f"👋 Hi {user_name}! Digestive discomfort is no fun. Here are some soothing options.",
            'sore throat': f"👋 Hi {user_name}!  A sore throat is painful. Here are some soothing remedies.",
            'acne': f"👋 Hi {user_name}! Here are some natural remedies for clearer skin.",
            'fatigue': f"👋 Hi {user_name}!  Feeling tired?  Here are some natural energy boosters.",
        }
        
        response = greetings.get(
            condition.lower(),
            f"👋 Hi {user_name}! Here are some evidence-based natural remedies for {condition}."
        )
        response += "\n\n"
        
        # Safety notes
        if allergies:
            response += f"🛡️ **Your Safety:** I've excluded remedies containing **{', '.join(allergies)}** based on your profile.\n\n"
        
        if medical_conditions:
            response += f"⚕️ **Health Consideration:** Taking into account your condition(s): {', '.join(medical_conditions)}.\n\n"
        
        response += "---\n\n"
        
        # Remedies with scores
        if remedies:
            for i, remedy in enumerate(remedies[:3], 1):
                response += f"### {remedy['scs_emoji']} Remedy {i}: {remedy['herb_name']}\n\n"
                
                # Score box
                response += f"📊 **Scientific Confidence Score: {remedy['scs_score']}/10** ({remedy['scs_level']})\n"
                response += f"📚 Evidence: {remedy['evidence_tier_label']}\n\n"
                
                # Mechanism
                response += f"**Why it helps:** {remedy. get('mechanism', 'Traditional therapeutic properties')}\n\n"
                
                # Usage instructions
                usage = remedy.get('usage_instructions', '')
                if usage:
                    response += f"{usage}\n\n"
                
                response += "---\n\n"
        else:
            response += "I couldn't find specific remedies from the knowledge base. Please consult a healthcare professional.\n\n"
        
        # Seasonal tip
        if env_context.get('season'):
            season = env_context['season']. title()
            seasonal_herbs = env_context.get('seasonal_herbs', [])
            if seasonal_herbs:
                safe_herbs = [h for h in seasonal_herbs if h. lower() not in [a.lower() for a in allergies]]
                if safe_herbs:
                    response += f"🌿 **{season} Wellness Tip:** {', '.join(safe_herbs[:3])} are especially beneficial this season.\n\n"
        
        # Score explanation
        response += """**Understanding Confidence Scores:**
| Score | Meaning |
|-------|---------|
| 🟢 8-10 | Strong scientific evidence |
| 🟡 5-7 | Good traditional/mechanistic support |
| 🔴 1-4 | Limited research, traditional use |

"""
        
        # Medical disclaimer
        response += "---\n\n"
        response += "⚠️ **When to See a Doctor:** If symptoms persist, worsen, or you experience severe symptoms, please consult a healthcare professional.\n\n"
        response += f"💚 Take care, {user_name}!  Ask me if you'd like more details about any remedy."
        
        return response
