"""
ServVia Fast TTS Service
=========================
Generates TTS in chunks for fast playback start.
Uses OpenAI TTS (same voice as original) with chunked audio delivery. 

First chunk plays in ~2-3 seconds while rest generates in background.
Full response is read - no trimming! 

Author: ServVia Team
Version: 2.0.0
"""

import asyncio
import logging
import os
import re
import uuid
import base64
from typing import List, Optional, Generator, Tuple

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# OpenAI client
openai_client = None
try:
    from openai import OpenAI
    api_key = os. getenv('OPENAI_API_KEY')
    if api_key:
        openai_client = OpenAI(api_key=api_key)
        logger.info("✅ FastTTS:  OpenAI client initialized")
except ImportError: 
    logger.warning("⚠️ FastTTS: OpenAI not installed")


# ==========================================
# TEXT CLEANING (Same as original tts.py)
# ==========================================

def clean_text_for_speech(text: str) -> str:
    """Clean text for TTS - removes markdown, emojis, etc."""
    if not text:
        return ""
    
    clean = text
    
    # Remove markdown headers
    clean = re.sub(r'#{1,6}\s*', '', clean)
    
    # Remove bold/italic but keep text
    clean = re. sub(r'\*\*([^*]+)\*\*', r'\1', clean)
    clean = re.sub(r'\*([^*]+)\*', r'\1', clean)
    clean = re.sub(r'__([^_]+)__', r'\1', clean)
    clean = re.sub(r'_([^_]+)_', r'\1', clean)
    
    # Remove code blocks
    clean = re.sub(r'```[\s\S]*? ```', '', clean)
    clean = re.sub(r'`([^`]+)`', r'\1', clean)
    
    # Remove links but keep text
    clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean)
    
    # Remove images
    clean = re. sub(r'!\[([^\]]*)\]\([^)]+\)', '', clean)
    
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', clean)
    
    # Clean table formatting
    clean = re.sub(r'\|', ' ', clean)
    clean = re.sub(r'-{3,}', '', clean)
    
    # Remove horizontal rules
    clean = re.sub(r'^\s*[-*_]{3,}\s*$', '', clean, flags=re. MULTILINE)
    
    # Convert bullet points to flowing text
    clean = re.sub(r'^\s*[-*+]\s+', '', clean, flags=re. MULTILINE)
    clean = re.sub(r'^\s*\d+\.\s+', '', clean, flags=re. MULTILINE)
    
    # Remove emojis
    emoji_pattern = re. compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U00002600-\U000026FF"
        "\U00002700-\U000027BF"
        "\U00002139"
        "]+",
        flags=re.UNICODE
    )
    clean = emoji_pattern.sub('', clean)
    
    # Clean whitespace
    clean = re.sub(r'\n+', '.  ', clean)
    clean = re.sub(r'\s+', ' ', clean)
    clean = re.sub(r'\.\s*\.\s*', '. ', clean)
    clean = re.sub(r',\s*,', ',', clean)
    
    # Fix encoding
    clean = clean. encode('utf-8', errors='ignore').decode('utf-8')
    
    # Final cleanup
    clean = clean.strip()
    clean = re.sub(r'^[.,;:\s]+', '', clean)
    clean = re. sub(r'[.,;:\s]+$', '. ', clean)
    
    return clean


# ==========================================
# TEXT CHUNKING
# ==========================================

def split_text_into_chunks(text: str, max_chunk_size: int = 400) -> List[str]:
    """
    Split text into chunks at sentence boundaries.
    Smaller chunks = faster first audio playback.
    
    Args:
        text:  Cleaned text to split
        max_chunk_size: Maximum characters per chunk (400 = ~3 seconds audio)
    
    Returns:
        List of text chunks
    """
    if len(text) <= max_chunk_size: 
        return [text] if text. strip() else []
    
    # Split by sentences (period/exclamation/question followed by space)
    sentences = re.split(r'(? <=[.!? ])\s+', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        if len(current_chunk) + len(sentence) + 1 <= max_chunk_size: 
            current_chunk += (" " if current_chunk else "") + sentence
        else:
            if current_chunk: 
                chunks.append(current_chunk. strip())
            
            # Handle very long sentences
            if len(sentence) > max_chunk_size: 
                words = sentence.split()
                current_chunk = ""
                for word in words:
                    if len(current_chunk) + len(word) + 1 <= max_chunk_size:
                        current_chunk += (" " if current_chunk else "") + word
                    else:
                        if current_chunk: 
                            chunks.append(current_chunk. strip())
                        current_chunk = word
            else:
                current_chunk = sentence
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


# ==========================================
# TTS GENERATION
# ==========================================

def generate_tts_for_chunk(chunk:  str, voice:  str = "nova") -> Optional[bytes]:
    """
    Generate TTS audio for a single text chunk.
    
    Args:
        chunk: Text to synthesize
        voice:  OpenAI voice (nova, alloy, echo, fable, onyx, shimmer)
    
    Returns:
        Audio bytes (MP3) or None if failed
    """
    if not openai_client or not chunk: 
        return None
    
    try: 
        response = openai_client.audio.speech. create(
            model="tts-1",
            voice=voice,
            input=chunk,
            response_format="mp3",
        )
        return response.content
    except Exception as e:
        logger. error(f"TTS chunk error: {e}")
        return None


def generate_first_chunk_fast(text: str, voice: str = "nova") -> Tuple[Optional[bytes], bool]:
    """
    Generate ONLY the first chunk for immediate playback.
    This is called first to start audio quickly (~2-3 seconds).
    
    Args:
        text: Full text to synthesize
        voice: OpenAI voice name
    
    Returns:
        Tuple of (first_audio_bytes, has_more_content)
    """
    if not openai_client: 
        logger.error("OpenAI client not available")
        return None, False
    
    # Clean text
    cleaned = clean_text_for_speech(text)
    if not cleaned:
        return None, False
    
    # Split into chunks
    chunks = split_text_into_chunks(cleaned, max_chunk_size=400)
    
    if not chunks:
        return None, False
    
    logger.info(f"🔊 FastTTS:  Generating first chunk ({len(chunks[0])} chars, {len(chunks)} total chunks)")
    
    # Generate ONLY first chunk
    first_audio = generate_tts_for_chunk(chunks[0], voice)
    has_more = len(chunks) > 1
    
    if first_audio: 
        logger.info(f"✅ First chunk ready: {len(first_audio)} bytes, has_more={has_more}")
    
    return first_audio, has_more


def generate_remaining_chunks(text:  str, voice: str = "nova") -> Optional[bytes]:
    """
    Generate audio for all chunks AFTER the first one.
    Called in background while first chunk plays. 
    
    Args: 
        text: Full text (will skip first chunk)
        voice: OpenAI voice name
    
    Returns:
        Combined audio bytes for chunks 2 onwards, or None
    """
    if not openai_client:
        return None
    
    # Clean text
    cleaned = clean_text_for_speech(text)
    if not cleaned:
        return None
    
    # Split into chunks
    chunks = split_text_into_chunks(cleaned, max_chunk_size=400)
    
    if len(chunks) <= 1:
        return None  # No remaining chunks
    
    logger.info(f"🔊 FastTTS:  Generating remaining {len(chunks) - 1} chunks")
    
    # Generate chunks 2 onwards
    remaining_audio = b""
    for i, chunk in enumerate(chunks[1:], start=2):
        audio = generate_tts_for_chunk(chunk, voice)
        if audio: 
            remaining_audio += audio
            logger.debug(f"✅ Chunk {i}/{len(chunks)} done")
    
    if remaining_audio:
        logger.info(f"✅ Remaining chunks ready: {len(remaining_audio)} bytes")
    
    return remaining_audio if remaining_audio else None


def generate_full_audio(text:  str, voice: str = "nova") -> Optional[bytes]: 
    """
    Generate full audio for entire text (all chunks combined).
    Used as fallback or for short texts.
    
    Args:
        text: Full text to synthesize
        voice: OpenAI voice name
    
    Returns:
        Combined audio bytes or None
    """
    if not openai_client:
        logger.error("OpenAI client not available")
        return None
    
    # Clean text
    cleaned = clean_text_for_speech(text)
    if not cleaned:
        return None
    
    # Split into chunks
    chunks = split_text_into_chunks(cleaned, max_chunk_size=500)
    
    if not chunks:
        return None
    
    logger.info(f"🔊 FastTTS:  Generating full audio ({len(cleaned)} chars, {len(chunks)} chunks)")
    
    # Generate all chunks
    full_audio = b""
    for i, chunk in enumerate(chunks, start=1):
        audio = generate_tts_for_chunk(chunk, voice)
        if audio:
            full_audio += audio
            logger.debug(f"✅ Chunk {i}/{len(chunks)} done")
    
    if full_audio: 
        logger.info(f"✅ Full audio ready: {len(full_audio)} bytes")
    
    return full_audio if full_audio else None


# ==========================================
# STREAMING GENERATOR
# ==========================================

def generate_streaming_tts(text: str, voice:  str = "nova") -> Generator[bytes, None, None]: 
    """
    Generator that yields audio chunks as they're generated. 
    Use this for true streaming playback.
    
    Usage:
        for audio_chunk in generate_streaming_tts(text):
            send_to_client(audio_chunk)
    """
    if not openai_client: 
        logger.error("OpenAI client not available")
        return
    
    # Clean text
    cleaned = clean_text_for_speech(text)
    if not cleaned:
        return
    
    # Split into chunks
    chunks = split_text_into_chunks(cleaned, max_chunk_size=400)
    
    logger.info(f"🔊 StreamingTTS: {len(cleaned)} chars, {len(chunks)} chunks")
    
    # Generate and yield each chunk
    for i, chunk in enumerate(chunks, start=1):
        audio = generate_tts_for_chunk(chunk, voice)
        if audio:
            logger.debug(f"✅ Streaming chunk {i}/{len(chunks)}: {len(audio)} bytes")
            yield audio


# ==========================================
# SYNC WRAPPER (for compatibility)
# ==========================================

def generate_fast_tts_sync(text: str, voice: str = "nova") -> Optional[str]:
    """
    Synchronous function that returns base64-encoded full audio.
    For backwards compatibility with existing code.
    
    Args:
        text: Text to synthesize
        voice: OpenAI voice name
    
    Returns:
        Base64-encoded MP3 audio string or None
    """
    audio_bytes = generate_full_audio(text, voice)
    
    if audio_bytes:
        return base64.b64encode(audio_bytes).decode('utf-8')
    
    return None