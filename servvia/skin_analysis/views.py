import json
import queue
import threading
import time as _time

from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import SkinAnalysis
from .disease_detector import SkinDiseaseDetector, detect_skin_disease_gemini, validate_skin_image
from edge.skin_classifier import classify_skin_image, edge_result_to_gemini_format, is_ollama_available
import logging
import tempfile
import os
from PIL import Image
import io

logger = logging.getLogger(__name__)
detector = SkinDiseaseDetector()

# Import Trust Engine
try:
    from core_temporal.trust_engine.engine import TrustEngine
    TRUST_ENGINE_AVAILABLE = True
    trust_engine = TrustEngine()
    logger.info("✅ Trust Engine integrated with Skin Analysis")
except ImportError as e:
    TRUST_ENGINE_AVAILABLE = False
    trust_engine = None
    logger.warning(f"⚠️ Trust Engine not available: {e}")


@api_view(['POST'])
def analyze_skin_image(request):
    """Analyze skin image with Trust Engine validation"""
    temp_path = None

    try:
        email = request.data.get('email_id')
        if not email:
            return Response({'success': False, 'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'success': False, 'error': 'Image file is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Get user profile
        user_profile = get_user_profile(email)

        # Process image: convert to RGB and save temporarily
        try:
            image_data = image_file.read()
            image = Image.open(io.BytesIO(image_data))
            if image.mode != 'RGB':
                image = image.convert('RGB')
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                image.save(tmp.name)
                temp_path = tmp.name
        except Exception as e:
            logger.error(f"Image processing error: {e}")
            return Response({'success': False, 'error': 'Invalid image file.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate that it's actually a skin image
        validation = validate_skin_image(temp_path)
        if not validation['is_skin_image']:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            return Response({
                'success': False,
                'error': validation['reason'],
                'suggestion': 'Please upload a clear photograph of the affected skin area.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # ── Primary: Edge AI (Qwen3.5-2B via Ollama) ──
        result = None
        edge_used = False
        edge_raw = classify_skin_image(temp_path)
        if edge_raw is not None:
            result = edge_result_to_gemini_format(edge_raw)
            if result is not None:
                edge_used = True
                logger.info(f"[EDGE] Skin analysis via Moondream2: {result['disease']} ({edge_raw['confidence']}%) in {edge_raw.get('edge_inference_time', '?')}s")

        # ── Fallback: Gemini (cloud) ──
        if result is None:
            if edge_raw is not None:
                logger.info(f"[FALLBACK] Edge confidence too low ({edge_raw.get('confidence', 0)}%), using Gemini")
            else:
                logger.info("[FALLBACK] Edge unavailable, using Gemini")
            result = detect_skin_disease_gemini(temp_path)

        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass

        if not result.get('success'):
            return Response({'success': False, 'error': result.get('error', 'Unable to analyze image')},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        disease = result.get('disease', 'Unknown')
        confidence_score = result.get('confidence_score', 0.0)

        # Trust Engine validation (personalized remedies)
        trust_validation = None
        if TRUST_ENGINE_AVAILABLE and trust_engine:
            trust_validation = validate_skin_recommendations(disease, user_profile)
            logger.info(f"✅ Trust Engine validated recommendations for {disease}")

        # Build detailed human-readable report
        formatted_summary = build_detailed_skin_analysis(result, trust_validation, user_profile)

        # Save analysis to database
        image_file.seek(0)  # Reset file pointer for saving
        analysis = SkinAnalysis.objects.create(
            email_id=email,
            image=image_file,
            diagnosis=disease,
            confidence_score=confidence_score,
            recommendations=formatted_summary
        )

        return Response({
            'success': True,
            'diagnosis': disease,
            'confidence': round(confidence_score * 100, 2),
            'severity': result.get('severity', 'Unknown'),
            'description': result.get('description', ''),
            'recommendations': formatted_summary,
            'urgency_note': result.get('urgency_note', ''),
            'analysis_id': analysis.id,
            'visual_analysis': result.get('visual_analysis', {}),
            'distinguishing_features': result.get('distinguishing_features', ''),
            'differential_diagnosis': result.get('differential_diagnosis', []),
            'key_features': result.get('key_features', []),
            'trust_validation': trust_validation
        })

    except Exception as e:
        logger.error(f"Skin analysis error: {e}", exc_info=True)
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass
        return Response({'success': False, 'error': 'An unexpected error occurred.'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_user_profile(email):
    """Fetch user profile for personalization"""
    try:
        from user_profile.models import UserProfile
        profile = UserProfile.objects.filter(email=email).first()
        if profile:
            return {
                'first_name': profile.first_name or 'there',
                'allergies': parse_list(profile.allergies),
                'medical_conditions': parse_list(profile.medical_conditions),
                'current_medications': parse_list(profile.current_medications)
            }
    except Exception as e:
        logger.warning(f"Could not get profile: {e}")
    return {'first_name': 'there', 'allergies': [], 'medical_conditions': [], 'current_medications': []}


def parse_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(',') if item.strip()]
    return []


def validate_skin_recommendations(disease, user_profile):
    """Validate and personalize remedies using Trust Engine"""
    if not TRUST_ENGINE_AVAILABLE or not trust_engine:
        return None

    try:
        condition_map = {
            'Acne': 'acne',
            'Eczema (Atopic Dermatitis)': 'eczema',
            'Psoriasis (mild forms)': 'psoriasis',
            'Psoriasis': 'psoriasis',
            'Heat Rash (Prickly Heat)': 'heat rash',
            'Hives (Urticaria)': 'hives',
            'Sunburn': 'burns',
            'Dry Skin (Xerosis)': 'dry skin',
            'Fungal Infections (Ringworm, Athlete\'s Foot)': 'fungal infection',
            'Athlete\'s Foot': 'fungal infection',
            'Jock Itch': 'fungal infection',
            'Contact Dermatitis': 'dermatitis',
            'Dandruff (Seborrheic Dermatitis)': 'dandruff',
            'Allergic Rash (Mild Allergic Dermatitis)': 'rash',
            'Scalp Folliculitis': 'skin',
            'Cold Sores': 'cold sores',
            'Rosacea': 'skin',
        }

        # Herbs known to Trust Engine, mapped per condition
        condition_herb_map = {
            'acne': ['tea tree', 'honey', 'turmeric', 'neem'],
            'eczema': ['coconut oil', 'aloe vera', 'honey', 'turmeric'],
            'psoriasis': ['aloe vera', 'turmeric', 'coconut oil', 'tea tree', 'honey'],
            'heat rash': ['aloe vera', 'turmeric', 'coconut oil'],
            'hives': ['aloe vera', 'honey', 'turmeric'],
            'burns': ['aloe vera', 'honey', 'coconut oil'],
            'dry skin': ['coconut oil', 'aloe vera', 'honey'],
            'fungal infection': ['garlic', 'turmeric', 'tea tree'],
            'dermatitis': ['aloe vera', 'coconut oil', 'turmeric'],
            'dandruff': ['tea tree', 'coconut oil', 'aloe vera'],
            'rash': ['aloe vera', 'honey', 'turmeric'],
            'skin': ['aloe vera', 'turmeric', 'honey'],
            'cold sores': ['honey', 'aloe vera', 'garlic'],
        }

        mapped_condition = condition_map.get(disease, disease.lower().split('(')[0].strip())
        herbs_to_check = condition_herb_map.get(mapped_condition, ['aloe vera', 'turmeric', 'honey'])

        user_meds = user_profile.get('current_medications', [])
        user_allergies = user_profile.get('allergies', [])

        evidence_level_tier = {
            'high': 1, 'moderate': 2, 'low_to_moderate': 2,
            'low': 3, 'very_low': 4, 'insufficient': 5,
        }
        tier_labels = {1: "Clinical Trials", 2: "Mechanistic Studies", 3: "Traditional Use", 4: "Anecdotal", 5: "Theoretical"}
        base_scores = {1: 9.5, 2: 8.0, 3: 6.0, 4: 4.0, 5: 2.0}

        validated_remedies = []
        warnings = []

        for herb_name in herbs_to_check:
            # Allergy check
            if any(herb_name.lower() in a.lower() or a.lower() in herb_name.lower()
                   for a in user_allergies):
                warnings.append(f"⚠️ Skipped {herb_name.title()} - allergy detected")
                continue

            # Get evidence from Trust Engine
            evidence = trust_engine.get_evidence_for_herb(herb_name, mapped_condition)

            evidence_level = evidence.get('evidence_level', 'very_low') if evidence else 'very_low'
            tier = evidence_level_tier.get(evidence_level, 4)
            score = float(base_scores.get(tier, 5.0))

            # Check drug interactions from evidence data
            has_interaction = False
            skip = False
            if evidence:
                for drug_interaction in evidence.get('interactions', []):
                    substance = drug_interaction.get('substance', '').lower()
                    for med in user_meds:
                        if med.lower() in substance or substance in med.lower():
                            severity_val = drug_interaction.get('severity', 'moderate')
                            effect = drug_interaction.get('description', 'possible interaction')
                            if severity_val in ['critical', 'major']:
                                warnings.append(f"🚫 **{herb_name.title()}** contraindicated with {med}: {effect}")
                                skip = True
                            else:
                                score -= 1.5
                                warnings.append(f"⚠️ Use **{herb_name.title()}** with caution if taking {med}")
                                has_interaction = True
                            break
                    if skip:
                        break

            if skip:
                continue

            # Only show mechanism if evidence is for the same/related condition
            # (avoids showing "heals burns" for psoriasis aloe vera entry)
            mechanism = ''
            if evidence:
                ev_condition = evidence.get('condition', '').lower().replace('_', ' ')
                mc = mapped_condition.lower()
                if mc in ev_condition or ev_condition in mc or any(w in ev_condition for w in mc.split() if len(w) > 3):
                    mechanism = evidence.get('summary', '')

            dose = ''
            if evidence and evidence.get('dosing'):
                dosing = evidence['dosing']
                dose = dosing.get('topical', dosing.get('adults', dosing.get('children', '')))

            validated_remedies.append({
                'name': herb_name,
                'score': round(score, 1),
                'tier': tier,
                'tier_label': tier_labels.get(tier, "Traditional Use"),
                'mechanism': mechanism,
                'dose': str(dose) if dose else '',
                'has_interaction': has_interaction,
            })

        validated_remedies.sort(key=lambda x: x['score'], reverse=True)

        return {
            'remedies': validated_remedies[:6],
            'warnings': warnings,
            'condition_mapped': mapped_condition,
            'total_found': len(validated_remedies),
        }

    except Exception as e:
        logger.error(f"Trust Engine validation error: {e}", exc_info=True)
        return None


_FALLBACK_DOSES = {
    "aloe vera":         "Apply pure gel directly to affected area 3–4× daily. Continue for 2–4 weeks.",
    "turmeric":          "Mix ½ tsp turmeric with coconut oil into a paste. Apply to lesions for 15–20 min, rinse. Once daily for 3–4 weeks.",
    "tea tree":          "Dilute 2–3 drops in 1 tsp carrier oil (coconut/jojoba). Apply with cotton pad 2× daily for 2–3 weeks.",
    "coconut oil":       "Warm a small amount between palms. Massage into affected area 2–3× daily after bathing. Use for 2–4 weeks.",
    "neem":              "Apply neem oil (diluted 1:10 with carrier oil) or neem leaf paste to skin 1–2× daily for 3 weeks.",
    "calendula":         "Apply calendula cream or diluted tincture to affected area 2–3× daily. Continue for 2–3 weeks.",
    "chamomile":         "Apply cooled chamomile tea compress for 10 min 2× daily, or use chamomile cream twice daily for 2 weeks.",
    "honey":             "Apply a thin layer of raw/manuka honey to lesions. Cover with gauze for 20–30 min, rinse. Once daily for 2–3 weeks.",
    "oatmeal":           "Add 1 cup colloidal oatmeal to lukewarm bath; soak 15–20 min daily. Or apply oatmeal paste for 10 min then rinse.",
    "lavender":          "Dilute 3–4 drops lavender oil in 1 tsp carrier oil. Apply to affected area 2× daily for 2–3 weeks.",
    "witch hazel":       "Apply undiluted to affected skin with cotton pad 2–3× daily. Continue for 1–2 weeks.",
    "apple cider vinegar": "Dilute 1 part ACV in 3 parts water. Apply with cotton ball 1–2× daily for up to 2 weeks. Rinse after 15 min.",
    "zinc":              "Apply zinc oxide cream to affected area after cleansing, 2–3× daily for 2–4 weeks.",
    "salicylic acid":    "Apply 2% salicylic acid gel or cream to lesions once daily at night. Continue for 4–6 weeks.",
}

def _fallback_dose(herb_name: str) -> str:
    return _FALLBACK_DOSES.get(herb_name.lower().strip(), "Apply topically to affected area 2× daily for 2–3 weeks. Discontinue if irritation occurs.")


def build_detailed_skin_analysis(result, trust_validation, user_profile):
    """Build comprehensive, patient-friendly skin analysis report"""
    disease = result.get('disease', 'Unknown')
    confidence_pct = round(result.get('confidence_score', 0) * 100, 1)
    severity = result.get('severity', 'Unknown')
    description = result.get('description', '')
    key_features = result.get('key_features', [])
    visual = result.get('visual_analysis', {})
    urgency_note = result.get('urgency_note', '')
    differential = result.get('differential_diagnosis', [])
    distinguishing = result.get('distinguishing_features', '')
    reasoning = result.get('reasoning', '')
    affected_area = result.get('affected_area', 'Not specified')

    user_name = user_profile.get('first_name', 'there')
    if not user_name or user_name.lower() in ['user', '']:
        user_name = 'there'

    import re as _re

    # Clean D2C pipeline technical prefix from reasoning
    clean_reasoning = ""
    if reasoning:
        clean_reasoning = _re.sub(r'D2C pipeline:[^\.]+\.?\s*', '', reasoning).strip()
        clean_reasoning = _re.sub(r'Edge AI \([^)]+\)\s*(classified as [^.]+\.?|—[^.]+\.?)\s*', '', clean_reasoning).strip()
        clean_reasoning = _re.sub(r'ServVia Edge AI\s*(classified as [^.]+\.?|—[^.]+\.?)\s*', '', clean_reasoning).strip()

    report = f"""## Skin Analysis Report
Hi **{user_name}**! I've analyzed your skin image and here's what I found:
---
### Diagnosis: **{disease}**
| | |
|---|---|
| **Confidence** | {confidence_pct}% |
| **Severity** | {severity} |
| **Affected Area** | {affected_area} |
---
### Why I Made This Diagnosis
{description}
"""

    if key_features:
        report += "**Key Visual Indicators:**\n\n"
        for feature in key_features:
            report += f"- {feature}\n"
        report += "\n"

    if distinguishing:
        report += f"**What makes this {disease} and not something else:**\n\n{distinguishing}\n\n"

    if differential:
        report += "**Other conditions I considered:**\n\n"
        for d in differential:
            report += f"- {d} (ruled out based on visual features)\n"
        report += "\n"

    report += "---\n### Evidence-Based Treatment Recommendations\n\n"

    if trust_validation and trust_validation.get('remedies'):
        report += f"Found **{len(trust_validation['remedies'])} scientifically validated remedies** for {disease}:\n\n"

        for i, remedy in enumerate(trust_validation['remedies'], 1):
            dot = "🟢" if remedy['score'] >= 8 else "🟡" if remedy['score'] >= 6 else "🔴"
            confidence_text = "Strong Evidence" if remedy['score'] >= 8 else "Good Evidence" if remedy['score'] >= 6 else "Traditional Use"

            report += f"#### {i}. {remedy['name'].title()} {dot}\n"
            report += f"**Scientific Confidence Score:** {remedy['score']}/10 ({confidence_text}) | **Evidence Level:** {remedy['tier_label']}\n\n"

            if remedy['mechanism']:
                report += f"**How it works:** {remedy['mechanism']}\n\n"

            dose = remedy['dose'] or _fallback_dose(remedy['name'])
            if dose:
                report += f"**Recommended usage:** {dose}\n\n"
            if remedy.get('has_interaction'):
                report += "**Use with caution** — see safety notes below\n\n"

            report += "---\n\n"

        report += "| Score | Meaning |\n|-------|----------|\n"
        report += "| 🟢 **8-10** | Clinical trial evidence (RCTs, meta-analyses) |\n"
        report += "| 🟡 **5-7** | Mechanistic studies with documented pathways |\n"
        report += "| 🔴 **1-4** | Traditional use or preliminary research |\n\n"

        if trust_validation.get('warnings'):
            report += "### Personalized Safety Alerts\n\n"
            report += "Based on your health profile, please note:\n\n"
            for warning in trust_validation['warnings']:
                report += f"{warning}\n\n"
    else:
        report += f"Evidence-informed home remedies for **{disease}**:\n\n"
        for i, rec in enumerate(result.get('recommendations', []), 1):
            report += f"{i}. {rec}\n\n"

    report += "---\n### What You Should Do Next\n\n"
    severity_lower = severity.lower()
    if 'severe' in severity_lower:
        report += f"**Severity Level: {severity}** 🔴\n\n{urgency_note}\n\n"
        report += "**Recommended Actions:**\n\n"
        report += "1. See a dermatologist within 24-48 hours\n"
        report += "2. Take photos daily to track changes\n"
        report += "3. Avoid touching or picking at the affected area\n"
        report += "4. Note any new triggers\n"
        report += "5. The remedies above may help while awaiting professional care\n\n"
    elif 'moderate' in severity_lower:
        report += f"**Severity Level: {severity}** 🟡\n\n{urgency_note}\n\n"
        report += "**Recommended Actions:**\n\n"
        report += "1. Try the top remedies for **5-7 days**\n"
        report += "2. Take a comparison photo in one week\n"
        report += "3. Keep area clean and moisturized\n"
        report += "4. Avoid known triggers\n"
        report += "5. Consult a dermatologist if no improvement\n\n"
    else:
        report += f"**Severity Level: {severity}** 🟢\n\n{urgency_note}\n\n"
        report += "**Recommended Actions:**\n\n"
        report += "1. Start with the highest-rated remedy above\n"
        report += "2. Use consistently for **1-2 weeks**\n"
        report += "3. Stay hydrated and maintain good hygiene\n"
        report += "4. Monitor progress\n"
        report += "5. Most cases resolve with proper care\n\n"

    report += f"---\n### Understanding {disease}\n\n"
    report += get_condition_education(disease)

    return report


def get_condition_education(disease):
    """Educational content about common skin conditions"""
    education = {
        "Acne": """
**What is Acne?**
Acne occurs when hair follicles become clogged with oil (sebum) and dead skin cells. Bacteria (P. acnes) can then multiply, causing inflammation.

**Common Triggers:**
- Hormonal changes (puberty, menstruation, stress)
- Certain foods (dairy, high-glycemic foods for some people)
- Comedogenic skincare products
- Touching your face frequently
- Stress and lack of sleep

**Prevention Tips:**
- Wash face twice daily with gentle cleanser
- Use non-comedogenic products
- Don't pick or squeeze pimples
- Change pillowcases regularly
- Stay hydrated
""",
        "Eczema (Atopic Dermatitis)": """
**What is Eczema?**
Eczema is a chronic inflammatory condition causing dry, itchy, inflamed skin. It's often linked to allergies and runs in families.

**Common Triggers:**
- Dry air and low humidity
- Harsh soaps and detergents
- Stress and anxiety
- Certain fabrics (wool, synthetic)
- Food allergies (dairy, eggs, nuts)

**Management Tips:**
- Moisturize immediately after bathing
- Use fragrance-free products
- Wear soft, breathable fabrics
- Identify and avoid your triggers
- Keep nails short to prevent scratching damage
""",
        "Psoriasis (mild forms)": """
**What is Psoriasis?**
Psoriasis is an autoimmune condition where skin cells multiply too quickly, causing thick, scaly patches.

**Common Triggers:**
- Stress
- Skin injuries (cuts, sunburn)
- Infections (strep throat)
- Cold, dry weather
- Certain medications
- Smoking and alcohol

**Management Tips:**
- Keep skin moisturized
- Get moderate sun exposure (15-20 min daily)
- Manage stress through relaxation techniques
- Avoid smoking and limit alcohol
- Consider anti-inflammatory diet
""",
        "Heat Rash (Prickly Heat)": """
**What is Heat Rash?**
Heat rash occurs when sweat ducts become blocked, trapping perspiration under the skin.

**Common Causes:**
- Hot, humid weather
- Excessive sweating
- Tight clothing
- Heavy creams that block pores
- Physical activity in heat

**Prevention & Relief:**
- Stay in cool, air-conditioned environments
- Wear loose, breathable cotton clothing
- Take cool showers
- Use lightweight, non-comedogenic products
- Avoid heavy physical activity in extreme heat
""",
        "Hives (Urticaria)": """
**What are Hives?**
Hives are raised, itchy welts that appear suddenly, usually due to an allergic reaction. They typically resolve within 24 hours but can recur.

**Common Triggers:**
- Food allergies (shellfish, nuts, eggs)
- Medications (antibiotics, aspirin)
- Insect stings
- Stress
- Temperature changes
- Infections

**When to Seek Emergency Care:**
- Difficulty breathing or swallowing
- Swelling of face, lips, or tongue
- Dizziness or fainting
- Rapid heartbeat
"""
    }

    return education.get(disease, f"""
**About {disease}:**
This is a common skin condition that can often be managed with proper care. For detailed information specific to your case, please consult a dermatologist.

**General Skin Health Tips:**
- Keep skin clean and appropriately moisturized
- Protect from excessive sun exposure
- Stay hydrated (8+ glasses of water daily)
- Eat a balanced diet rich in vitamins A, C, and E
- Get adequate sleep (7-8 hours)
- Manage stress levels
""")


@api_view(['GET'])
def get_skin_analysis_history(request):
    """Get user's skin analysis history (last 10)"""
    try:
        email = request.query_params.get('email_id')
        if not email:
            return Response({'success': False, 'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        analyses = SkinAnalysis.objects.filter(email_id=email).order_by('-created_at')[:10]

        results = [{
            'id': a.id,
            'diagnosis': a.diagnosis,
            'confidence': round(a.confidence_score * 100, 2),
            'date': a.created_at.strftime('%Y-%m-%d %H:%M'),
            'image_url': request.build_absolute_uri(a.image.url) if a.image else None
        } for a in analyses]

        return Response({'success': True, 'history': results, 'count': len(results)})
    except Exception as e:
        logger.error(f"History error: {e}")
        return Response({'success': False, 'error': 'Failed to retrieve history'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════
# SSE STREAMING — POST /api/skin/analyze/stream/
# ═══════════════════════════════════════════════════════════════════════════

def _sse(event: str, data) -> str:
    """Format a single SSE event."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _prepare_skin_image(image_file):
    """Save uploaded image to temp file, return (temp_path, image_data) or raise ValueError."""
    image_file.seek(0)
    image_data = image_file.read()
    image = Image.open(io.BytesIO(image_data))
    if image.mode != 'RGB':
        image = image.convert('RGB')
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
    tmp_path = tmp.name
    tmp.close()  # Must close before writing on Windows (file locking)
    image.save(tmp_path)
    return tmp_path, image_data


@csrf_exempt
def stream_skin_analysis_view(request):
    """
    SSE streaming endpoint for skin analysis.

    POST /api/skin/analyze/stream/
    Body: multipart/form-data with email_id + image

    Events:
        stage  — Pipeline progress
        token  — Response words
        done   — Final metadata
        error  — Error
    """
    if request.method != "POST":
        return StreamingHttpResponse(
            _sse("error", {"message": "POST required"}),
            content_type="text/event-stream",
            status=405,
        )

    email = request.POST.get("email_id", "").strip()
    image_file = request.FILES.get("image")

    if not email or not image_file:
        return StreamingHttpResponse(
            _sse("error", {"message": "Missing email_id or image file"}),
            content_type="text/event-stream",
            status=400,
        )

    event_q = queue.Queue()

    def _pipeline_worker():
        """Run image validation → Gemini analysis → Trust Engine in background thread."""
        _stream_start = _time.time()
        temp_path = None
        try:
            # ── Stage 1: Process image ──
            event_q.put(("stage", {
                "id": "processing",
                "label": "Processing image...",
                "icon": "fa-image",
            }))

            try:
                temp_path, image_data = _prepare_skin_image(image_file)
            except Exception as e:
                event_q.put(("error", {"message": f"Invalid image: {e}"}))
                return

            # ── Stage 2: Validate skin image ──
            event_q.put(("stage", {
                "id": "validating",
                "label": "Validating skin image...",
                "icon": "fa-check-circle",
            }))

            validation = validate_skin_image(temp_path)
            if not validation['is_skin_image']:
                event_q.put(("error", {"message": validation['reason']}))
                return

            # ── Stage 3: Edge AI Analysis (primary) ──
            result = None
            edge_raw = None

            if is_ollama_available():
                event_q.put(("stage", {
                    "id": "analysis",
                    "label": "Analyzing with Edge AI...",
                    "icon": "fa-microchip",
                }))
                edge_raw = classify_skin_image(temp_path)
                if edge_raw is not None:
                    result = edge_result_to_gemini_format(edge_raw)
                    if result is not None:
                        logger.info(f"[EDGE] Stream: {result['disease']} ({edge_raw['confidence']}%)")

            # ── Stage 3b: Gemini fallback (cloud) ──
            if result is None:
                reason = "low confidence" if edge_raw else "Edge AI unavailable"
                event_q.put(("stage", {
                    "id": "analysis",
                    "label": f"Analyzing with Cloud AI ({reason})...",
                    "icon": "fa-cloud",
                }))
                result = detect_skin_disease_gemini(temp_path)

            # Clean up temp file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    temp_path = None
                except OSError:
                    pass

            if not result.get('success'):
                event_q.put(("error", {"message": result.get('error', 'Analysis failed')}))
                return

            disease = result.get('disease', 'Unknown')
            confidence_score = result.get('confidence_score', 0.0)

            # ── Stage 4: Trust Engine ──
            user_profile = get_user_profile(email)
            trust_validation = None
            if TRUST_ENGINE_AVAILABLE and trust_engine:
                event_q.put(("stage", {
                    "id": "trust",
                    "label": "Validating with Trust Engine...",
                    "icon": "fa-shield-alt",
                }))
                trust_validation = validate_skin_recommendations(disease, user_profile)

            # ── Build formatted report ──
            formatted_summary = build_detailed_skin_analysis(result, trust_validation, user_profile)

            # ── Save to DB ──
            image_file.seek(0)
            analysis = SkinAnalysis.objects.create(
                email_id=email,
                image=image_file,
                diagnosis=disease,
                confidence_score=confidence_score,
                recommendations=formatted_summary,
            )

            # ── Stream formatted summary word-by-word ──
            _elapsed = _time.time() - _stream_start
            logger.info(f"ServVia Skin Analysis responded in {_elapsed:.2f}s")
            event_q.put(("stage", {
                "id": "streaming",
                "label": "",
                "icon": "fa-pen",
            }))
            event_q.put(("stream_summary", formatted_summary))

            # ── Done ──
            event_q.put(("done", {
                "analysis_id": analysis.id,
                "diagnosis": disease,
                "confidence": round(confidence_score * 100, 2),
                "severity": result.get('severity', 'Unknown'),
            }))

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Skin stream pipeline error: {e}\n{tb}")
            event_q.put(("error", {"message": f"{type(e).__name__}: {e}"}))
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
            event_q.put(("end", None))

    def _event_generator():
        """SSE generator — reads from queue, yields events to client."""
        thread = threading.Thread(target=_pipeline_worker, daemon=True)
        thread.start()

        while True:
            try:
                event_type, data = event_q.get(timeout=5)
            except queue.Empty:
                if thread.is_alive():
                    yield _sse("heartbeat", {"ts": int(_time.time())})
                    continue
                else:
                    yield _sse("error", {"message": "Pipeline ended unexpectedly"})
                    break

            if event_type == "end":
                break
            elif event_type == "stage":
                yield _sse("stage", data)
            elif event_type == "error":
                yield _sse("error", data)
                break
            elif event_type == "stream_summary":
                import re as _re
                # Split preserving whitespace so newlines are kept intact
                tokens = _re.split(r'(\s+)', data)
                for tok in tokens:
                    if tok:
                        yield _sse("token", {"text": tok})
                        if not tok.isspace():
                            _time.sleep(0.009)
            elif event_type == "done":
                yield _sse("done", data)

        thread.join(timeout=5)

    resp = StreamingHttpResponse(_event_generator(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp
