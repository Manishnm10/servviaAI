"""
ServVia Edge — Local Skin Disease Classifier
==============================================

Uses Qwen3.5-2B via Ollama for on-device skin image analysis.
All processing runs locally — no image data leaves the user's machine.

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
OLLAMA_MODEL = "qwen3.5:2b"
EDGE_TIMEOUT = 45  # seconds — max wait for Ollama response
CONFIDENCE_THRESHOLD = 70  # below this → fall back to Gemini

# The 21 conditions the system recognizes
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
# Compact classification prompt — optimized for minimal output tokens
# ─────────────────────────────────────────────────────────────────────────────

_CONDITIONS_LIST = "\n".join(f"{i+1}. {c}" for i, c in enumerate(SKIN_CONDITIONS))

EDGE_CLASSIFICATION_PROMPT = f"""You are a dermatology classifier. Analyze this skin image and classify it.

ALLOWED CONDITIONS (pick EXACTLY one):
{_CONDITIONS_LIST}

DIFFERENTIATION RULES:
- Heat Rash: tiny 1mm dots, 100+, sandpaper texture, uniform
- Hives: raised welts 5-20mm, 10-40 bumps, individually visible → DEFAULT over Heat Rash if unsure
- Athlete's Foot: on FEET, peeling/scaly between toes
- Razor Bumps: on SHAVED areas (neck/jaw), ingrown hairs visible
- Folliculitis: bumps centered on hair follicles with pustules
- Mosquito Bites: few (3-10), scattered, exposed skin, central punctum
- Eczema: diffuse borders, thin scales, wet/oozing or very dry
- Psoriasis: thick plaques, silvery scales, sharp borders
- Contact Dermatitis: sharp geometric boundaries matching contact point

RESPOND WITH ONLY THIS JSON — no explanation, no markdown fences:
{{"condition":"exact name from list","confidence":0-100,"severity":"mild|moderate|severe|normal","key_features":["feature1","feature2","feature3"],"affected_area":"body part","description":"one sentence describing what you see"}}"""


# ─────────────────────────────────────────────────────────────────────────────
# Ollama health check
# ─────────────────────────────────────────────────────────────────────────────

def is_ollama_available() -> bool:
    """Check if Ollama is running and the model is loaded."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        if resp.status_code != 200:
            return False
        models = resp.json().get("models", [])
        available = any(
            OLLAMA_MODEL.split(":")[0] in m.get("name", "")
            for m in models
        )
        if not available:
            logger.warning(
                f"Ollama running but {OLLAMA_MODEL} not found. "
                f"Available: {[m['name'] for m in models]}"
            )
        return available
    except Exception:
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
    if not is_ollama_available():
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
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "user",
                "content": EDGE_CLASSIFICATION_PROMPT,
                "images": [image_b64],
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 200,  # cap output tokens — JSON response is ~120 tokens
            "num_ctx": 4096,     # smaller context window for speed
        },
        # Disable thinking mode to get response in content field
        "think": False,
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

        # Qwen3.5 bug workaround: response may be in 'thinking' instead of 'content'
        raw_content = message.get("content", "")
        if not raw_content or not raw_content.strip():
            raw_content = message.get("thinking", "")
            if raw_content:
                logger.info("[EDGE] Used 'thinking' field (Qwen3.5 vision bug workaround)")

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


def _parse_edge_response(raw_content: str) -> Optional[Dict]:
    """Parse JSON from Qwen3.5 response, handling common formatting issues."""
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
            cleaned = cleaned[start:end]

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"[EDGE] Failed to parse JSON: {e}\nRaw: {cleaned[:300]}")
        return None

    # Validate required fields
    condition = result.get("condition", "")
    confidence = result.get("confidence", 0)

    if not condition:
        logger.warning("[EDGE] No condition in response")
        return None

    # Ensure confidence is numeric
    if isinstance(confidence, str):
        try:
            confidence = int(confidence)
        except ValueError:
            confidence = 50

    result["confidence"] = min(max(confidence, 0), 100)
    return result


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
        "differential_diagnosis": [],
        "distinguishing_features": "",
        "visual_analysis": {
            "border_type": "",
            "scale_type": "",
            "texture": "",
            "lesion_size": "",
            "lesion_count": "",
        },
        "measurements": {
            "num_lesions": 0,
            "avg_size_mm": 0,
            "size_category": "unknown",
            "uniformity": 0,
        },
        "reasoning": f"Edge AI ({OLLAMA_MODEL}) classified as {condition} with {confidence}% confidence.",
        "recommendations": remedies,
        "urgency_note": urgency_note,
        "accuracy": f"Edge AI ({OLLAMA_MODEL})",
        "analyzed_by": f"servvia-edge-{OLLAMA_MODEL}",
        "edge_inference_time": edge_result.get("edge_inference_time", 0),
    }
