"""
ServVia Text-to-Speech Service
Primary:  OpenAI TTS (natural voices, excellent Hindi support)
Fallback: Google Cloud TTS
"""

import asyncio
import aiohttp
import logging
import os
import re
import uuid

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from google.cloud import texttospeech
from google.oauth2 import service_account

from common.constants import Constants
from language_service.utils import get_language_by_code
from django_core.config import Config

logger = logging.getLogger(__name__)

# ==========================================
# INITIALIZE CREDENTIALS
# ==========================================

# Google credentials
google_credentials = None
try:
    google_credentials = service_account.Credentials.from_service_account_file(
        Config.GOOGLE_APPLICATION_CREDENTIALS
    )
    logger.info("✅ Google TTS credentials loaded")
except Exception as e:
    logger.warning(f"⚠️ Google TTS credentials not available: {e}")

# OpenAI client
openai_client = None
try:
    from openai import OpenAI
    api_key = os.getenv('OPENAI_API_KEY') or getattr(Config, 'OPENAI_API_KEY', None)
    if api_key:
        openai_client = OpenAI(api_key=api_key)
        logger.info("✅ OpenAI TTS client initialized")
    else:
        logger.warning("⚠️ OpenAI API key not found for TTS")
except Exception as e:
    logger.warning(f"⚠️ OpenAI TTS client failed to initialize: {e}")


# ==========================================
# MAIN TTS FUNCTION
# ==========================================

async def synthesize_speech(
    input_text: str,
    input_language: str,
    id_string: str = None,
    aiohttp_session=None,
    audio_encoding_format=None,
    sample_rate_hertz=48000,
) -> str:
    """
    Synthesize speech - tries OpenAI TTS first (natural voices), 
    falls back to Google TTS if OpenAI fails.
    
    Args:
        input_text: Text to convert to speech
        input_language: Language code (en, hi, ta, te, etc.)
        id_string: Unique identifier for the audio file
        aiohttp_session: Optional aiohttp session (for Azure)
        audio_encoding_format: Audio format (MP3 or OGG)
        sample_rate_hertz: Sample rate for audio
        
    Returns:
        Path to the generated audio file, or None if all methods failed
    """
    # Generate unique ID if not provided
    id_string = str(uuid.uuid4()) if not id_string else str(id_string)
    
    # Clean text for speech synthesis
    cleaned_text = clean_text_for_speech(input_text)
    
    # Validate text
    if not cleaned_text or len(cleaned_text.strip()) < 2:
        logger.warning("Text too short or empty for TTS")
        return None
    
    # Truncate if too long (OpenAI limit is 4096 chars)
    if len(cleaned_text) > 4000:
        cleaned_text = cleaned_text[:4000] + "..."
        logger.info("Text truncated to 4000 characters for TTS")
    
    logger.info(f"🔊 TTS request: {len(cleaned_text)} chars, language: {input_language}")
    
    # Try OpenAI TTS first (much better quality and natural sounding)
    if openai_client:
        try:
            result = await synthesize_with_openai(cleaned_text, input_language, id_string)
            if result:
                logger.info(f"✅ OpenAI TTS success: {result}")
                return result
        except Exception as e:
            logger.error(f"OpenAI TTS failed: {e}")
    
    # Fallback to Google TTS
    if google_credentials:
        try: 
            result = await synthesize_with_google(
                cleaned_text,
                input_language,
                id_string,
                audio_encoding_format,
                sample_rate_hertz
            )
            if result:
                logger.info(f"✅ Google TTS success: {result}")
                return result
        except Exception as e:
            logger.error(f"Google TTS failed: {e}")
    
    logger.error("❌ All TTS methods failed")
    return None


# ==========================================
# OPENAI TTS (PRIMARY - NATURAL VOICES)
# ==========================================

async def synthesize_with_openai(text: str, language: str, id_string: str) -> str:
    """
    Use OpenAI TTS for natural-sounding speech.
    
    Args:
        text: Cleaned text to synthesize
        language: Language code (used for logging)
        id_string: Unique file identifier
        
    Returns: 
        Path to generated MP3 file
    """
    file_name = f"response_{id_string}.mp3"
    
    # Choose voice based on use case
    voice = "nova"
    
    logger.info(f"🎤 OpenAI TTS: voice={voice}, language={language}, chars={len(text)}")
    
    try:
        # Call OpenAI TTS API
        response = await asyncio.to_thread(
            openai_client.audio.speech.create,
            model="tts-1",  # Use "tts-1-hd" for higher quality (2x cost)
            voice=voice,
            input=text,
            response_format="mp3"
        )
        
        # Write audio to file
        with open(file_name, "wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)
        
        logger.info(f"✅ OpenAI TTS generated: {file_name}")
        return file_name
        
    except Exception as e:
        logger.error(f"OpenAI TTS synthesis error: {e}", exc_info=True)
        raise


# ==========================================
# GOOGLE TTS (FALLBACK)
# ==========================================

async def synthesize_with_google(
    text: str,
    input_language: str,
    id_string: str,
    audio_encoding_format=None,
    sample_rate_hertz=48000
) -> str:
    """
    Fallback: Use Google Cloud TTS.
    
    Args:
        text: Cleaned text to synthesize
        input_language: Language code
        id_string: Unique file identifier
        audio_encoding_format: MP3 or OGG
        sample_rate_hertz: Audio sample rate
        
    Returns: 
        Path to generated audio file
    """
    # Determine file format
    if audio_encoding_format and str(audio_encoding_format).lower() == Constants.MP3:
        audio_encoding = texttospeech.AudioEncoding.MP3
        file_name = f"response_{id_string}.{Constants.MP3}"
    else:
        audio_encoding = texttospeech.AudioEncoding.OGG_OPUS
        file_name = f"response_{id_string}.{Constants.OGG}"
    
    # Clean language code
    input_language = input_language.split("-")[0] if "-" in input_language else input_language
    
    # Map language codes to Google BCP codes
    language_map = {
        'en': 'en-IN',
        'hi': 'hi-IN',
        'ta': 'ta-IN',
        'te': 'te-IN',
        'kn': 'kn-IN',
        'ml': 'ml-IN',
        'bn': 'bn-IN',
        'gu': 'gu-IN',
        'mr': 'mr-IN',
        'pa': 'pa-IN',
        'ur': 'ur-IN',
    }
    
    # Try to get language code from language service
    language_code = "en-IN"  # Default to Indian English
    
    # Assuming get_language_by_code is available and working
    language = get_language_by_code(input_language)
    if language:
        language_code = language.get("bcp_code", language_map.get(input_language, "en-IN"))
    else:
        language_code = language_map.get(input_language, "en-IN")
    
    logger.info(f"🎤 Google TTS: language_code={language_code}, chars={len(text)}")
    
    try:
        # Create synthesis input
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        # Configure voice
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
        )
        
        # Configure audio
        audio_config = texttospeech.AudioConfig(
            audio_encoding=audio_encoding,
            sample_rate_hertz=sample_rate_hertz
        )
        
        # Create client and synthesize
        client = texttospeech.TextToSpeechClient(credentials=google_credentials)
        
        response = await asyncio.to_thread(
            client.synthesize_speech,
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
        
        # Write to file
        with open(file_name, "wb") as out:
            out.write(response.audio_content)
        
        logger.info(f"✅ Google TTS generated: {file_name}")
        return file_name
        
    except Exception as e:
        logger.error(f"Google TTS synthesis error: {e}", exc_info=True)
        raise


# ==========================================
# AZURE TTS (LEGACY SUPPORT)
# ==========================================

async def synthesize_speech_azure(text_to_synthesize, language_code, aiohttp_session):
    """
    Synthesise speech using Azure TTS model (legacy support).
    """
    audio_content = None

    url = f"https://{Config.AZURE_SERVICE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": Config.AZURE_SUBSCRIPTION_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "ogg-48khz-16bit-mono-opus",
    }

    # Select voice based on language
    AZURE_VOICE = "en-GB-SoniaNeural"
    if language_code == "en-KE":
        AZURE_VOICE = "en-KE-AsiliaNeural"
    elif language_code == "sw-KE":
        AZURE_VOICE = "sw-KE-ZuriNeural"
    elif language_code == "en-NG":
        AZURE_VOICE = "en-NG-EzinneNeural"
    elif language_code == "hi-IN":
        AZURE_VOICE = "hi-IN-SwaraNeural"
    elif language_code == "en-IN":
        AZURE_VOICE = "en-IN-NeerjaNeural"

    body = f"""
    <speak version='1.0' xml:lang='{language_code}'>
        <voice xml:lang='{language_code}' xml:gender='Female' name='{AZURE_VOICE}'>
            {text_to_synthesize}
        </voice>
    </speak>
    """

    try:
        async with aiohttp_session.post(url, data=body, headers=headers) as response:
            audio_content = await response.read() if response.status == 200 else None
    except Exception as e: 
        logger.error(f"Azure TTS error: {e}")

    return audio_content


# ==========================================
# TEXT CLEANING FOR SPEECH
# ==========================================

def clean_text_for_speech(text: str) -> str:
    """
    Clean text for natural speech synthesis.
    
    Removes:
    - Markdown formatting (headers, bold, italic, links, etc.)
    - Emojis and special characters
    - Table formatting
    - Code blocks
    - Excessive whitespace
    
    Converts: 
    - Newlines to natural pauses (periods)
    - Bullet points to flowing text
    
    Args:
        text: Raw text with potential markdown
        
    Returns:
        Clean text suitable for TTS
    """
    if not text:
        return ""
    
    clean = text
    
    # Remove markdown headers (# ## ### etc.)
    clean = re.sub(r'#{1,6}\s*', '', clean)
    
    # Remove bold/italic but keep the text
    clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean)
    clean = re.sub(r'\*([^*]+)\*', r'\1', clean)
    clean = re.sub(r'__([^_]+)__', r'\1', clean)
    clean = re.sub(r'_([^_]+)_', r'\1', clean)
    
    # Remove code blocks entirely
    clean = re.sub(r'```[\s\S]*?```', '', clean)
    clean = re.sub(r'`([^`]+)`', r'\1', clean)
    
    # Remove links but keep link text
    clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean)
    
    # Remove images entirely
    clean = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', clean)
    
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', clean)
    
    # Clean up table formatting
    clean = re.sub(r'\|', ' ', clean)
    clean = re.sub(r'-{3,}', '', clean)
    clean = re.sub(r': ?-+: ?', '', clean)
    
    # Remove horizontal rules
    clean = re.sub(r'^\s*[-*_]{3,}\s*$', '', clean, flags=re.MULTILINE)
    
    # Convert bullet points to flowing text
    clean = re.sub(r'^\s*[-*+]\s+', '', clean, flags=re.MULTILINE)
    clean = re.sub(r'^\s*\d+\.\s+', '', clean, flags=re.MULTILINE)
    
    # Remove common emojis used in the app
    emoji_chars = (
        '🔬📋🏥📊🔍💊⚠️✅❌🟢🟡🔴👤🎯📚🧠💪🥗🩺📌📈❓🚨⚡🌿⏰💧📅🔗👋'
        '📸📄🎤💡🏃‍♂️🥛🍵☕🌡️💤😊🙏🌙☀️🍃🧪💉🏋️‍♀️🧘‍♂️🥦🍎🥕🍋'
    )
    for emoji in emoji_chars:
        clean = clean.replace(emoji, '')
    
    # Remove Unicode emoji ranges
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed characters
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FA6F"  # chess symbols
        "\U0001FA70-\U0001FAFF"  # symbols extended-a
        "\U00002600-\U000026FF"  # misc symbols
        "\U00002700-\U000027BF"  # dingbats
        "]+",
        flags=re.UNICODE
    )
    clean = emoji_pattern.sub('', clean)
    
    # Clean up whitespace
    clean = re.sub(r'\n+', '. ', clean)  # Newlines become pauses
    clean = re.sub(r'\s+', ' ', clean)   # Multiple spaces to single
    clean = re.sub(r'\.\s*\. ', '. ', clean)  # Multiple periods to single period and space
    clean = re.sub(r',\s*,', ',', clean)   # Multiple commas
    
    # Remove any remaining problematic characters (surrogates)
    # This fixes the UnicodeEncodeError
    clean = clean.encode('utf-8', errors='ignore').decode('utf-8')
    
    # Final trim
    clean = clean.strip()
    
    # Remove leading/trailing punctuation
    clean = re.sub(r'^[.,;:\s]+', '', clean)
    clean = re.sub(r'[.,;:\s]+$', '.', clean)
    
    return clean
