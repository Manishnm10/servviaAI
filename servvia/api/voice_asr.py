"""
ServVia — Voice Speech-to-Text (Gemini primary, Whisper fallback)
=================================================================

Transcribes a recorded audio clip and AUTO-DETECTS the spoken language — no
language hint, no UI selector.

Robustness technique (ported from the original language_service/whisper_transcribe.py):
both engines are primed with a MEDICAL prompt containing common symptom phrases
in romanized + native script across Indian languages. This biases the model
toward correct medical terminology AND the correct language/script — e.g. it
stops Kannada being mis-detected/written as Hindi. See ``medical_asr_prompt.py``.

Engine priority:
  1. Google Gemini  (primary)  — most robust in testing: correct language AND
     native script for kn/hi/ta/te. Uses GEMINI_API_KEY/GOOGLE_API_KEY.
     Accepts wav/mp3/ogg/flac (NOT webm) — the frontend uploads WAV.
  2. OpenAI Whisper (fallback) — your original engine. Uses OPENAI_API_KEY.
     Accepts webm/wav/mp3/… directly.

Both return the transcript in the language's NATIVE script, so the chat pipeline
detects the language and generates the reply in that same language.
"""

import json
import logging
import os

from django_core.config import Config, ENV_CONFIG
from api.language_support import LANGUAGES
from api.medical_asr_prompt import MEDICAL_ASR_PROMPT, MEDICAL_ASR_PROMPT_JSON

logger = logging.getLogger(__name__)

# Map a language NAME or code (Whisper reports e.g. "kannada"; Gemini reports
# an ISO code) to a bare ISO-639-1 code.
_NAME_TO_ISO = {info[0].lower(): code for code, info in LANGUAGES.items()}

# Gemini model for STT — user-selected gemini-2.5-flash-lite (verified working
# for audio transcription). Deliberately DISTINCT from the skin-analysis module
# (gemini-3-flash-preview / gemini-2.5-flash / gemini-3.1-flash-lite-preview) so
# voice STT has independent quota/behavior. Cross-provider fallback on rate limit
# is OpenAI Whisper (see transcribe_audio_clip).
_GEMINI_MODELS = ["gemini-2.5-flash-lite"]

# Extension -> mime hint for Gemini (frontend sends wav).
_EXT_MIME = {
    "wav": "audio/wav", "mp3": "audio/mp3", "ogg": "audio/ogg",
    "flac": "audio/flac", "aac": "audio/aac", "m4a": "audio/aac",
}


def _to_iso(lang) -> str:
    if not lang:
        return ""
    lang = str(lang).strip().lower()
    if lang in _NAME_TO_ISO:
        return _NAME_TO_ISO[lang]
    return lang.split("-")[0]


def _mime_for(filename: str) -> str:
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "wav").lower()
    return _EXT_MIME.get(ext, "audio/wav")


def _resolve_gemini_key():
    return (
        os.getenv("GEMINI_API_KEY") or ENV_CONFIG.get("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY") or ENV_CONFIG.get("GOOGLE_API_KEY")
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. GEMINI (primary)
# ─────────────────────────────────────────────────────────────────────────────

def _transcribe_gemini(content: bytes, mime: str) -> dict:
    """Transcribe via Gemini with medical-prompt priming. Returns {transcript, language} or raises."""
    from google import genai
    from google.genai import types

    api_key = _resolve_gemini_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY / GOOGLE_API_KEY not configured")

    client = genai.Client(api_key=api_key)
    audio_part = types.Part.from_bytes(data=content, mime_type=mime)

    last_err = None
    for model in _GEMINI_MODELS:
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[MEDICAL_ASR_PROMPT_JSON, audio_part],
            )
            raw = (getattr(resp, "text", "") or "").strip()
            if not raw:
                continue
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            try:
                data = json.loads(raw)
                transcript = (data.get("transcript") or "").strip()
                language = _to_iso(data.get("language"))
            except (json.JSONDecodeError, AttributeError):
                transcript, language = raw, ""
            if transcript:
                logger.info(f"🎙️ Gemini STT ok ({model}) | lang={language} | {len(transcript)} chars")
                return {"transcript": transcript, "language": language}
        except Exception as e:
            last_err = e
            logger.warning(f"Gemini STT model {model} failed: {e}")
    if last_err:
        raise last_err
    raise RuntimeError("Gemini returned no transcript")


# ─────────────────────────────────────────────────────────────────────────────
# 2. OPENAI WHISPER (fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _transcribe_whisper(content: bytes, filename: str) -> dict:
    """Transcribe via OpenAI Whisper with medical-prompt priming. Returns dict or {}."""
    key = Config.OPENAI_WHISPER_KEY
    if not key:
        return {}
    try:
        from openai import OpenAI

        client = OpenAI(api_key=key)
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, content),
            prompt=MEDICAL_ASR_PROMPT,
            response_format="verbose_json",
        )
        transcript = (getattr(result, "text", "") or "").strip()
        language = _to_iso(getattr(result, "language", "") or "")
        if transcript:
            logger.info(f"🎙️ Whisper STT ok | lang={language} | {len(transcript)} chars")
            return {"transcript": transcript, "language": language, "engine": "openai-whisper"}
    except Exception as e:
        logger.warning(f"OpenAI Whisper fallback failed: {e}")
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY
# ─────────────────────────────────────────────────────────────────────────────

def transcribe_audio_clip(content: bytes, filename: str = "voice.wav") -> dict:
    """
    Transcribe an audio clip with automatic language detection.

    Args:
        content:  Raw audio bytes. Frontend uploads WAV (Gemini-friendly); the
                  Whisper fallback also accepts webm/mp3/etc.
        filename: Extension hint (e.g. "voice.wav").

    Returns:
        {"transcript": str, "language": iso_code, "engine": str}
        On failure: {"transcript": "", "language": "", "engine": "none", "error": ...}
    """
    if not content:
        return {"transcript": "", "language": "", "engine": "none", "error": "empty audio"}

    # ── 1. Gemini (primary) ──
    try:
        out = _transcribe_gemini(content, _mime_for(filename))
        if out.get("transcript"):
            out["engine"] = "gemini"
            return out
    except Exception as e:
        logger.warning(f"Gemini STT unavailable, trying Whisper fallback: {e}")

    # ── 2. Whisper (fallback) ──
    out = _transcribe_whisper(content, filename)
    if out.get("transcript"):
        return out

    logger.error("❌ All STT engines failed — caller should fall back to typing")
    return {"transcript": "", "language": "", "engine": "none", "error": "transcription unavailable"}
