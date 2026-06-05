"""
ServVia — Multilingual Support
==============================

Single source of truth for language metadata used across the pipeline:

  * Speech-to-Text  (Google Cloud Speech BCP-47 codes)
  * Generate-in-language (the LLM writes its reply directly in the user's
    language — see ``build_language_directive``)
  * Text-to-Speech  (BCP-47 voice codes)

Design goals
------------
1. **India first** — every scheduled Indian language is covered with its
   native name and a Google STT/TTS BCP-47 code.
2. **World coverage** — a broad set of major world languages is included, and
   any ISO code we do not explicitly map degrades gracefully (the directive is
   still generated from the raw code, which modern LLMs handle well).

The detected/selected language flows through the pipeline as a short ISO-639-1
code (e.g. ``"kn"``, ``"hi"``, ``"en"``). Google Translate's ``detect_language``
and our UI selector both speak this dialect.
"""

# ─────────────────────────────────────────────────────────────────────────────
# LANGUAGE TABLE
#   code -> (English name, native name, BCP-47 code for STT/TTS)
#   India-first, then major world languages.
# ─────────────────────────────────────────────────────────────────────────────

LANGUAGES = {
    # ── English (baseline) ──
    "en": ("English", "English", "en-IN"),

    # ── Indian languages (22 scheduled + widely used) ──
    "hi": ("Hindi", "हिन्दी", "hi-IN"),
    "kn": ("Kannada", "ಕನ್ನಡ", "kn-IN"),
    "ta": ("Tamil", "தமிழ்", "ta-IN"),
    "te": ("Telugu", "తెలుగు", "te-IN"),
    "ml": ("Malayalam", "മലയാളം", "ml-IN"),
    "bn": ("Bengali", "বাংলা", "bn-IN"),
    "gu": ("Gujarati", "ગુજરાતી", "gu-IN"),
    "mr": ("Marathi", "मराठी", "mr-IN"),
    "pa": ("Punjabi", "ਪੰਜਾਬੀ", "pa-IN"),
    "ur": ("Urdu", "اردو", "ur-IN"),
    "or": ("Odia", "ଓଡ଼ିଆ", "or-IN"),
    "as": ("Assamese", "অসমীয়া", "as-IN"),
    "ks": ("Kashmiri", "کٲشُر", "ks-IN"),
    "sd": ("Sindhi", "سنڌي", "sd-IN"),
    "ne": ("Nepali", "नेपाली", "ne-IN"),
    "sa": ("Sanskrit", "संस्कृतम्", "sa-IN"),
    "kok": ("Konkani", "कोंकणी", "kok-IN"),
    "mai": ("Maithili", "मैथिली", "mai-IN"),
    "doi": ("Dogri", "डोगरी", "doi-IN"),
    "brx": ("Bodo", "बड़ो", "brx-IN"),
    "mni": ("Manipuri", "মৈতৈলোন্", "mni-IN"),
    "sat": ("Santali", "ᱥᱟᱱᱛᱟᱲᱤ", "sat-IN"),

    # ── Major world languages ──
    "ar": ("Arabic", "العربية", "ar-XA"),
    "zh": ("Chinese", "中文", "zh"),
    "ja": ("Japanese", "日本語", "ja-JP"),
    "ko": ("Korean", "한국어", "ko-KR"),
    "es": ("Spanish", "Español", "es-ES"),
    "fr": ("French", "Français", "fr-FR"),
    "de": ("German", "Deutsch", "de-DE"),
    "pt": ("Portuguese", "Português", "pt-BR"),
    "ru": ("Russian", "Русский", "ru-RU"),
    "it": ("Italian", "Italiano", "it-IT"),
    "nl": ("Dutch", "Nederlands", "nl-NL"),
    "tr": ("Turkish", "Türkçe", "tr-TR"),
    "vi": ("Vietnamese", "Tiếng Việt", "vi-VN"),
    "th": ("Thai", "ไทย", "th-TH"),
    "id": ("Indonesian", "Bahasa Indonesia", "id-ID"),
    "ms": ("Malay", "Bahasa Melayu", "ms-MY"),
    "fa": ("Persian", "فارسی", "fa-IR"),
    "sw": ("Swahili", "Kiswahili", "sw-KE"),
    "pl": ("Polish", "Polski", "pl-PL"),
    "uk": ("Ukrainian", "Українська", "uk-UA"),
    "he": ("Hebrew", "עברית", "he-IL"),
    "fil": ("Filipino", "Filipino", "fil-PH"),
    "my": ("Burmese", "မြန်မာ", "my-MM"),
    "si": ("Sinhala", "සිංහල", "si-LK"),
    "km": ("Khmer", "ខ្មែរ", "km-KH"),
}

# Languages whose scripts are NOT space-delimited. The SSE typing animation
# splits on spaces, so these stream in larger chunks (still fully functional).
# All Indian languages are space-delimited, so none appear here.
NON_SPACED_SCRIPTS = {"zh", "ja", "th", "km", "my"}

# Default ASR confidence-equivalent fallback BCP code.
DEFAULT_BCP = "en-IN"


def _normalize(code: str) -> str:
    """Reduce 'en-US' / 'KN' / 'hi_IN' to a bare lowercase ISO code ('en', 'kn', 'hi')."""
    if not code:
        return "en"
    code = code.strip().lower().replace("_", "-")
    return code.split("-")[0]


def get_language_info(code: str):
    """
    Return (english_name, native_name, bcp_code) for a language code.

    Unknown codes degrade gracefully: the code itself is used as the name so
    the LLM still receives a usable directive (modern models recognise ISO
    codes), and the BCP code falls back to Indian English for TTS safety.
    """
    norm = _normalize(code)
    if norm in LANGUAGES:
        return LANGUAGES[norm]
    return (code or "the user's language", code or "", DEFAULT_BCP)


def to_bcp(code: str) -> str:
    """Map an ISO code to a BCP-47 code for Google STT/TTS."""
    return get_language_info(code)[2]


def is_english(code: str) -> bool:
    return _normalize(code) == "en"


def build_language_directive(code: str) -> str:
    """
    Build the instruction block injected into the Proposer prompt so the LLM
    writes its ENTIRE reply directly in the user's language.

    Returns an empty string for English (no directive needed).

    The machine-readable ``<!-- HERBS_USED: ... -->`` declaration is explicitly
    kept in English — the safety/trust engine parses it and matches herb names
    against an English evidence database.
    """
    if is_english(code):
        return ""

    english_name, native_name, _ = get_language_info(code)
    native_hint = f" ({native_name})" if native_name and native_name != english_name else ""

    return (
        "\n\n=== LANGUAGE REQUIREMENT (CRITICAL) ===\n"
        f"The patient is communicating in {english_name}{native_hint}. "
        f"Write your ENTIRE response to the patient in fluent, natural {english_name} — "
        "including all section headers, empathetic opening, remedy names, instructions, "
        "and the closing offer. Use everyday, warm language a real person speaks, not a "
        "literal word-for-word translation.\n"
        "- Keep medical/scientific terms and drug names that have no common local word in "
        "English (in parentheses) so they remain unambiguous.\n"
        "- Do NOT add an English translation alongside; respond ONLY in "
        f"{english_name}.\n"
        "- EXCEPTION: the final '<!-- HERBS_USED: ... -->' declaration MUST stay in "
        "English with common English herb names — it is parsed by the safety engine.\n"
        "=== END LANGUAGE REQUIREMENT ===\n"
    )
