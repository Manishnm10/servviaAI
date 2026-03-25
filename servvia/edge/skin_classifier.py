"""
ServVia Edge — Local Skin Disease Classifier
==============================================

Uses Moondream2 (1.8B) via Ollama for on-device skin image analysis.
All processing runs locally — no image data leaves the user's machine.

Model: moondream (1.8B, vision-native, ~1.7 GB)

Pipeline position:
    [Image Upload] -> [Local Validation] -> ** THIS CLASSIFIER ** -> Structured JSON

Returns None if analysis fails — caller decides how to handle (no automatic fallback).
"""

import base64
import json
import logging
import time
from typing import Dict, Optional

import httpx

logger = logging.getLogger("ServVia.Edge.SkinClassifier")

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "moondream"           # Moondream2 1.8B — fast, vision-native
EDGE_TIMEOUT = 45                    # moondream cold-start is ~3s (1.8B)
CONFIDENCE_THRESHOLD = 65

# Only moondream is installed locally
_PREFERRED_VISION_MODELS = [
    "moondream",         # Moondream2 1.8B — primary and only local model
]

# Selected model — set by _init_vision_model() on first call
_active_model: Optional[str] = None
_model_check_time: float = 0.0       # timestamp of last Ollama check
_MODEL_CHECK_TTL: float = 30.0       # cache Ollama availability for 30s

# Scalp conditions requiring a second-pass plaque vs flake challenge
_SCALP_AMBIGUOUS = {"Dandruff (Seborrheic Dermatitis)", "Psoriasis (mild forms)", "Scalp Folliculitis"}

# Supported skin conditions — matches Gemini pipeline
SKIN_CONDITIONS = [
    "Dry Skin (Xerosis)",
    "Acne",
    "Fungal Infections (Ringworm, Athlete's Foot)",
    "Sunburn",
    "Eczema (Atopic Dermatitis)",
    "Dandruff (Seborrheic Dermatitis)",
    "Contact Dermatitis",
    "Heat Rash (Prickly Heat)",
    "Psoriasis (mild forms)",
    "Hives (Urticaria)",
    "Cold Sores",
    "Warts (Common Warts)",
    "Razor Bumps (Pseudofolliculitis Barbae)",
    "Ingrown Hairs",
    "Chapped Lips",
    "Athlete's Foot",
    "Jock Itch",
    "Scalp Folliculitis",
    "Mosquito Bite Reactions",
    "Allergic Rash (Mild Allergic Dermatitis)",
    "Normal Skin",
]

# ─────────────────────────────────────────────────────────────────────────────
# D2C — Describe-then-Classify: visual feature extraction prompt
#
# Instead of asking the local model to produce complex medical JSON (which small
# models fail at), we ask 10 simple yes/no questions about what it sees.
# A deterministic rule-based classifier then maps those answers to a diagnosis.
# This plays to moondream's actual strength and produces consistent results.
# ─────────────────────────────────────────────────────────────────────────────

FEATURE_EXTRACTION_PROMPT = (
    "Describe the skin condition in this image. "
    "Cover: body part location, color of the affected area, "
    "size of lesions (tiny/small/large), how many lesions are visible, "
    "texture (smooth/rough/scaly/crusty), whether bumps are raised or flat, "
    "and any pustules, plaques, flaking, or ring shapes. "
    "Be specific and clinical."
)


# ─────────────────────────────────────────────────────────────────────────────
# Ollama health check
# ─────────────────────────────────────────────────────────────────────────────

def _init_vision_model() -> Optional[str]:
    """
    Query Ollama for available models and return the best vision model name.
    Preference order defined in _PREFERRED_VISION_MODELS.

    Results are cached for _MODEL_CHECK_TTL seconds to avoid repeated
    HTTP round-trips (especially the 3s timeout when Ollama is offline).
    """
    global _active_model, _model_check_time

    now = time.time()
    if _active_model is not None and (now - _model_check_time) < _MODEL_CHECK_TTL:
        return _active_model
    # Also respect TTL for negative results (Ollama offline)
    if _active_model is None and _model_check_time > 0 and (now - _model_check_time) < _MODEL_CHECK_TTL:
        return None

    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        _model_check_time = time.time()
        if resp.status_code != 200:
            _active_model = None
            return None
        available = [m.get("name", "") for m in resp.json().get("models", [])]
        if not available:
            _active_model = None
            return None

        for preferred in _PREFERRED_VISION_MODELS:
            base = preferred.split(":")[0].lower()
            tag = preferred.split(":")[1] if ":" in preferred else None
            for name in available:
                name_lower = name.lower()
                if base in name_lower and (tag is None or tag in name_lower):
                    if _active_model != name:
                        logger.info(f"[EDGE] Selected vision model: {name}")
                    _active_model = name
                    return name

        logger.warning(f"[EDGE] No preferred vision model found. Available: {available}")
        _active_model = None
        return None
    except Exception:
        _model_check_time = time.time()
        _active_model = None
        return None


def is_ollama_available() -> bool:
    """Check if Ollama is running and a usable vision model is available."""
    return _init_vision_model() is not None


def warmup_vision_model() -> bool:
    """
    Pre-load the vision model into memory with a cheap text-only request.
    Call this at server startup so the first real image request isn't cold.
    Returns True if model responded, False otherwise.
    """
    model = _init_vision_model()
    if not model:
        return False
    try:
        logger.info(f"[EDGE] Warming up {model} (vision layers)...")
        # Use a 1x1 white pixel image to trigger full vision pipeline load
        # (text-only warm-up does NOT pre-load the visual encoder)
        import base64, io
        from PIL import Image as _PILImage
        tiny = _PILImage.new("RGB", (1, 1), color=(255, 255, 255))
        buf = io.BytesIO()
        tiny.save(buf, format="JPEG")
        tiny_b64 = base64.b64encode(buf.getvalue()).decode()

        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "What color is this?", "images": [tiny_b64]}],
                "stream": False,
                "options": {"num_predict": 3, "num_ctx": 512},
            },
            timeout=90,
        )
        if resp.status_code == 200:
            logger.info(f"[EDGE] {model} is warm and ready.")
            return True
    except Exception as e:
        logger.warning(f"[EDGE] Warm-up failed: {e}")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Edge classification
# ─────────────────────────────────────────────────────────────────────────────

def classify_skin_image(image_path: str) -> Optional[Dict]:
    """
    Classify a skin image using the D2C (Describe-then-Classify) pipeline.

    Step 1 — Describe: Moondream2 answers 10 targeted yes/no visual questions
             about the image (~80 tokens output, fast).
    Step 2 — Classify: A deterministic rule-based classifier maps those feature
             answers to one of the 21 supported skin conditions.
    Step 3 — Refine: Scalp challenge pass corrects psoriasis/dandruff ambiguity.

    Returns a structured dict matching Gemini's output format, or None on failure.
    """
    model = _init_vision_model()
    if not model:
        logger.warning("[EDGE] Ollama not available — skipping edge classification")
        return None

    # Load, resize to 512px max, encode as base64 JPEG
    try:
        from PIL import Image
        import io
        img = Image.open(image_path).convert("RGB")
        max_dim = max(img.size)
        if max_dim > 512:
            scale = 512 / max_dim
            img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        image_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        logger.info(f"[EDGE] Image encoded: {img.size[0]}x{img.size[1]}")
    except Exception as e:
        logger.error(f"[EDGE] Image load failed: {e}")
        return None

    start_time = time.time()

    # ── D2C Step 1: Extract visual features ──────────────────────────────────
    features = _extract_visual_features(image_b64, model)
    if not features:
        logger.warning("[EDGE] Feature extraction returned nothing")
        return None

    elapsed_desc = time.time() - start_time
    logger.info(f"[EDGE] Features in {elapsed_desc:.1f}s: {features}")

    # ── D2C Step 2: Rule-based classification ────────────────────────────────
    condition, confidence, severity = _d2c_classify(features)
    affected_area = features.get("location", "other")

    # ── D2C Step 3: Scalp challenge refinement ───────────────────────────────
    if condition in _SCALP_AMBIGUOUS or affected_area == "scalp":
        challenge = _challenge_scalp_condition(image_b64)
        logger.info(f"[EDGE] Scalp challenge: {challenge!r} (initial: {condition})")
        if challenge == "A" and "Psoriasis" not in condition:
            condition = "Psoriasis (mild forms)"
            confidence = max(confidence, 82)
            severity = "moderate"
            logger.info("[EDGE] Scalp override → Psoriasis (thick adherent plaque confirmed)")
        elif challenge == "B" and "Dandruff" not in condition:
            condition = "Dandruff (Seborrheic Dermatitis)"
            confidence = max(confidence, 78)
            severity = "mild"
            logger.info("[EDGE] Scalp override → Dandruff (loose flakes confirmed)")

    elapsed = time.time() - start_time
    logger.info(f"[EDGE] D2C result: {condition} ({confidence}%) [{severity}] in {elapsed:.1f}s")

    return {
        "condition": condition,
        "confidence": confidence,
        "severity": severity,
        "key_features": _build_key_features(features, condition),
        "affected_area": affected_area,
        "description": _build_description(condition, features),
        "reasoning": _build_reasoning(condition, features),
        "differential_diagnosis": _build_differentials(condition),
        "distinguishing_features": _build_distinguishing(condition, features),
        "border_type": "sharp/defined" if features.get("red_border") else "diffuse/poorly-defined",
        "scale_type": (
            "thick/silvery" if features.get("thick_crust")
            else ("thin/fine" if features.get("scaling") else "none")
        ),
        "texture": "raised/plaque-like" if features.get("raised") else "flat",
        "edge_inference_time": round(elapsed, 2),
        "edge_model": model,
    }


_SCALP_CHALLENGE_PROMPT = """Look ONLY at the scale/flake on this scalp image. Ignore everything else.

Which exactly do you physically see?
A = THICK, RAISED, adherent silvery-white PLAQUE patches with a sharply defined reddish border around them (psoriasis plaques — like raised crusty patches stuck to the skin, not loose)
B = Fine, loose white or yellowish flakes that are NOT raised into plaques, no defined red border (dandruff — like shed skin flakes)

Reply with only the single letter A or B."""


def _challenge_scalp_condition(image_b64: str) -> Optional[str]:
    """
    Targeted binary challenge for ambiguous scalp conditions.
    Returns 'A' (plaque → psoriasis) or 'B' (flake → dandruff), or None on failure.
    Uses minimal tokens (~3s) so total overhead is small.
    """
    payload = {
        "model": _active_model or OLLAMA_MODEL,
        "messages": [{"role": "user", "content": _SCALP_CHALLENGE_PROMPT, "images": [image_b64]}],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 5, "num_ctx": 2048},
    }
    try:
        resp = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=20)
        if resp.status_code != 200:
            return None
        content = resp.json().get("message", {}).get("content", "").strip().upper()
        for char in content:
            if char in ("A", "B"):
                return char
        return None
    except Exception as e:
        logger.warning(f"[EDGE] Scalp challenge failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# D2C Step 1 — Feature extraction via moondream
# ─────────────────────────────────────────────────────────────────────────────

def _extract_visual_features(image_b64: str, model: str) -> Optional[Dict]:
    """
    Ask moondream to describe the skin image in natural language covering
    color, size, count, location, and texture. Then parse the narrative
    into a structured features dict.

    Moondream handles open-ended description far better than structured
    multi-answer formats — this exploits its actual capability.
    Expected output time: 5-12 seconds.
    """
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": FEATURE_EXTRACTION_PROMPT,
                "images": [image_b64],
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 200,
            "num_ctx": 2048,
        },
    }
    try:
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=EDGE_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.error(f"[EDGE] Ollama {resp.status_code}: {resp.text[:200]}")
            return None
        content = resp.json().get("message", {}).get("content", "").strip()
        word_count = len(content.split())
        if not content or word_count < 20:
            logger.warning(f"[EDGE] Moondream description too short ({word_count} words)")
            return None
        logger.info(f"[EDGE] Moondream description: {content}")
        return _parse_narrative_features(content)
    except httpx.TimeoutException:
        logger.warning("[EDGE] Moondream timeout")
        return None
    except Exception as e:
        logger.error(f"[EDGE] Feature extraction error: {e}", exc_info=True)
        return None


def _parse_narrative_features(text: str) -> Dict:
    """
    Extract clinical visual features from moondream's free-text description.

    Uses regex word-boundary matching to avoid substring false-positives
    (e.g. "surface" containing "face", "raised" inside "No raised plaques").
    Negation detection strips "no/not/without X" patterns before checking.
    """
    import re

    t = text.lower()

    def _word(kw: str) -> bool:
        """True if kw appears as a whole word/phrase in t."""
        return bool(re.search(r'\b' + re.escape(kw) + r'\b', t))

    def _any_word(kws) -> bool:
        return any(_word(kw) for kw in kws)

    def _negated(kw: str) -> bool:
        """True if kw is preceded by a negation within 60 chars (covers list negation)."""
        pattern = r'\b(no|not|without|never|none|absent)\b.{0,60}\b' + re.escape(kw) + r'\b'
        return bool(re.search(pattern, t))

    # ── Location — word-boundary safe; neck/beard before face ─────────────────
    _LOC_KEYWORDS = {
        "scalp":  ["scalp", "hairline", "head", "hair", "crown", "vertex"],
        "neck":   ["neck", "jawline", "beard"],
        "face":   ["face", "cheek", "forehead", "chin", "nose", "facial"],
        "foot":   ["foot", "feet", "toe", "sole", "ankle"],
        "groin":  ["groin", "pubic"],
        "arm":    ["arm", "elbow", "forearm", "wrist"],
        "leg":    ["leg", "knee", "shin", "calf"],
        "back":   ["back"],
    }
    location = "other"
    for loc, kws in _LOC_KEYWORDS.items():
        if _any_word(kws):
            location = loc
            break
    # "inner thigh" → groin (compound phrase, checked separately)
    if location == "other" and "inner thigh" in t:
        location = "groin"

    # ── Early-exit: description indicates healthy/normal skin ────────────────
    _normal_phrases = ["no visible", "no signs of", "no evidence of", "no abnormal",
                       "appears healthy", "healthy skin", "normal skin", "no lesion",
                       "no redness", "no scaling", "no bumps"]
    _is_normal_desc = sum(1 for ph in _normal_phrases if ph in t) >= 2

    if _is_normal_desc:
        return {
            "location": location if location != "other" else "other",
            "scaling": False, "thick_crust": False, "raised": False,
            "red_border": False, "pustules": False, "ring_pattern": False,
            "large_bumps": False, "tiny_uniform": False, "oily": False,
            "_description": text,
        }

    # ── Scaling / flaking ─────────────────────────────────────────────────────
    scaling = _any_word(["scaling", "scales", "scale", "flaking", "flakes", "peeling",
                         "desquamation", "scaly", "flaky"]) and not (
        _negated("scaling") or _negated("scales") or _negated("flaking") or
        _negated("flakes") or _negated("peeling") or _negated("scaly")
    )

    # ── Thick crust / plaque — only when NOT negated ─────────────────────────
    _thick_kws = ["thick plaque", "silvery plaque", "silvery scale", "silver plaque",
                  "thick scale", "thick crust", "adherent plaque", "adherent scale",
                  "silvery", "compacted scale", "crusty patch", "stuck-on"]
    thick_crust = _any_word(_thick_kws) or (
        _word("plaque") and not _negated("plaque") and not _negated("plaques")
    )

    # ── Raised / elevated — only when NOT negated ────────────────────────────
    _raised_kws = ["raised", "elevated", "bump", "bumps", "welt", "swelling",
                   "protrude", "papule", "nodule", "lump"]
    raised = _any_word(_raised_kws) and not _negated("raised") and not _negated("bumps")

    # ── Sharply defined red border — compound phrases only ───────────────────
    red_border = _any_word([
        "sharp border", "sharp edge", "sharp margin", "defined border",
        "defined margin", "sharply defined", "well-defined", "well defined",
        "well-defined margin", "demarcated", "circumscribed", "clear border",
        "distinct border", "distinct margin",
    ])

    # ── Pustules / pus / white-tipped ────────────────────────────────────────
    pustules = (_any_word([
        "pustule", "pustules", "pus-filled", "whitehead", "whiteheads",
        "white tip", "white-tip", "yellow tip", "yellow-tip",
        "white bump", "white dot", "white-headed",
    ]) and not (_negated("pustule") or _negated("pustules") or _negated("whitehead"))
    ) or (_word("pus") and not _negated("pus"))

    # ── Ring / annular pattern ────────────────────────────────────────────────
    ring_pattern = _any_word([
        "ring", "ring-shaped", "circular", "annular", "central clearing",
        "central clear",
    ]) and not (_negated("ring") or _negated("ring shape") or _negated("circular") or _negated("annular"))

    # ── Large bumps / welts (hives ≥5mm) ─────────────────────────────────────
    large_bumps = _any_word([
        "large bump", "large welt", "large raised", "big bump",
        "welt", "wheal",
    ])

    # ── Tiny uniform dots (heat rash, 1-3mm) ─────────────────────────────────
    tiny_uniform = _any_word([
        "tiny dot", "tiny dots", "pinpoint", "sandpaper",
        "uniform dots", "hundreds of", "numerous tiny", "many tiny",
        "fine dots", "prickly heat",
    ])

    # ── Oily / greasy surface ─────────────────────────────────────────────────
    oily = _any_word(["oily", "greasy", "sebaceous"])

    return {
        "location":    location,
        "scaling":     scaling,
        "thick_crust": thick_crust,
        "raised":      raised,
        "red_border":  red_border,
        "pustules":    pustules,
        "ring_pattern":ring_pattern,
        "large_bumps": large_bumps,
        "tiny_uniform":tiny_uniform,
        "oily":        oily,
        "_description": text,   # preserved for logging / downstream use
    }


# ─────────────────────────────────────────────────────────────────────────────
# D2C Step 2 — Rule-based classifier
# Rules derived from the same differential logic used in the Gemini pipeline.
# ─────────────────────────────────────────────────────────────────────────────

def _d2c_classify(f: Dict):
    """
    Map extracted visual features to a diagnosis using deterministic rules.
    Returns (condition: str, confidence: int, severity: str).

    Rule priority (high → low):
        1. Scalp conditions (location = scalp)
        2. Ring / fungal pattern
        3. Foot / groin location
        4. Heat Rash (tiny uniform dots)
        5. Hives (large raised smooth welts)
        6. Pustule-based conditions (acne, folliculitis, razor bumps)
        7. Scaling-based conditions (psoriasis body, eczema, contact dermatitis)
        8. Dry skin / normal fallback
    """
    loc  = f.get("location", "other")
    scal = f.get("scaling", False)
    thck = f.get("thick_crust", False)
    rais = f.get("raised", False)
    rbor = f.get("red_border", False)
    pust = f.get("pustules", False)
    ring = f.get("ring_pattern", False)
    lrge = f.get("large_bumps", False)
    tiny = f.get("tiny_uniform", False)
    oily = f.get("oily", False)

    # ── 1. SCALP ─────────────────────────────────────────────────────────────
    # Key differentials: Psoriasis vs Dandruff vs Scalp Folliculitis
    # Psoriasis: thick adherent silvery plaques + defined red border
    # Dandruff: fine loose flakes on oily scalp, no raised patches
    # Folliculitis: pustules on hair follicles
    if loc == "scalp":
        if pust:
            return "Scalp Folliculitis", 84, "mild"
        if scal and thck and rbor:
            return "Psoriasis (mild forms)", 88, "moderate"
        if scal and thck:
            return "Psoriasis (mild forms)", 81, "moderate"
        if scal and oily:
            return "Dandruff (Seborrheic Dermatitis)", 85, "mild"
        if scal:
            # Scaling without oiliness leans psoriasis on scalp
            return "Psoriasis (mild forms)", 73, "moderate"
        return "Dandruff (Seborrheic Dermatitis)", 67, "mild"

    # ── 2. RING PATTERN → FUNGAL ─────────────────────────────────────────────
    # Ringworm: ring with central clearing, scaly raised border
    # Athlete's Foot: between/under toes, scaling/maceration
    # Jock Itch: groin/inner thighs, ring-shaped edge
    if ring:
        if loc == "foot":
            return "Athlete's Foot", 89, "mild"
        if loc == "groin":
            return "Jock Itch", 86, "mild"
        return "Fungal Infections (Ringworm, Athlete's Foot)", 86, "mild"

    # ── 3. FOOT ──────────────────────────────────────────────────────────────
    # Athlete's Foot: white scaly peeling skin, maceration between toes
    if loc == "foot":
        if scal:
            return "Athlete's Foot", 85, "mild"
        if rais and lrge:
            return "Hives (Urticaria)", 74, "moderate"
        return "Athlete's Foot", 72, "mild"

    # ── 4. GROIN ─────────────────────────────────────────────────────────────
    if loc == "groin":
        return "Jock Itch", 84, "mild"

    # ── 5. HEAT RASH ─────────────────────────────────────────────────────────
    # Tiny UNIFORM dots like sandpaper (1-3mm), 100+, NOT raised welts
    # Key differential vs Hives: Heat Rash = sandpaper texture; Hives = large welts
    if tiny and not lrge:
        return "Heat Rash (Prickly Heat)", 86, "mild"

    # ── 6. HIVES ─────────────────────────────────────────────────────────────
    # Large RAISED smooth welts (5-30mm), no pustules, no scaling
    # Key differential vs Heat Rash: Hives = individual large welts you can count
    # Key differential vs Folliculitis: Hives = smooth surface, not follicle-centered
    if rais and lrge and not pust and not scal:
        return "Hives (Urticaria)", 85, "moderate"
    if rais and lrge and not pust and scal and loc in ("arm", "leg", "back"):
        # Large raised + scaling on body = likely Contact Dermatitis or Psoriasis
        if rbor:
            return "Contact Dermatitis", 76, "moderate"
        return "Psoriasis (mild forms)", 73, "moderate"

    # ── 7. MOSQUITO BITES ────────────────────────────────────────────────────
    # Few scattered bumps on exposed skin (arms, legs) — not Hives scale
    if rais and not lrge and not pust and not scal and loc in ("arm", "leg"):
        return "Mosquito Bite Reactions", 72, "mild"

    # ── 8. PUSTULE-BASED CONDITIONS ──────────────────────────────────────────
    # Acne: face/chest/back, mix of comedones + pustules, random distribution
    # Folliculitis: pustules centered on follicles, hair-bearing areas
    # Razor Bumps: neck/jawline shaved areas, ingrown hair pattern
    if pust:
        if loc == "neck":
            # Neck + pustules + raised → Razor Bumps (shaved area pattern)
            return "Razor Bumps (Pseudofolliculitis Barbae)", 80, "mild"
        if loc in ("face", "back", "chest"):
            return "Acne", 84, "mild"
        if loc in ("arm", "leg"):
            # Folliculitis pattern on hair-bearing limbs
            return "Scalp Folliculitis", 74, "mild"
        # Generic pustular on other locations
        return "Acne", 71, "mild"

    # ── 9. SCALING-BASED CONDITIONS (no pustules) ────────────────────────────
    if scal:
        # Body psoriasis: thick adherent plaques, sharp red border, extensor surfaces
        if thck and rbor:
            return "Psoriasis (mild forms)", 84, "moderate"
        if thck:
            return "Psoriasis (mild forms)", 77, "moderate"
        # Contact Dermatitis: sharp geometric border matching contact point
        if rbor and not thck and loc in ("arm", "neck", "face"):
            return "Contact Dermatitis", 75, "moderate"
        # Seborrheic Dermatitis on face (oily + scaling, not scalp)
        if oily and loc == "face":
            return "Dandruff (Seborrheic Dermatitis)", 76, "mild"
        # Eczema: diffuse borders, thin scales, dry or weeping, flexural
        if loc in ("arm", "leg"):
            return "Eczema (Atopic Dermatitis)", 76, "mild"
        # Dry skin: scaling without inflammation on face/other
        if not rais and not rbor and loc in ("face", "other"):
            return "Dry Skin (Xerosis)", 72, "mild"
        return "Eczema (Atopic Dermatitis)", 70, "mild"

    # ── 10. CONTACT DERMATITIS — red border without scaling ──────────────────
    # Sharp geometric border matching a contact point, not scaling-based
    if rbor and not scal and loc in ("arm", "neck", "face", "other"):
        return "Contact Dermatitis", 74, "moderate"

    # ── 11. FACE / NECK DEFAULTS ─────────────────────────────────────────────
    if loc == "face":
        if rais and not lrge:
            return "Acne", 70, "mild"
        if not rais and not scal:
            return "Dry Skin (Xerosis)", 67, "mild"
    if loc == "neck":
        if rais:
            return "Razor Bumps (Pseudofolliculitis Barbae)", 70, "mild"

    # ── 11. NORMAL / FALLBACK ────────────────────────────────────────────────
    return "Normal Skin", 68, "normal"


# ─────────────────────────────────────────────────────────────────────────────
# D2C result builders
# ─────────────────────────────────────────────────────────────────────────────

def _build_key_features(f: Dict, condition: str) -> list:
    parts = []
    if f.get("scaling"):
        parts.append("thick adherent scaling" if f.get("thick_crust") else "surface scaling/flaking")
    if f.get("red_border"):
        parts.append("sharply defined erythematous border")
    if f.get("raised"):
        parts.append("elevated/raised lesions" if not f.get("large_bumps") else "large raised welts")
    if f.get("pustules"):
        parts.append("follicular pustules")
    if f.get("ring_pattern"):
        parts.append("annular (ring-shaped) pattern with central clearing")
    if f.get("tiny_uniform"):
        parts.append("numerous uniform tiny papules (sandpaper texture)")
    if f.get("oily"):
        parts.append("seborrheic/oily skin surface")
    if not parts:
        parts.append(f"visual features consistent with {condition}")
    return parts[:4]


_CONDITION_DESCRIPTIONS = {
    "Psoriasis (mild forms)":             "Thick, silvery-white adherent plaques with sharply defined erythematous borders. Scales are dry and compacted, not loose.",
    "Dandruff (Seborrheic Dermatitis)":   "Fine white or yellowish flakes on an oily scalp surface. No raised plaques or defined red borders present.",
    "Scalp Folliculitis":                 "Small erythematous pustules centered on hair follicles at the scalp or hairline.",
    "Acne":                               "Mixed inflammatory lesions including papules, pustules, and comedones on sebaceous-dense areas.",
    "Hives (Urticaria)":                  "Raised smooth erythematous wheals (5-30mm), well-defined, appearing suddenly and blanching on pressure.",
    "Heat Rash (Prickly Heat)":           "Hundreds of tiny uniform erythematous papules (1-3mm) creating a sandpaper-like texture in sweat-prone areas.",
    "Eczema (Atopic Dermatitis)":         "Poorly-defined dry or weeping patches with fine scaling, often in flexural distribution.",
    "Contact Dermatitis":                 "Sharply delineated erythematous patch with geometric border corresponding to the contact area.",
    "Fungal Infections (Ringworm, Athlete's Foot)": "Annular lesion with raised scaly border and central clearing — classic dermatophyte pattern.",
    "Athlete's Foot":                     "White macerated scaling between toes or on sole, with possible fissuring and peeling.",
    "Jock Itch":                          "Ring-shaped erythematous patch with raised scaly margin in the groin or inner thighs.",
    "Razor Bumps (Pseudofolliculitis Barbae)": "Erythematous papules and pustules in a linear/grid pattern following shaved areas of the neck and jaw.",
    "Mosquito Bite Reactions":            "Scattered discrete erythematous wheals on exposed skin, each with a possible central punctum.",
    "Dry Skin (Xerosis)":                 "Diffuse fine scaling with roughness and tightness, no active inflammation or pustules.",
    "Normal Skin":                        "No visible lesions, redness, scaling, or inflammatory changes identified.",
}


def _build_description(condition: str, f: Dict) -> str:
    return _CONDITION_DESCRIPTIONS.get(
        condition,
        f"Visual presentation consistent with {condition} based on feature analysis.",
    )


def _build_reasoning(condition: str, f: Dict) -> str:
    active = [k for k, v in f.items() if k != "location" and v is True]
    loc = f.get("location", "unspecified")
    feat_str = ", ".join(active) if active else "general visual pattern"
    return (
        f"D2C pipeline: location={loc}, active features=[{feat_str}] → "
        f"rule-based classifier selected '{condition}'."
    )


_DIFFERENTIALS = {
    "Psoriasis (mild forms)":             ["Dandruff (Seborrheic Dermatitis)", "Eczema (Atopic Dermatitis)"],
    "Dandruff (Seborrheic Dermatitis)":   ["Psoriasis (mild forms)", "Scalp Folliculitis"],
    "Scalp Folliculitis":                 ["Dandruff (Seborrheic Dermatitis)", "Acne"],
    "Acne":                               ["Scalp Folliculitis", "Razor Bumps (Pseudofolliculitis Barbae)"],
    "Hives (Urticaria)":                  ["Heat Rash (Prickly Heat)", "Mosquito Bite Reactions"],
    "Heat Rash (Prickly Heat)":           ["Hives (Urticaria)", "Contact Dermatitis"],
    "Eczema (Atopic Dermatitis)":         ["Psoriasis (mild forms)", "Contact Dermatitis"],
    "Contact Dermatitis":                 ["Eczema (Atopic Dermatitis)", "Hives (Urticaria)"],
    "Fungal Infections (Ringworm, Athlete's Foot)": ["Eczema (Atopic Dermatitis)", "Contact Dermatitis"],
    "Athlete's Foot":                     ["Contact Dermatitis", "Eczema (Atopic Dermatitis)"],
    "Razor Bumps (Pseudofolliculitis Barbae)": ["Acne", "Scalp Folliculitis"],
    "Mosquito Bite Reactions":            ["Hives (Urticaria)", "Contact Dermatitis"],
}


def _build_differentials(condition: str) -> list:
    return _DIFFERENTIALS.get(condition, [])


_DISTINGUISHING = {
    "Psoriasis (mild forms)":           "Thick STUCK-ON silvery plaques with sharply defined red borders — distinguishes from dandruff's loose flakes.",
    "Dandruff (Seborrheic Dermatitis)": "Fine LOOSE flakes on oily scalp with NO raised plaques or defined borders — distinguishes from psoriasis.",
    "Hives (Urticaria)":                "Large SMOOTH welts (>5mm) that appear suddenly — distinguishes from heat rash's tiny sandpaper dots.",
    "Heat Rash (Prickly Heat)":         "Hundreds of TINY UNIFORM dots (1-3mm) like sandpaper — distinguishes from hives' large individual welts.",
    "Acne":                             "Comedones (blackheads/whiteheads) alongside pustules on sebaceous areas — distinguishes from folliculitis.",
    "Razor Bumps (Pseudofolliculitis Barbae)": "LINEAR pattern following razor strokes in shaved neck/jaw area — distinguishes from acne.",
    "Athlete's Foot":                   "White macerated scaling BETWEEN TOES — distinguishes from contact dermatitis by location.",
    "Eczema (Atopic Dermatitis)":       "DIFFUSE poorly-defined borders with thin fine scales — distinguishes from psoriasis's sharp thick plaques.",
    "Contact Dermatitis":               "GEOMETRIC/SHARP border matching contact point exactly — distinguishes from eczema's diffuse spread.",
}


def _build_distinguishing(condition: str, f: Dict) -> str:
    return _DISTINGUISHING.get(condition, "")


# ─────────────────────────────────────────────────────────────────────────────
# Legacy JSON parser (kept as dead code — no longer on primary path)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_edge_response(raw_content: str) -> Optional[Dict]:
    """
    Parse model response into a structured dict.
    Primary path: JSON parse.
    Fallback: extract fields from MiniCPM-V's narrative text format.
    """
    cleaned = raw_content.strip()

    # Strip markdown fences if present
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    # Extract JSON object if surrounded by text
    if "{" in cleaned:
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if end > start:
            json_candidate = cleaned[start:end]
            try:
                result = json.loads(json_candidate)
                condition = result.get("condition", "")
                # Reject placeholder/echo output — moondream sometimes returns
                # the literal prompt template text instead of classifying
                if condition and condition in SKIN_CONDITIONS:
                    confidence = result.get("confidence", 0)
                    if isinstance(confidence, str):
                        try:
                            confidence = int(confidence)
                        except ValueError:
                            confidence = 75
                    result["confidence"] = min(max(confidence, 0), 100)
                    return result
                elif condition:
                    logger.warning(
                        f"[EDGE] Rejected invalid condition from model: '{condition}' "
                        f"— not in SKIN_CONDITIONS"
                    )
                    return None
            except json.JSONDecodeError:
                pass  # fall through to narrative parser

    # ── Narrative fallback: extract fields from MiniCPM-V's numbered list format ──
    logger.info("[EDGE] JSON parse failed — attempting narrative extraction")
    return _extract_from_narrative(cleaned)


def _extract_from_narrative(text: str) -> Optional[Dict]:
    """
    Extract diagnosis from MiniCPM-V's natural language analysis format.
    Example: '1. Body Part: scalp  2. Lesions: raised plaques  3. Scale: thick silvery...'
    """
    import re

    text_lower = text.lower()

    # Find which condition is mentioned most prominently
    condition_hits = {}
    for cond in SKIN_CONDITIONS:
        # Match by full name or key words (e.g. "psoriasis", "dandruff")
        key = cond.split("(")[0].strip().lower()
        count = len(re.findall(r'\b' + re.escape(key.split()[0]) + r'\b', text_lower))
        if count > 0:
            condition_hits[cond] = count

    if not condition_hits:
        logger.warning("[EDGE] Narrative extraction: no condition matched")
        return None

    condition = max(condition_hits, key=condition_hits.get)

    # Severity
    severity = "mild"
    for s in ("severe", "moderate", "mild", "normal"):
        if s in text_lower:
            severity = s
            break

    # Key features from bold items in numbered lists: **Key**: value
    features = re.findall(r'\*\*([^*\n]+)\*\*[:\s]+([^\n*]+)', text)
    key_features = [f"{k.strip()}: {v.strip()}" for k, v in features[:3]]
    if not key_features:
        # Fallback: first three non-empty lines
        lines = [l.strip(" *1234567890.-") for l in text.split("\n") if len(l.strip()) > 20]
        key_features = lines[:3]

    # Affected area
    area_match = re.search(r'(?:location|area|body part)[^:]*:\s*([^\n.]+)', text, re.I)
    affected_area = area_match.group(1).strip() if area_match else "Not specified"

    # Confidence: explicit number or infer from language
    conf_match = re.search(r'(\d{2,3})\s*%', text)
    confidence = int(conf_match.group(1)) if conf_match else 78

    logger.info(f"[EDGE] Narrative extracted: {condition} ({confidence}%)")

    return {
        "condition": condition,
        "confidence": min(max(confidence, 0), 100),
        "severity": severity,
        "key_features": key_features,
        "affected_area": affected_area,
        "description": text[:300].replace("\n", " "),
        "reasoning": text[:500],
        "differential_diagnosis": [],
        "distinguishing_features": "",
        "border_type": "",
        "scale_type": "",
        "texture": "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Convert edge result to Gemini-compatible format
# ─────────────────────────────────────────────────────────────────────────────

def edge_result_to_gemini_format(edge_result: Dict) -> Dict:
    """
    Convert edge classifier output to the same format as detect_skin_disease_gemini().
    This allows the existing views.py pipeline to work unchanged.
    """
    condition = edge_result.get("condition", "Unknown")
    confidence = edge_result.get("confidence", 0)
    severity_raw = edge_result.get("severity", "mild").lower()
    description = edge_result.get("description", "")
    key_features = edge_result.get("key_features", [])
    affected_area = edge_result.get("affected_area", "Not specified")

    # Map confidence to text
    if confidence > 90:
        confidence_text = "Very High"
    elif confidence > 75:
        confidence_text = "High"
    elif confidence > 60:
        confidence_text = "Moderate"
    else:
        confidence_text = "Low"

    # Severity → urgency mapping (same as Gemini path)
    urgency_map = {
        "severe": ("Severe", "High", "⚠️ **URGENT:** This condition requires immediate medical attention."),
        "moderate": ("Moderate", "Moderate", "💡 Try home remedies, but consult a doctor if symptoms persist."),
        "mild": ("Mild", "Low", "✅ This can typically be managed with home remedies."),
        "normal": ("Normal", "None", "✅ Your skin appears healthy."),
    }
    severity, urgency, urgency_note = urgency_map.get(
        severity_raw, ("Mild", "Low", "✅ Try home remedies and monitor progress.")
    )

    # Low confidence → Normal Skin override (same as Gemini path)
    if condition.lower() != "normal skin" and confidence < CONFIDENCE_THRESHOLD:
        return None  # Signal caller to fall back to Gemini

    # Import CONDITION_REMEDIES from disease_detector
    try:
        from skin_analysis.disease_detector import CONDITION_REMEDIES
        remedies = CONDITION_REMEDIES.get(condition, [
            "Consult a healthcare professional for accurate diagnosis",
            "Maintain good hygiene",
            "Keep affected area clean and dry",
        ])
    except ImportError:
        remedies = ["Consult a healthcare professional"]

    # Build clinical reasoning — never expose model name
    raw_reasoning = edge_result.get("reasoning", "")
    raw_distinguishing = edge_result.get("distinguishing_features", "")
    if raw_reasoning:
        clinical_reasoning = raw_reasoning
    else:
        features_text = ", ".join(key_features[:3]) if key_features else "characteristic visual features"
        clinical_reasoning = (
            f"The visual presentation shows {features_text}, consistent with {condition}. "
            f"{description}"
        )

    return {
        "success": True,
        "disease": condition,
        "confidence": confidence_text,
        "confidence_score": confidence / 100,
        "severity": severity,
        "urgency": urgency,
        "description": description,
        "key_features": key_features,
        "affected_area": affected_area,
        "differential_diagnosis": edge_result.get("differential_diagnosis", []),
        "distinguishing_features": raw_distinguishing,
        "visual_analysis": {
            "border_type": edge_result.get("border_type", ""),
            "scale_type": edge_result.get("scale_type", ""),
            "texture": edge_result.get("texture", ""),
            "lesion_size": "",
            "lesion_count": "",
        },
        "measurements": {
            "num_lesions": 0,
            "avg_size_mm": 0,
            "size_category": "unknown",
            "uniformity": 0,
        },
        "reasoning": clinical_reasoning,
        "recommendations": remedies,
        "urgency_note": urgency_note,
        "accuracy": "ServVia Edge AI",
        "analyzed_by": f"servvia-edge-{_active_model or OLLAMA_MODEL}",
        "edge_inference_time": edge_result.get("edge_inference_time", 0),
    }
