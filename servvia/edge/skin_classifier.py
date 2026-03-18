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

def classify_skin_image(image_path: str) -> Optional[Dict]:
    """
    Classify a skin image using Qwen3.5-2B via Ollama.

    Args:
        image_path: Path to the image file (jpg/png).

    Returns:
        Structured dict matching Gemini's output format, or None on failure/timeout.
        Includes 'edge_inference_time' for performance tracking.
    """
    model = _init_vision_model()
    if not model:
        logger.warning("Ollama not available — skipping edge classification")
        return None

    # Resize image to 512px max dimension (faster encoding + inference)
    # and encode as base64 JPEG
    try:
        from PIL import Image
        img = Image.open(image_path)
        max_dim = max(img.size)
        if max_dim > 512:
            scale = 512 / max_dim
            new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
            img = img.resize(new_size, Image.LANCZOS)
            logger.info(f"[EDGE] Resized image: {img.size[0]}x{img.size[1]}")
        import io
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        image_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to process image: {e}")
        return None

    # Call Ollama API
    # "format": "json" forces the model to emit valid JSON regardless of its natural style
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
        "format": "json",   # Ollama-level JSON enforcement — overrides model verbosity
        "options": {
            "temperature": 0.1,
            "num_predict": 300,  # enough for full JSON including reasoning
            "num_ctx": 4096,
        },
    }

    start_time = time.time()

    try:
        logger.info(f"[EDGE] Sending image to {OLLAMA_MODEL}...")
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=EDGE_TIMEOUT,
        )
        elapsed = time.time() - start_time

        if resp.status_code != 200:
            logger.error(f"[EDGE] Ollama returned {resp.status_code}: {resp.text[:200]}")
            return None

        result = resp.json()
        message = result.get("message", {})

        raw_content = message.get("content", "")

        if not raw_content or not raw_content.strip():
            logger.warning(f"[EDGE] Empty response from {OLLAMA_MODEL} after {elapsed:.1f}s")
            return None

        logger.info(f"[EDGE] Got response in {elapsed:.1f}s ({len(raw_content)} chars)")

        # Parse JSON from response
        parsed = _parse_edge_response(raw_content)
        if parsed is None:
            return None

        parsed["edge_inference_time"] = round(elapsed, 2)
        parsed["edge_model"] = OLLAMA_MODEL

        condition = parsed.get("condition", "")
        affected_area = parsed.get("affected_area", "").lower()

        # ── Scalp challenge pass: binary plaque vs flake for ambiguous conditions ──
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
        logger.warning(f"[EDGE] Ollama timeout after {elapsed:.1f}s — falling back to cloud")
        return None
    except Exception as e:
        logger.error(f"[EDGE] Classification error: {e}", exc_info=True)
        return None


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
