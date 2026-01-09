"""
Smart Indian Language Corrector for Medical Speech
Uses phonetic matching + LLM correction for misheard phrases

Current Date: 2025-12-30
"""
import re
import logging
from difflib import SequenceMatcher
from typing import Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)

# =============================================================================
# CANONICAL MEDICAL PHRASES FOR ALL INDIAN LANGUAGES
# Format: {language_code: {canonical_phrase: english_translation}}
# =============================================================================

MEDICAL_PHRASES = {
    'kn': {
        # Kannada phrases
        "nanige jwara ide": "I have fever",
        "nanige kemmu ide": "I have cough",
        "nanige thalenovu ide": "I have headache",
        "nanige hotte novu ide": "I have stomach pain",
        "nanige gantalu novu ide": "I have sore throat",
        "nanige vaanthi aagthide": "I am vomiting",
        "nanige sheethaagide": "I have cold",
        "nanige bedi aagthide": "I have diarrhea",
        "nanige maisullu novu ide": "I have body pain",
        "nanige shakti illa":  "I feel weak",
        "nanige nidde bartilla": "I cannot sleep",
        "nanige usiraata taklif ide": "I have breathing problem",
        "nanige ene novu ide": "I have chest pain",
        "nanige bellu novu ide": "I have back pain",
        "nanige keel novu ide": "I have joint pain",
        "nanige charma samasye ide": "I have skin problem",
        "nanige allergy ide": "I have allergy",
        "jwara ide": "I have fever",
        "kemmu ide": "I have cough",
        "thalenovu ide": "I have headache",
        "hotte novu":  "stomach pain",
        "gantalu novu": "sore throat",
    },
    'hi': {
        # Hindi phrases
        "mujhe bukhar hai": "I have fever",
        "mujhe khansi hai": "I have cough",
        "mujhe sir dard hai": "I have headache",
        "mujhe pet dard hai": "I have stomach pain",
        "mujhe gala dard hai": "I have sore throat",
        "mujhe ulti ho rahi hai": "I am vomiting",
        "mujhe sardi hai": "I have cold",
        "mujhe dast hai": "I have diarrhea",
        "mujhe badan dard hai": "I have body pain",
        "mujhe kamzori hai": "I feel weak",
        "mujhe neend nahi aati": "I cannot sleep",
        "mujhe sans lene mein taklif hai": "I have breathing problem",
        "mujhe seene mein dard hai": "I have chest pain",
        "mujhe kamar dard hai": "I have back pain",
        "mujhe jodon mein dard hai": "I have joint pain",
        "bukhar hai": "I have fever",
        "khansi hai":  "I have cough",
        "sir dard hai": "I have headache",
        "pet dard hai": "stomach pain",
        "gala dard hai": "sore throat",
    },
    'ta': {
        # Tamil phrases
        "enakku kaichal irukku": "I have fever",
        "enakku irumal irukku": "I have cough",
        "enakku thalai vali irukku": "I have headache",
        "enakku vayiru vali irukku": "I have stomach pain",
        "enakku thondai vali irukku": "I have sore throat",
        "enakku vaanthi varuthu":  "I am vomiting",
        "enakku jalam irukku": "I have cold",
        "enakku vayitru pokku": "I have diarrhea",
        "enakku udambu vali":  "I have body pain",
        "enakku saavu irukku": "I feel weak",
        "kaichal irukku": "I have fever",
        "irumal irukku": "I have cough",
        "thalai vali":  "headache",
        "vayiru vali": "stomach pain",
    },
    'te': {
        # Telugu phrases
        "naaku jwaram undi": "I have fever",
        "naaku dabbhu undi": "I have cough",
        "naaku tala noppi undi": "I have headache",
        "naaku kadupu noppi undi": "I have stomach pain",
        "naaku gonthu noppi undi": "I have sore throat",
        "naaku vamthulu vastunnai":  "I am vomiting",
        "naaku jalabu chesindi": "I have cold",
        "naaku virechanaalu":  "I have diarrhea",
        "naaku oththi noppi":  "I have body pain",
        "naaku balagam ledu": "I feel weak",
        "jwaram undi": "I have fever",
        "dabbhu undi": "I have cough",
        "tala noppi": "headache",
        "kadupu noppi": "stomach pain",
    },
    'ml': {
        # Malayalam phrases
        "enikku pani und": "I have fever",
        "enikku chuma und": "I have cough",
        "enikku thala vedana und": "I have headache",
        "enikku vayaru vedana und": "I have stomach pain",
        "enikku thonda vedana und": "I have sore throat",
        "enikku okkanam varunnu": "I am vomiting",
        "enikku jaladhosham und": "I have cold",
        "enikku vayaru ilakunnu": "I have diarrhea",
        "enikku udal vedana":  "I have body pain",
        "enikku ksheenam":  "I feel weak",
        "pani und": "I have fever",
        "chuma und":  "I have cough",
        "thala vedana": "headache",
        "vayaru vedana": "stomach pain",
    },
    'mr': {
        # Marathi phrases
        "mala taap aahey": "I have fever",
        "mala khokhla aahey": "I have cough",
        "mala dokey dukhte":  "I have headache",
        "mala pot dukhte": "I have stomach pain",
        "mala ghasa dukhto": "I have sore throat",
        "mala ulti hote": "I am vomiting",
        "mala sardi zali": "I have cold",
        "mala jullab aahey": "I have diarrhea",
        "mala ang dukhte": "I have body pain",
        "mala kamzori vatey": "I feel weak",
        "taap aahey": "I have fever",
        "khokhla aahey": "I have cough",
        "dokey dukhte": "headache",
        "pot dukhte": "stomach pain",
    },
    'bn': {
        # Bengali phrases
        "amar jor hoyeche": "I have fever",
        "amar kashi hoyeche": "I have cough",
        "amar matha byatha":  "I have headache",
        "amar pet byatha": "I have stomach pain",
        "amar gola byatha": "I have sore throat",
        "amar bomi hocche": "I am vomiting",
        "amar thanda legechhe": "I have cold",
        "amar diarrhea hoyeche": "I have diarrhea",
        "amar gaye byatha": "I have body pain",
        "amar durbolota":  "I feel weak",
        "jor hoyeche": "I have fever",
        "kashi hoyeche": "I have cough",
        "matha byatha": "headache",
        "pet byatha": "stomach pain",
    },
    'gu': {
        # Gujarati phrases
        "mane taav che": "I have fever",
        "mane khansi che": "I have cough",
        "mane mathanu dard che": "I have headache",
        "mane petma dard che": "I have stomach pain",
        "mane gala ma dard che": "I have sore throat",
        "mane ulti thay che": "I am vomiting",
        "mane shardi che": "I have cold",
        "mane julab che": "I have diarrhea",
        "mane ange dard che": "I have body pain",
        "mane nablai che": "I feel weak",
        "taav che": "I have fever",
        "khansi che":  "I have cough",
        "mathanu dard":  "headache",
        "petma dard": "stomach pain",
    },
    'pa': {
        # Punjabi phrases
        "mainu bukhar hai": "I have fever",
        "mainu khansi hai":  "I have cough",
        "mainu sir dard hai":  "I have headache",
        "mainu pait dard hai": "I have stomach pain",
        "mainu gala dard hai": "I have sore throat",
        "mainu ulti aundi hai": "I am vomiting",
        "mainu zukam hai": "I have cold",
        "mainu dast lagge ne": "I have diarrhea",
        "mainu jism dard hai": "I have body pain",
        "mainu kamzori hai": "I feel weak",
        "bukhar hai": "I have fever",
        "khansi hai":  "I have cough",
        "sir dard":  "headache",
        "pait dard": "stomach pain",
    },
    'en': {
        # English phrases (for completeness)
        "i have fever": "I have fever",
        "i have cough":  "I have cough",
        "i have headache": "I have headache",
        "i have stomach pain": "I have stomach pain",
        "i have sore throat": "I have sore throat",
        "i am vomiting": "I am vomiting",
        "i have cold": "I have cold",
        "i have diarrhea":  "I have diarrhea",
        "i have body pain":  "I have body pain",
        "i feel weak": "I feel weak",
    }
}


# =============================================================================
# PHONETIC NORMALIZATION RULES
# Handles common sound substitutions across Indian languages
# =============================================================================

def phonetic_normalize(text: str) -> str:
    """
    Normalize text for phonetic comparison. 
    Handles common ASR mistakes and sound variations.
    """
    if not text:
        return ""
    
    text = text.lower().strip()
    
    # Common phonetic substitutions (order matters!)
    substitutions = [
        # Remove common filler words/sounds
        (r'\b(um|uh|ah|eh|oh)\b', ''),
        
        # Vowel variations
        (r'ee+', 'i'),
        (r'oo+', 'u'),
        (r'aa+', 'a'),
        (r'ii+', 'i'),
        (r'uu+', 'u'),
        
        # Consonant variations (aspirated -> non-aspirated)
        (r'th', 't'),
        (r'dh', 'd'),
        (r'bh', 'b'),
        (r'ph', 'p'),
        (r'kh', 'k'),
        (r'gh', 'g'),
        (r'ch', 'c'),
        (r'jh', 'j'),
        (r'sh', 's'),
        
        # Common sound confusions
        (r'v', 'w'),
        (r'z', 's'),
        (r'q', 'k'),
        (r'x', 'ks'),
        
        # Hindi/Urdu endings often misheard
        (r'\bidhar\b', 'ide'),
        (r'\bhai\b', 'ide'),
        (r'\bhain\b', 'ide'),
        (r'\bnahi\b', 'illa'),
        (r'\bnai\b', 'illa'),
        
        # Common Kannada mishearings
        (r'\bke\b', 'ge'),
        (r'\bka\b', 'ge'),
        (r'\bki\b', 'ge'),
        (r'\bnani\b', 'nanige'),
        (r'\bnandale\b', 'nanige'),
        (r'\bnundle\b', 'nanige'),
        
        # Animal/random word substitutions (common ASR errors)
        (r'\btiger\b', 'thalenovu'),
        (r'\blion\b', 'novu'),
        (r'\bno\b', 'novu'),
        (r'\btale\b', 'thale'),
        (r'\bnuvvida\b', 'novu ide'),
        (r'\bvida\b', 'ide'),
        
        # Common word boundaries
        (r'novuide', 'novu ide'),
        (r'jwaraid', 'jwara ide'),
        (r'kemmuide', 'kemmu ide'),
        
        # Clean up multiple spaces
        (r'\s+', ' '),
    ]
    
    for pattern, replacement in substitutions: 
        text = re.sub(pattern, replacement, text)
    
    return text. strip()


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two strings"""
    if not text1 or not text2:
        return 0.0
    return SequenceMatcher(None, text1, text2).ratio()


def calculate_word_overlap(text1: str, text2: str) -> float:
    """Calculate word overlap between two strings"""
    words1 = set(text1.split())
    words2 = set(text2.split())
    
    if not words1 or not words2:
        return 0.0
    
    overlap = len(words1 & words2)
    return overlap / max(len(words1), len(words2))


# =============================================================================
# MAIN CORRECTION FUNCTIONS
# =============================================================================

def find_best_match(
    transcription: str,
    language: str,
    threshold: float = 0.40
) -> Tuple[Optional[str], Optional[str], float]:
    """
    Find the best matching medical phrase using phonetic similarity.
    
    Args:
        transcription:  The misheard transcription
        language: Language code (kn, hi, ta, te, ml, mr, bn, gu, pa, en)
        threshold: Minimum similarity threshold
        
    Returns:
        Tuple of (matched_phrase, english_translation, confidence)
    """
    # Get phrases for the language
    lang_code = language.lower().split('-')[0]
    phrases = MEDICAL_PHRASES. get(lang_code, {})
    
    if not phrases:
        # Try all languages if specific language not found
        for code, lang_phrases in MEDICAL_PHRASES.items():
            phrases. update(lang_phrases)
    
    # Normalize input
    normalized_input = phonetic_normalize(transcription)
    
    best_match = None
    best_translation = None
    best_score = 0.0
    
    for phrase, translation in phrases.items():
        normalized_phrase = phonetic_normalize(phrase)
        
        # Calculate multiple similarity metrics
        char_similarity = calculate_similarity(normalized_input, normalized_phrase)
        word_overlap = calculate_word_overlap(normalized_input, normalized_phrase)
        
        # Also check original (non-normalized) similarity
        original_similarity = calculate_similarity(transcription. lower(), phrase.lower())
        
        # Combined score with weights
        combined_score = (
            char_similarity * 0.4 +
            word_overlap * 0.3 +
            original_similarity * 0.3
        )
        
        # Boost score if key medical words are found
        medical_keywords = ['novu', 'jwara', 'kemmu', 'thale', 'hotte', 'dard', 'bukhar', 
                          'khansi', 'kaichal', 'vali', 'vedana', 'pani', 'taap']
        for keyword in medical_keywords:
            if keyword in normalized_input and keyword in normalized_phrase:
                combined_score += 0.15
                break
        
        if combined_score > best_score: 
            best_score = combined_score
            best_match = phrase
            best_translation = translation
    
    if best_score >= threshold:
        return best_match, best_translation, min(best_score, 0.99)
    
    return None, None, 0.0


def correct_transcription(
    transcription: str,
    language: str,
    use_llm_fallback: bool = True
) -> Dict: 
    """
    Correct a misheard transcription using phonetic matching.
    
    Args:
        transcription: The raw transcription from ASR
        language: Language code
        use_llm_fallback: Whether to use LLM for correction if phonetic fails
        
    Returns: 
        Dict with correction results
    """
    if not transcription: 
        return {
            'success': False,
            'original': transcription,
            'corrected': transcription,
            'english': None,
            'confidence':  0,
            'method': 'none'
        }
    
    logger.info(f"🔧 Attempting correction for:  '{transcription}' (lang: {language})")
    
    # Step 1: Try phonetic matching
    matched, english, confidence = find_best_match(transcription, language, threshold=0.35)
    
    if matched:
        logger.info(f"✅ Phonetic match found: '{matched}' -> '{english}' (confidence: {confidence:.2%})")
        return {
            'success': True,
            'original': transcription,
            'corrected': matched,
            'english': english,
            'confidence': confidence,
            'method': 'phonetic'
        }
    
    # Step 2: Try with more aggressive normalization
    aggressive_input = phonetic_normalize(transcription)
    matched, english, confidence = find_best_match(aggressive_input, language, threshold=0.30)
    
    if matched: 
        logger.info(f"✅ Aggressive phonetic match:  '{matched}' -> '{english}' (confidence: {confidence:.2%})")
        return {
            'success': True,
            'original': transcription,
            'corrected': matched,
            'english': english,
            'confidence': confidence,
            'method': 'phonetic_aggressive'
        }
    
    # Step 3: LLM fallback (if enabled)
    if use_llm_fallback:
        llm_result = correct_with_llm(transcription, language)
        if llm_result and llm_result. get('success'):
            return llm_result
    
    # No correction found
    logger.warning(f"⚠️ No correction found for:  '{transcription}'")
    return {
        'success': False,
        'original': transcription,
        'corrected': transcription,
        'english': None,
        'confidence': 0,
        'method': 'none'
    }


def correct_with_llm(transcription: str, language: str) -> Optional[Dict]:
    """
    Use LLM to correct misheard medical transcription.
    This is a fallback when phonetic matching fails.
    """
    try:
        from openai import OpenAI
        from django.conf import settings
        import json
        
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Language names for prompt
        lang_names = {
            'kn': 'Kannada', 'hi': 'Hindi', 'ta': 'Tamil', 'te': 'Telugu',
            'ml': 'Malayalam', 'mr': 'Marathi', 'bn': 'Bengali', 'gu':  'Gujarati',
            'pa': 'Punjabi', 'en': 'English'
        }
        lang_name = lang_names.get(language.split('-')[0], 'Indian')
        
        response = client.chat.completions. create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are an expert in {lang_name} medical speech recognition correction. 

Given a mistranscribed {lang_name} medical phrase, identify what the user likely said. 

Common {lang_name} medical phrases include symptoms like:
- Fever, cough, headache, stomach pain, sore throat
- Vomiting, cold, diarrhea, body pain, weakness

Output ONLY valid JSON:  {{"corrected":  "correct phrase in romanized {lang_name}", "english": "English translation", "confidence": 0.0-1.0}}

If you cannot determine the phrase, return: {{"corrected": null, "english": null, "confidence": 0}}"""
                },
                {
                    "role": "user",
                    "content": f"Correct this mistranscribed {lang_name} medical phrase: '{transcription}'"
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=150
        )
        
        result = json.loads(response.choices[0].message.content)
        
        if result.get('corrected'):
            logger.info(f"✅ LLM correction:  '{result['corrected']}' -> '{result. get('english')}' "
                       f"(confidence:  {result.get('confidence', 0.7):.2%})")
            return {
                'success': True,
                'original': transcription,
                'corrected': result['corrected'],
                'english':  result.get('english'),
                'confidence': result.get('confidence', 0.7),
                'method': 'llm'
            }
        
    except Exception as e:
        logger.warning(f"LLM correction failed:  {e}")
    
    return None


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def smart_correct(transcription: str, language: str = 'kn') -> Dict:
    """
    Main entry point for smart correction.
    
    Args:
        transcription:  Raw ASR transcription
        language: Language code
        
    Returns:
        Dict with corrected text and metadata
    """
    return correct_transcription(transcription, language, use_llm_fallback=True)