"""
Language Translation Service for ServVIA
Current Date and Time (UTC): 2025-11-24 13:53:13
Current User: lil-choco

Features:
- Automatic language detection
- Translation to/from English
- Kannada medical dictionary for better accuracy
- Google Cloud Translation API integration
"""
import os
import asyncio
from google.cloud import translate_v2 as translate
from google.oauth2 import service_account
from django.conf import settings

# Constants
BASE_DIR = settings.BASE_DIR

class Constants:
    """Language code constants for translation service"""
    LANGUAGE_SHORT_CODE_ENG = 'en'
    LANGUAGE_SHORT_CODE_NATIVE = 'en'  # Default to English
    LANGUAGE_CODE_ENGLISH = 'en'
    LANGUAGE_CODE_KANNADA = 'kn'
    LANGUAGE_CODE_HINDI = 'hi'
    LANGUAGE_CODE_TAMIL = 'ta'
    LANGUAGE_CODE_TELUGU = 'te'

# Google Cloud credentials
try:
    from django.conf import settings
    
    # ✅ CORRECTED PATH: Use settings or fallback to direct path
    gcp_cred_path = getattr(settings, 'GCP_TRANSLATION_CREDENTIALS_PATH', 
                            r"C:\Users\cools\Downloads\servvia-google-credentials.json")
    
    if os.path.exists(gcp_cred_path):
        credentials = service_account.Credentials.from_service_account_file(gcp_cred_path)
        print(f"✅ GCP Translation credentials loaded: {gcp_cred_path}")
    else:
        print(f"⚠️ GCP credentials file not found at: {gcp_cred_path}")
        credentials = None
        
except Exception as e:
    print(f"⚠️ Could not load GCP credentials: {e}")
    credentials = None


# ✅ Kannada medical dictionary for common health terms
KANNADA_MEDICAL = {
    # Fever
    "nange jwara ide": "I have fever",
    "jwara idhe": "have fever",
    "nange jwara edhe":"I have fever",
    "jwara": "fever",
    "jvara": "fever",
    "kaichi": "fever",
    
    # Pain
    "novu ide" : "have pain",
    "novu": "pain",
    "tala novu": "headache",
    "hotte novu": "stomach ache",
    "kaalu novu": "leg pain",
    
    # Cough/Cold
    "nanige kemmu ide": "I have cough",
    "nange kemmu ide": "I have cough",
    "kemmu ide": "have cough",
    "kemmu": "cough",
    "mosaru": "cold",
    "sali": "cough",
    
    # Common phrases
    "nange": "I have",
    "nanage": "I have",
    "nanige":"I have",
    "enu maadali" : "what to do",
    "upachara": "treatment",
    "aushadha": "medicine",
    
    # Body parts
    "tala": "head",
    "tale": "head",
    "hotte": "stomach",
    "otte":"stomach",
    "kaalu": "leg",
    "kai": "hand",
    "bennu": "back",
    
    # Symptoms
    "vanthi": "vomiting",
    "hakki": "vomit",
    "loose motion": "loose motion",
    "khushi": "happy",  # Sometimes used in context
}


def check_kannada_medical(text: str) -> str:
    """
    Check if text contains Kannada medical terms and translate
    Enhanced with better matching
    
    Args:
        text: Input text to check
        
    Returns:
        English translation if found, None otherwise
    """
    text_lower = text.lower().strip()
    
    # Direct match
    if text_lower in KANNADA_MEDICAL:
        translation = KANNADA_MEDICAL[text_lower]
        print(f"✅ Direct match: '{text}' → '{translation}'")
        return translation
    
    # Partial match - check if text contains any key
    for kannada, english in KANNADA_MEDICAL.items():
        if kannada in text_lower:
            # Build translated sentence
            translated_parts = []
            for word in text_lower.split():
                if word in KANNADA_MEDICAL:
                    translated_parts.append(KANNADA_MEDICAL[word])
                else:
                    translated_parts.append(word)
            
            translation = ' '.join(translated_parts)
            print(f"✅ Partial match: '{text}' → '{translation}'")
            return translation
    
    return None


async def a_translate_to_english(text: str) -> str:
    """
    Translate text to English using Google Cloud Translation
    
    Args:
        text: Text to translate
        
    Returns:
        Translated English text
    """
    if not credentials:
        return text
        
    translate_client = translate.Client(credentials=credentials)
    
    # Add healthcare context hint for better translation
    translation = await asyncio.to_thread(
        translate_client.translate,
        text,
        target_language=Constants.LANGUAGE_SHORT_CODE_ENG,
        format_="text",
        model="nmt"  # Use Neural Machine Translation for better accuracy
    )
    return translation["translatedText"]


async def a_translate_to(text: str, lang_code: str) -> str:
    """
    Translate text to specified language
    
    Args:
        text: Text to translate
        lang_code: Target language code (e.g., 'kn' for Kannada)
        
    Returns:
        Translated text
    """
    if not credentials:
        return text
        
    translate_client = translate.Client(credentials=credentials)
    
    # Extract base language code (hi-Latn -> hi, kn -> kn)
    lang_code = lang_code.split("-")[0] if "-" in lang_code else lang_code
    
    translation = await asyncio.to_thread(
        translate_client.translate,
        text,
        target_language=lang_code,
        format_="text",
        model="nmt"  # Use Neural Machine Translation
    )
    return translation["translatedText"]


async def detect_language_and_translate_to_english(input_msg):
    """
    Detect the language of specified text and translate it to English
    Enhanced with Kannada medical dictionary for better accuracy
    
    Args:
        input_msg: Input message in any language
        
    Returns:
        Tuple of (translated_text, detected_language)
    """
    if not credentials:
        return input_msg, "en"
    
    # Step 0: Check Kannada medical dictionary first (with better logging)
    dict_translation = check_kannada_medical(input_msg)
    
    if dict_translation:
        print(f"✅ Medical Dictionary Match:")
        print(f"   Input: '{input_msg}'")
        print(f"   Translation: '{dict_translation}'")
        print(f"   Source: Kannada Medical Dictionary")
        return dict_translation, "kn"  # ✅ Return "kn" for Kannada
    
    # Step 1: Detect language with Google
    translate_client = translate.Client(credentials=credentials)
    
    try:
        language_detection = await asyncio.to_thread(translate_client.detect_language, input_msg)
        input_language_detected = language_detection["language"]
        confidence = language_detection.get("confidence", 0)
        
        print(f"🌐 Language Detection:")
        print(f"   Input: '{input_msg}'")
        print(f"   Detected: {input_language_detected} (confidence: {confidence})")
    except Exception as e:
        print(f"❌ Language detection failed: {e}")
        input_language_detected = "en"
        confidence = 0

    # Step 2: Translate if not English
    if input_language_detected != Constants.LANGUAGE_SHORT_CODE_ENG:
        try:
            translated_input_message = await a_translate_to_english(input_msg)
            print(f"   Translated: '{translated_input_message}'")
        except Exception as e:
            print(f"❌ Translation failed: {e}")
            translated_input_message = input_msg
    else:
        translated_input_message = input_msg
        print(f"   Already in English, no translation needed")

    return translated_input_message, input_language_detected


async def translate_text_to_language(text, target_language_code):
    """
    Translate text to target language
    
    Args:
        text: Text to translate
        target_language_code: Target language code
        
    Returns:
        Translated text
    """
    if not credentials:
        return text
        
    try:
        translate_client = translate.Client(credentials=credentials)
        
        # Extract base language code (hi-Latn -> hi, kn -> kn, en-US -> en)
        base_lang = target_language_code.split("-")[0] if "-" in target_language_code else target_language_code
        
        print(f"🌐 Translation Output:")
        print(f"   Text length: {len(text)} chars")
        print(f"   Target: {base_lang} (from {target_language_code})")
        
        # Translate the text to the detected language
        result = await asyncio.to_thread(
            translate_client.translate,
            text,
            target_language=base_lang,
            format_="text",
            model="nmt"  # Neural Machine Translation for better quality
        )
        
        translated = result['translatedText']
        print(f"   ✅ Translated successfully")
        
        return translated
        
    except Exception as e:
        print(f"❌ Translation error: {e}")
        return text