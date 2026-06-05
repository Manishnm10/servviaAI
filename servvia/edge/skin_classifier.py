"""
ServVia Edge — Local Skin Disease Classifier
==============================================

Uses MiniCPM-V 2.6 (8B) via Ollama for on-device skin image analysis.
All processing runs locally — no image data leaves the user's machine.

Model preference order (first available in Ollama wins):
    minicpm-v → llama3.2-vision → llava:13b → llava:7b → llava → ...

Pipeline position:
    [Image Upload] -> [Local Validation] -> ** THIS CLASSIFIER ** -> Structured JSON

Fallback:
    If edge confidence < threshold OR timeout → Gemini cloud fallback
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
OLLAMA_MODEL = "minicpm-v"           # default; auto-upgraded if better model found
EDGE_TIMEOUT = 120                   # allow cold-start load time (8B model ~5.5GB)
CONFIDENCE_THRESHOLD = 65

# Vision models in order of dermatology accuracy — first available wins
_PREFERRED_VISION_MODELS = [
    "minicpm-v",         # MiniCPM-V 2.6 8B — primary model
    "llama3.2-vision",   # excellent visual understanding
    "llava:13b",         # high accuracy, larger
    "llava:7b",          # good balance
    "llava",             # default llava tag
    "llava-phi3",        # small but dedicated vision
    "moondream",         # minimal but vision-native
    "bakllava",          # vision-tuned
]

# Selected model — set by _init_vision_model() on first call
_active_model: Optional[str] = None

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
# Dermatologist-grade classification prompt
# ─────────────────────────────────────────────────────────────────────────────

_CONDITIONS_LIST = "\n".join(f"{i+1}. {c}" for i, c in enumerate(SKIN_CONDITIONS))

EDGE_CLASSIFICATION_PROMPT = f"""You are an expert dermatologist AI. Analyze this skin image with clinical precision.

ALLOWED CONDITIONS — pick EXACTLY ONE:
{_CONDITIONS_LIST}

CRITICAL DIFFERENTIALS — read before deciding:

SCALP (if scalp/hairline visible):
- PSORIASIS (mild forms): THICK RAISED adherent silvery-white PLAQUES. Signs: sharply demarcated RED borders, plaques extend beyond hairline onto forehead/ears/neck, reddish inflamed skin around plaques, scales are DRY and SILVERY (not greasy). → Pick PSORIASIS if you see raised plaques with defined red borders.
- DANDRUFF: Fine LOOSE white/yellowish flakes that fall off easily. Signs: greasy/oily scalp appearance, NO raised plaques, NO sharp red borders, diffuse distribution within hairline. → Pick DANDRUFF if you see loose flakes on oily scalp without plaques.
- SCALP FOLLICULITIS: Small red pustules on individual hair follicles, pus tips visible.

INFLAMMATORY:
- ECZEMA: Poorly defined patches, intensely dry or weeping/crusted, thin fine scales, flexural areas (inner elbows, behind knees).
- PSORIASIS (body): Thick silvery plaques, SHARP red borders, extensor surfaces (elbows, knees).
- CONTACT DERMATITIS: Sharp geometric/linear border matching contact area, blistering.
- HIVES: Raised smooth wheals 5-30mm, well-defined, blanch on pressure, anywhere on body.
- HEAT RASH: 1-3mm uniform tiny red dots (100+), sandpaper texture, in hot/sweaty skin folds.

ACNE-LIKE:
- ACNE: Mix of comedones (blackheads/whiteheads) + papules + pustules, face/chest/back.
- FOLLICULITIS: ONLY pustules centered on hair follicles, no comedones.
- RAZOR BUMPS: In shaved areas (neck/jaw), ingrown hairs visible, linear pattern.

INFECTIONS:
- RINGWORM: Ring-shaped with clearing in center, scaly raised border.
- ATHLETE'S FOOT: Between/under toes, white macerated peeling skin.
- JOCK ITCH: Groin/inner thighs, ring-shaped edge, not on scrotum.
- COLD SORES: Clustered blisters on/around lips, honey-crusted.
- WARTS: Rough cauliflower-like surface, on hands/feet.

NORMAL SKIN: No visible lesions, redness, scaling, or inflammation.

ANALYSIS STEPS:
1. Identify body part / location
2. Note if lesions are RAISED or flat
3. Check scale type: thick/silvery vs thin/fine vs greasy/loose
4. Check borders: sharp/defined vs diffuse/poorly-defined
5. Count lesions and estimate size
6. Make diagnosis

RESPOND WITH ONLY THIS JSON (no markdown, no extra text):
{{"condition":"exact name from list","confidence":0-100,"severity":"mild|moderate|severe|normal","key_features":["feature1","feature2","feature3"],"affected_area":"body part","description":"2 sentences: what you see clinically.","reasoning":"Why this condition and NOT the most similar alternative. Reference specific visual features.","differential_diagnosis":["alt1","alt2"],"distinguishing_features":"key feature separating this from alternatives","border_type":"sharp/defined OR diffuse/poorly-defined","scale_type":"thick/silvery OR thin/fine OR loose/greasy OR none","texture":"flat OR raised OR plaque-like"}}"""

# ─── Simplified prompt for small models (moondream, llava-phi3, etc.) ─────
# These models can't handle complex multi-step prompts or large JSON schemas.
# Two-pass approach: Pass 1 = describe what you see, Pass 2 = deterministic mapping.

_SMALL_MODEL_DESCRIBE_PROMPT = (
    "Describe what you see on this skin in detail. Include the body part, skin color, "
    "texture, any bumps, spots, patches, rashes, redness, scales, flakes, or swelling, "
    "and the overall pattern."
)

# Ultra-short retry prompt for when the primary prompt yields empty output.
# Moondream often produces 0 tokens for multi-clause prompts but answers simple questions.
_SMALL_MODEL_RETRY_PROMPTS = [
    "What do you see on this skin?",
    "Describe this image.",
]

# Models that need the simplified two-pass approach (base name matching)
_SMALL_MODELS = {"moondream", "llava-phi3"}

# Models that must skip /api/chat and go straight to /api/generate for vision
# (moondream returns empty content via chat but works correctly via generate)
_GENERATE_ONLY_MODELS = {"moondream"}

# Keyword → condition mapping for deterministic classification from descriptions
_KEYWORD_CONDITION_MAP = [
    # Order matters: more specific patterns first
    (["ring", "circular", "center clear"], "Fungal Infections (Ringworm, Athlete's Foot)"),
    (["between toes", "toe", "macerat", "peeling between"], "Athlete's Foot"),
    (["groin", "inner thigh", "jock"], "Jock Itch"),
    (["blister", "lip", "cold sore", "herpes", "cluster", "mouth"], "Cold Sores"),
    (["wart", "cauliflower", "rough bump", "verruca"], "Warts (Common Warts)"),
    (["razor", "shav", "ingrown", "neck bump"], "Razor Bumps (Pseudofolliculitis Barbae)"),
    (["ingrown hair"], "Ingrown Hairs"),
    (["mosquito", "insect bite", "bug bite"], "Mosquito Bite Reactions"),
    (["chapped lip", "dry lip", "cracked lip"], "Chapped Lips"),
    (["silvery", "plaque", "thick scale", "psoriasis", "white scale",
      "white patch", "scaly patch", "rough patch"], "Psoriasis (mild forms)"),
    (["dandruff", "flak", "scalp flak", "greasy scalp", "white flake",
      "dry flake"], "Dandruff (Seborrheic Dermatitis)"),
    (["follicul", "pustule", "hair follicle", "scalp bump"], "Scalp Folliculitis"),
    (["hive", "wheal", "welt", "urticaria", "raised welt"], "Hives (Urticaria)"),
    (["heat rash", "prickly", "tiny red dot", "sweat rash", "miliaria"], "Heat Rash (Prickly Heat)"),
    (["eczema", "atopic", "weeping", "crusted patch", "flexural"], "Eczema (Atopic Dermatitis)"),
    (["contact", "geometric", "linear rash", "blister rash"], "Contact Dermatitis"),
    (["sunburn", "sun burn", "peeling skin", "sun damage"], "Sunburn"),
    (["acne", "pimple", "blackhead", "whitehead", "comedone", "zit"], "Acne"),
    (["fungal", "fungus", "ringworm", "tinea"], "Fungal Infections (Ringworm, Athlete's Foot)"),
    (["dry skin", "xerosis", "flaky dry", "cracked skin", "scaly dry"], "Dry Skin (Xerosis)"),
    (["allerg", "rash", "red bump", "itchy bump"], "Allergic Rash (Mild Allergic Dermatitis)"),
    # Broad visual patterns as last resort
    (["red patch", "inflam", "irritat"], "Eczema (Atopic Dermatitis)"),
    (["bump", "raised", "papule"], "Acne"),
    (["scale", "scaly", "flak"], "Dry Skin (Xerosis)"),
    (["normal", "healthy", "clear skin", "no lesion", "no rash"], "Normal Skin"),
]


def _is_small_model(model_name: str) -> bool:
    """Check if the active model needs the simplified prompt path."""
    name_lower = model_name.lower()
    return any(sm in name_lower for sm in _SMALL_MODELS)


def _classify_from_description(description: str) -> Dict:
    """
    Deterministic classification: map a natural-language skin description
    to one of the supported conditions using keyword matching with
    region-aware scoring boosts.
    """
    desc_lower = description.lower()

    # ── Region detection ──────────────────────────────────────────────
    # Word-boundary matching so "head" doesn't match "forehead" and
    # "hair" doesn't match "eyelash/eyebrow/facial hair".
    import re as _re
    has_scalp_word = bool(_re.search(r"\b(?:scalp|hairline|crown)\b", desc_lower))
    has_hair_context = bool(_re.search(
        r"\b(?:their|the|your|his|her) hair\b|"
        r"\bhair (?:visible|is|appears|above|at the|styled|on top|on the head)\b|"
        r"\bflaky scalp\b|\bgreasy hair\b|\boily hair\b|\bdry hair\b",
        desc_lower,
    ))
    on_scalp = has_scalp_word or has_hair_context

    # Face includes forehead, cheek, nose, chin, jaw, eye area.
    on_face = any(w in desc_lower for w in (
        "face", "forehead", "cheek", "chin", "jaw", "nose",
        "eyebrow", "eyelid", "under the eye", "t-zone",
    )) and not on_scalp

    # Scaly/flaky cues (classic psoriasis/dandruff vocabulary).
    scaly_feature = any(w in desc_lower for w in (
        "scale", "scaly", "flak", "rough texture", "rough patch",
        "dry patch", "white patch", "white bump", "silver",
        "white spot", "white dot", "white mark", "dry skin",
        "crust", "peel",
    ))
    # Pimple/acne cues (clinical or lay language for multiple small bumps).
    pimple_feature = any(w in desc_lower for w in (
        "pimple", "whitehead", "blackhead", "zit", "comedone",
        "pustule", "papule",
    ))
    multiple_bumps = any(phrase in desc_lower for phrase in (
        "bumps scattered", "many bumps", "several bumps", "multiple bumps",
        "numerous bumps", "tiny bumps", "small bumps", "cluster of bumps",
        "bumps across", "bumps all over", "red bumps", "small skin growth",
        "skin growths",
    ))
    generic_skin_issue = any(w in desc_lower for w in (
        "spot", "patch", "mark", "bump", "rash", "red", "dry",
        "white", "rough", "flak", "scale", "crust", "peel",
    ))

    # ── Scoring ──────────────────────────────────────────────────────
    best_condition = "Normal Skin"
    best_score = 0.0
    best_keywords = []

    for keywords, condition in _KEYWORD_CONDITION_MAP:
        score = float(sum(1 for kw in keywords if kw in desc_lower))

        # Scalp region boosts
        if on_scalp and scaly_feature:
            if condition.startswith("Psoriasis"):
                score += 2.0
            elif condition.startswith("Dandruff"):
                score += 1.5
            elif condition.startswith("Allergic Rash") or condition == "Acne":
                score -= 1.0
        elif on_scalp and generic_skin_issue:
            if condition.startswith("Psoriasis"):
                score += 1.2
            elif condition.startswith("Dandruff"):
                score += 1.0
            elif condition.startswith("Scalp Folliculitis"):
                score += 0.8
            elif condition.startswith("Allergic Rash") or condition == "Acne":
                score -= 0.5

        # Face region boosts: face + (pimples OR multiple small bumps) → Acne
        if on_face and (pimple_feature or multiple_bumps):
            if condition == "Acne":
                score += 2.0
            elif condition.startswith("Allergic Rash"):
                score -= 0.8
        elif on_face and generic_skin_issue:
            # Face + vague abnormality: small nudge to Acne, penalize
            # generic Allergic Rash so it doesn't win with just "rash" keyword.
            if condition == "Acne":
                score += 0.5
            elif condition.startswith("Allergic Rash"):
                score -= 0.3

        if score > best_score:
            best_score = score
            best_condition = condition
            best_keywords = [kw for kw in keywords if kw in desc_lower]

    # Defaults when scoring produces nothing meaningful.
    if best_score <= 0:
        if on_scalp and (scaly_feature or generic_skin_issue):
            best_condition = "Psoriasis (mild forms)"
            best_score = 1.0
            best_keywords = ["scalp", "abnormal mark"]
        elif on_face and (pimple_feature or multiple_bumps):
            best_condition = "Acne"
            best_score = 1.0
            best_keywords = ["face", "multiple bumps"]

    # Confidence based on match strength
    if best_score >= 3:
        confidence = 85
    elif best_score >= 2:
        confidence = 78
    elif best_score >= 1:
        confidence = 70
    else:
        confidence = 50

    # Severity from description keywords
    severity = "mild"
    if any(w in desc_lower for w in ["severe", "intense", "spreading", "large area", "painful"]):
        severity = "severe"
    elif any(w in desc_lower for w in ["moderate", "noticeable", "inflamed", "swollen"]):
        severity = "moderate"
    elif any(w in desc_lower for w in ["normal", "healthy", "clear"]):
        severity = "normal"

    # Extract key features: sentences containing matched keywords
    sentences = [s.strip() for s in description.replace("\n", ". ").split(".") if len(s.strip()) > 10]
    key_features = []
    for s in sentences[:5]:
        s_lower = s.lower()
        if any(kw in s_lower for kw in best_keywords) or any(
            w in s_lower for w in ["red", "bump", "rash", "scale", "dry", "patch", "blister", "itch"]
        ):
            key_features.append(s.strip())
        if len(key_features) >= 3:
            break
    if not key_features:
        key_features = sentences[:3]

    # Extract affected area. Priority order matters: scalp/hairline/forehead
    # should beat generic "back" when the description mentions hair — moondream
    # often says "back of the neck" which naive regex picks up as "back".
    import re
    # Strip phrases that use anatomy prepositionally (e.g., "back of their neck").
    area_search_text = re.sub(r"\bback of\b", "", desc_lower)

    priority_areas = [
        "scalp", "hairline", "forehead", "face", "cheek", "nose", "lip",
        "neck", "shoulder", "chest", "torso", "back", "stomach",
        "arm", "elbow", "wrist", "hand", "finger",
        "leg", "thigh", "knee", "shin", "foot", "feet", "toe", "groin",
    ]
    affected_area = "Not specified"
    if on_scalp:
        # Strong signal already — prefer scalp/forehead over generic body parts.
        for candidate in ("scalp", "hairline", "forehead", "head"):
            if candidate in area_search_text:
                affected_area = "Scalp" if candidate in ("scalp", "hairline", "head") else candidate.title()
                break
    if affected_area == "Not specified":
        for candidate in priority_areas:
            if re.search(rf"\b{candidate}\b", area_search_text):
                affected_area = candidate.title()
                break

    logger.info(
        f"[EDGE] Description-based classification: {best_condition} "
        f"(score={best_score}, confidence={confidence}%, keywords={best_keywords})"
    )

    return {
        "condition": best_condition,
        "confidence": confidence,
        "severity": severity,
        "key_features": key_features,
        "affected_area": affected_area,
        "description": description[:300].replace("\n", " "),
        "reasoning": f"Visual description matched {len(best_keywords)} indicator(s) for {best_condition}: {', '.join(best_keywords)}. {description[:200]}",
        "differential_diagnosis": [],
        "distinguishing_features": "",
        "border_type": "",
        "scale_type": "",
        "texture": "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Ollama health check
# ─────────────────────────────────────────────────────────────────────────────

def _init_vision_model() -> Optional[str]:
    """
    Query Ollama for available models and return the best vision model name.
    Preference order defined in _PREFERRED_VISION_MODELS.
    """
    global _active_model
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        if resp.status_code != 200:
            return None
        available = [m.get("name", "") for m in resp.json().get("models", [])]
        if not available:
            return None

        for preferred in _PREFERRED_VISION_MODELS:
            base = preferred.split(":")[0].lower()
            tag = preferred.split(":")[1] if ":" in preferred else None
            for name in available:
                name_lower = name.lower()
                # Match base name; if tag specified, match it too
                if base in name_lower and (tag is None or tag in name_lower):
                    if _active_model != name:
                        logger.info(f"[EDGE] Selected vision model: {name}")
                        _active_model = name
                    return name

        logger.warning(f"[EDGE] No preferred vision model found. Available: {available}")
        return None
    except Exception:
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

def _encode_image(image_path: str) -> Optional[str]:
    """Resize image to 512px max and return base64-encoded JPEG."""
    try:
        from PIL import Image
        import io
        img = Image.open(image_path)
        max_dim = max(img.size)
        if max_dim > 512:
            scale = 512 / max_dim
            new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
            img = img.resize(new_size, Image.LANCZOS)
            logger.info(f"[EDGE] Resized image: {img.size[0]}x{img.size[1]}")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to process image: {e}")
        return None


def _describe_via_generate(model: str, image_b64: str, timeout: int) -> Optional[str]:
    """
    Description via /api/generate. Tries the detailed prompt first, then falls
    back to progressively simpler prompts on empty response — small vision models
    (especially moondream) sometimes emit 0 tokens on multi-clause prompts.
    """
    prompts_to_try = [_SMALL_MODEL_DESCRIBE_PROMPT] + _SMALL_MODEL_RETRY_PROMPTS
    deadline = time.time() + timeout

    for attempt, prompt in enumerate(prompts_to_try, 1):
        remaining = int(deadline - time.time())
        if remaining <= 5:
            break
        try:
            resp = httpx.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "images": [image_b64],
                    "stream": False,
                    # No temperature override — use model defaults; moondream is
                    # sensitive to low temps on complex prompts.
                    "options": {"num_predict": 256, "num_ctx": 2048},
                },
                timeout=remaining,
            )
            if resp.status_code != 200:
                logger.warning(
                    "[EDGE] /api/generate attempt %d HTTP %d: %s",
                    attempt, resp.status_code, resp.text[:200],
                )
                continue

            content = resp.json().get("response", "").strip()
            if content:
                logger.info(
                    "[EDGE] /api/generate attempt %d succeeded (%d chars, prompt=%r)",
                    attempt, len(content), prompt[:40] + "...",
                )
                return content

            logger.warning(
                "[EDGE] /api/generate attempt %d returned empty (prompt=%r) — retrying with simpler prompt",
                attempt, prompt[:40] + "...",
            )
        except httpx.TimeoutException:
            logger.warning("[EDGE] /api/generate attempt %d timed out", attempt)
            break
        except Exception as e:
            logger.warning("[EDGE] /api/generate attempt %d error: %s", attempt, e)
            continue

    return None


def _classify_small_model(model: str, image_b64: str) -> Optional[Dict]:
    """
    Two-pass classification for small vision models (moondream, llava-phi3).

    Pass 1: Ask the model to describe what it sees (simple open-ended prompt).
            Tries /api/chat first; falls back to /api/generate if content is empty
            (moondream returns empty content via chat but works via generate).
    Pass 2: Deterministically map the description to a supported condition.
    """
    start_time = time.time()

    raw_content = None
    model_base = model.split(":")[0].lower()

    # Pass 1a: try /api/chat (skipped for models known to return empty via chat)
    if model_base not in _GENERATE_ONLY_MODELS:
        try:
            logger.info(f"[EDGE] Small model path — asking {model} to describe skin image...")
            resp = httpx.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": _SMALL_MODEL_DESCRIBE_PROMPT,
                            "images": [image_b64],
                        },
                    ],
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 300, "num_ctx": 2048},
                },
                timeout=EDGE_TIMEOUT,
            )
            elapsed = time.time() - start_time

            if resp.status_code == 200:
                raw_content = resp.json().get("message", {}).get("content", "").strip()
                if not raw_content:
                    logger.warning(
                        f"[EDGE] chat returned empty after {elapsed:.1f}s — retrying via /api/generate"
                    )
            else:
                logger.error(f"[EDGE] Ollama /api/chat returned {resp.status_code}: {resp.text[:200]}")

        except httpx.TimeoutException:
            elapsed = time.time() - start_time
            logger.warning(f"[EDGE] /api/chat timed out after {elapsed:.1f}s")
        except Exception as e:
            logger.error(f"[EDGE] /api/chat error: {e}", exc_info=True)
    else:
        logger.info(f"[EDGE] {model} uses /api/generate directly (skipping chat)")

    # Pass 1b: /api/generate — primary for moondream, fallback for others
    if not raw_content:
        remaining = max(30, EDGE_TIMEOUT - int(time.time() - start_time))
        raw_content = _describe_via_generate(model, image_b64, timeout=remaining)

    elapsed = time.time() - start_time

    if not raw_content:
        logger.warning(f"[EDGE] Both chat and generate returned empty after {elapsed:.1f}s")
        return None

    logger.info(f"[EDGE] Got description in {elapsed:.1f}s ({len(raw_content)} chars): {raw_content[:150]}...")

    # Pass 2: Deterministic keyword-based classification
    parsed = _classify_from_description(raw_content)
    parsed["edge_inference_time"] = round(elapsed, 2)
    parsed["edge_model"] = model

    logger.info(
        f"[EDGE] Classification: {parsed.get('condition', '?')} "
        f"({parsed.get('confidence', 0)}%) in {elapsed:.1f}s"
    )
    return parsed


def _classify_large_model(model: str, image_b64: str) -> Optional[Dict]:
    """
    Full structured classification for capable vision models (minicpm-v, llava, llama3.2-vision).
    Uses the detailed dermatology prompt with JSON output.
    """
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert dermatologist AI. You MUST respond ONLY with valid JSON. "
                    "Do not write any text outside the JSON object. Do not use markdown. "
                    "Start your response with { and end with }."
                ),
            },
            {
                "role": "user",
                "content": EDGE_CLASSIFICATION_PROMPT,
                "images": [image_b64],
            },
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
            "num_predict": 300,
            "num_ctx": 4096,
        },
    }

    start_time = time.time()

    try:
        logger.info(f"[EDGE] Sending image to {model}...")
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=EDGE_TIMEOUT,
        )
        elapsed = time.time() - start_time

        if resp.status_code != 200:
            logger.error(f"[EDGE] Ollama returned {resp.status_code}: {resp.text[:200]}")
            return None

        raw_content = resp.json().get("message", {}).get("content", "").strip()
        if not raw_content:
            logger.warning(f"[EDGE] Empty response from {model} after {elapsed:.1f}s")
            return None

        logger.info(f"[EDGE] Got response in {elapsed:.1f}s ({len(raw_content)} chars)")

        parsed = _parse_edge_response(raw_content)
        if parsed is None:
            return None

        parsed["edge_inference_time"] = round(elapsed, 2)
        parsed["edge_model"] = model

        condition = parsed.get("condition", "")
        affected_area = parsed.get("affected_area", "").lower()

        # Scalp challenge pass for ambiguous conditions
        if condition in _SCALP_AMBIGUOUS or "scalp" in affected_area:
            challenge = _challenge_scalp_condition(image_b64)
            logger.info(f"[EDGE] Scalp challenge result: {challenge!r} (condition was: {condition})")
            if challenge == "A" and "Psoriasis" not in condition:
                logger.info(f"[EDGE] Challenge override: {condition} → Psoriasis (mild forms)")
                parsed["condition"] = "Psoriasis (mild forms)"
                parsed["confidence"] = max(parsed.get("confidence", 70), 78)
                parsed["reasoning"] = (
                    "Visual challenge confirmed THICK RAISED silvery-white plaques with defined "
                    "reddish borders — characteristic of psoriasis, not the fine loose flakes of dandruff."
                )
            elif challenge == "B" and "Dandruff" not in condition:
                logger.info(f"[EDGE] Challenge override: {condition} → Dandruff (Seborrheic Dermatitis)")
                parsed["condition"] = "Dandruff (Seborrheic Dermatitis)"
                parsed["confidence"] = max(parsed.get("confidence", 70), 78)
                parsed["reasoning"] = (
                    "Visual challenge confirmed fine loose flakes without raised plaques or defined borders "
                    "— consistent with dandruff rather than psoriasis."
                )

        logger.info(
            f"[EDGE] Classification: {parsed.get('condition', '?')} "
            f"({parsed.get('confidence', 0)}%) in {elapsed:.1f}s"
        )
        return parsed

    except httpx.TimeoutException:
        elapsed = time.time() - start_time
        logger.warning(f"[EDGE] Ollama timeout after {elapsed:.1f}s")
        return None
    except Exception as e:
        logger.error(f"[EDGE] Classification error: {e}", exc_info=True)
        return None


def classify_skin_image(image_path: str) -> Optional[Dict]:
    """
    Classify a skin image using the best available Ollama vision model.

    Automatically selects the right strategy:
    - Small models (moondream, llava-phi3): two-pass describe→classify
    - Large models (minicpm-v, llava, llama3.2-vision): full structured JSON prompt

    Returns:
        Structured dict matching Gemini's output format, or None on failure/timeout.
    """
    model = _init_vision_model()
    if not model:
        logger.warning("Ollama not available — skipping edge classification")
        return None

    image_b64 = _encode_image(image_path)
    if not image_b64:
        return None

    if _is_small_model(model):
        logger.info(f"[EDGE] Using simplified two-pass path for small model: {model}")
        return _classify_small_model(model, image_b64)
    else:
        return _classify_large_model(model, image_b64)


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
                if condition:
                    confidence = result.get("confidence", 0)
                    if isinstance(confidence, str):
                        try:
                            confidence = int(confidence)
                        except ValueError:
                            confidence = 75
                    result["confidence"] = min(max(confidence, 0), 100)
                    return result
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
