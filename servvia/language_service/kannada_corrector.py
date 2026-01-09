"""
Kannada Speech Recognition Post-Processor
Fixes common STT errors for Kannada medical phrases
"""
from difflib import SequenceMatcher
import re

# Common Kannada medical phrases and their STT mistakes
# Format: "correct_phrase":  ["common_mistake1", "common_mistake2", ...]
KANNADA_MEDICAL_CORRECTIONS = {
    # ===== FEVER =====
    "nanige jwara ide": [
        "ke dwara idhar", "nani ge jwara ide", "na nige jwara ide", "ke jvara ide",
        "aniket movie", "money get water", "nani gay water", "ke water idea",
        "money ke bara", "nanika jawara", "nanige jawara", "nanige jvara",
        "nani ge jwara", "money get jwara", "ani get jwara ide"
    ],
    "jwara ide": [
        "jvara ide", "jwara hai", "jvar ide", "fever ide", "water ide",
        "jawara ide", "jar ide", "jara ide", "jwar ide"
    ],
    "jwara bantide": ["jwara ban tide", "jvara bantide", "jawara bantide", "water bantide"],
    
    # ===== HEADACHE =====
    "nanige thalenovu ide": [
        "ke tale novu ide", "nani ge tale novu", "ke talen ovu ide",
        "nani ke tale", "money get tale", "tale no video", "tale know we",
        "tale new we", "nani ge tale novu ide", "tale novu ide"
    ],
    "thalenovu":  ["tale novu", "tale no", "talen ovu", "thale novu", "tale pain"],
    
    # ===== COLD =====
    "nanige sheethaagide": [
        "nani ge sheethagide", "money get sheeta", "sheet agide", "sita guide",
        "seeta guide", "cheetah guide", "she taa gide", "sheetha agide", "negadi", "negadi agide"
    ],
    "sheetha":  ["sheeta", "seeta", "sita", "cheetah", "sheet"],
    
    # ===== COUGH =====
    "nanige kemmu ide": [
        "nani ge kemmu", "money get kim", "ke mu ide", "kim who",
        "kemmu ide", "kemu ide", "kim mu ide", "come who ide"
    ],
    "kemmu": ["kemm", "kim", "kemu", "come", "kim mu"],
    
    # ===== STOMACH PAIN =====
    "nanige hotte novu ide": [
        "nani ge hotte novu", "hot e novu", "hotel no we", "hotel novu",
        "hotte novu ide", "hottey novu", "hote novu", "otte nove"
    ],
    "hotte novu": ["hot e novu", "hotel novu", "hottey novu", "hote novu"],
    
    # ===== THROAT PAIN / SORE THROAT =====
    "nanige gantalu novu ide": [
        "gun ta lu novu", "gantalu novu", "kantalu novu", "gandalu novu",
        "gun talu", "ganta lu novu ide", "gantlu"
    ],
    "gantalu novu": ["gun ta lu", "kantalu", "gandalu", "gantalu", "gunta lu"],
    
    # ===== VOMITING =====
    "nanige vaanthi aagthide": [
        "want he", "wanti", "vanti", "vaanti aagthide", "want aagthide",
        "vomit agide", "want tea", "vanthi"
    ],
    
    # ===== BODY PAIN =====
    "nanige maisullu novu ide": [
        "my sullu novu", "mai sulu", "my su lu", "mice lu novu",
        "maisullu novu", "mai sullu novu ide", "mai novu", "mai kai novu"
    ],
    
    # ===== DIARRHEA =====
    "nanige bedi aagthide": [
        "bed e", "beedi", "bedy", "bedhi", "beedi aagthide",
        "bedi aagthide", "bed aagthide"
    ],
    
    # ===== WEAKNESS =====
    "nanige shakti illa":  [
        "shakthi illa", "sakti illa", "shock tea", "shak tea illa",
        "shakti ila", "sakthi illa", "susthu", "sustu"
    ],
    
    # ===== COMMON WORDS =====
    "nanige":  ["nani ge", "money get", "nani ke", "nani gay", "ani get", "nanny get", "money ke"],
    "ide": ["idhe", "ede", "idhey", "id", "idea"],
    "novu": ["no we", "know we", "now we", "no vu", "know you"],
    "aagthide": ["aag thide", "ag tide", "aag tide", "aagide"],
}

# Kannada to English medical term mapping
KANNADA_TO_ENGLISH = {
    "jwara": "fever",
    "thalenovu": "headache",
    "tale novu": "headache", 
    "sheetha": "cold",
    "kemmu": "cough",
    "hotte novu": "stomach pain",
    "gantalu novu": "sore throat",
    "vaanthi":  "vomiting",
    "maisullu novu": "body pain",
    "bedi":  "diarrhea",
    "shakti illa": "weakness",
    "nanige": "I have",
    "ide": "is there",
    "aagthide": "is happening",
}


def correct_kannada_medical_phrase(transcribed_text: str) -> tuple:
    """
    Correct common Kannada medical phrase mistakes from STT
    
    Args:
        transcribed_text: Text from speech recognition
        
    Returns:
        Tuple of (corrected_text, confidence, was_corrected)
    """
    text_lower = transcribed_text. lower().strip()
    
    best_match = None
    best_similarity = 0.0
    
    # Check each known phrase
    for correct_phrase, mistake_variations in KANNADA_MEDICAL_CORRECTIONS.items():
        # Check exact match with correct phrase
        if text_lower == correct_phrase:
            return correct_phrase, 1.0, False  # Already correct
        
        # Check if it matches any known mistake
        for mistake in mistake_variations:
            # Exact match with mistake
            if text_lower == mistake:
                return correct_phrase, 0.95, True
            
            # Similarity match
            similarity = SequenceMatcher(None, text_lower, mistake).ratio()
            
            if similarity > best_similarity: 
                best_similarity = similarity
                best_match = correct_phrase
    
    # Lower threshold for Kannada (STT is often very wrong)
    if best_similarity > 0.45:  # Lowered from 0.6 to 0.45
        return best_match, best_similarity, True
    
    # No correction found
    return transcribed_text, 0.0, False


def get_english_translation(kannada_phrase: str) -> str:
    """
    Get English translation of corrected Kannada phrase
    
    Args:
        kannada_phrase: Kannada phrase to translate
        
    Returns:
        English translation or original if not found
    """
    phrase_lower = kannada_phrase. lower().strip()
    
    # Check direct match
    for kannada, english in KANNADA_TO_ENGLISH.items():
        if kannada in phrase_lower:
            phrase_lower = phrase_lower.replace(kannada, english)
    
    return phrase_lower


def enhance_kannada_transcription(transcribed_text: str, language:  str = 'kn') -> dict:
    """
    Enhance Kannada transcription with corrections
    
    Args:
        transcribed_text: Original transcription
        language: Language code
        
    Returns:
        Enhanced result with corrections
    """
    if language != 'kn':
        return {
            'text': transcribed_text,
            'corrected':  False,
            'confidence': 0.75,
            'original':  transcribed_text
        }
    
    # Try to correct
    corrected_text, similarity, was_corrected = correct_kannada_medical_phrase(transcribed_text)
    
    if was_corrected:
        # Also get English translation
        english_hint = get_english_translation(corrected_text)
        
        return {
            'text':  corrected_text,
            'corrected': True,
            'confidence': similarity,
            'original': transcribed_text,
            'english_hint': english_hint,
            'correction_note': f'Auto-corrected from "{transcribed_text}" (similarity: {similarity:.1%})'
        }
    else:
        return {
            'text': transcribed_text,
            'corrected': False,
            'confidence': 0.75,
            'original': transcribed_text
        }