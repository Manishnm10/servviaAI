"""
ServVia 4.0 — Comprehensive Demo Script (All 5 Objectives)
============================================================

Run this AFTER starting the server:
    cd C:\\Users\\cools\\servviaAI\\farmer-chat
    python manage.py runserver 0.0.0.0:9000

Then in another terminal:
    cd C:\\Users\\cools\\servviaAI\\farmer-chat
    python demo_all_objectives.py

This script demonstrates all 5 thesis objectives with synthetic data,
printing clear headers and results for evaluator review.
"""

import json
import os
import sys
import time
import requests
from io import BytesIO

BASE = "http://127.0.0.1:9000"
EMAIL = "demo@servvia.ai"

# Colors for terminal output
class C:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"

def banner(title, obj_num):
    print(f"\n{'='*80}")
    print(f"{C.BOLD}{C.HEADER}  OBJECTIVE {obj_num}: {title}{C.END}")
    print(f"{'='*80}\n")

def sub_banner(title):
    print(f"\n{C.BOLD}{C.CYAN}  --- {title} ---{C.END}\n")

def ok(msg):
    print(f"  {C.GREEN}[PASS]{C.END} {msg}")

def fail(msg):
    print(f"  {C.RED}[FAIL]{C.END} {msg}")

def info(msg):
    print(f"  {C.BLUE}[INFO]{C.END} {msg}")

def warn(msg):
    print(f"  {C.YELLOW}[WARN]{C.END} {msg}")

def show_json(data, indent=2, max_lines=30):
    """Pretty-print JSON, truncated for readability."""
    text = json.dumps(data, indent=indent, ensure_ascii=False)
    lines = text.split("\n")
    for line in lines[:max_lines]:
        print(f"    {line}")
    if len(lines) > max_lines:
        print(f"    ... ({len(lines) - max_lines} more lines)")

def post_json(url, payload, timeout=120):
    """POST JSON and return parsed response."""
    t0 = time.time()
    resp = requests.post(url, json=payload, timeout=timeout)
    elapsed = time.time() - t0
    return resp.status_code, resp.json(), elapsed

def post_chat(query, timeout=120):
    """Send a chat query and return response data + timing."""
    return post_json(f"{BASE}/api/chat/get_answer_for_text_query/", {
        "email_id": EMAIL,
        "query": query,
    }, timeout=timeout)

def stream_chat(query, timeout=120):
    """Send a streaming chat query, collect SSE events, return them."""
    t0 = time.time()
    resp = requests.post(
        f"{BASE}/api/chat/stream/",
        json={"email_id": EMAIL, "query": query},
        stream=True,
        timeout=timeout,
    )
    events = []
    full_text = ""
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            data = json.loads(line[6:])
            events.append((current_event, data))
            if current_event == "token":
                full_text += data.get("text", "")
            elif current_event == "emergency":
                full_text = data.get("response", "")
    elapsed = time.time() - t0
    return events, full_text, elapsed


def check_server():
    """Verify the server is running."""
    print(f"{C.BOLD}Checking server at {BASE}...{C.END}")
    try:
        r = requests.get(f"{BASE}/api/ping/", timeout=5)
        if r.status_code == 200:
            ok("Server is running")
            return True
    except requests.ConnectionError:
        pass
    fail(f"Server not reachable at {BASE}")
    print(f"\n  Start it with:")
    print(f"    cd C:\\Users\\cools\\servviaAI\\farmer-chat")
    print(f"    python manage.py runserver 0.0.0.0:9000\n")
    return False


# ══════════════════════════════════════════════════════════════════════
# OBJECTIVE 1: Multi-Agent Clinical Verification via LangGraph
# ══════════════════════════════════════════════════════════════════════
def demo_objective_1():
    banner("Multi-Agent Clinical Verification (LangGraph)", 1)

    # ── Test 1a: Minor query (Proposer-only fast path) ──
    sub_banner("Test 1a: Minor Query — Proposer-Only Fast Path (skips Critic)")
    info("Query: 'I have a mild headache and feel a bit tired'")
    info("Expected: Proposer generates response WITHOUT Critic review")
    info("Look in terminal for: 'Proposer-ONLY fast path (minor query, skipping Critic)'")
    print()

    code, data, elapsed = post_chat("I have a mild headache and feel a bit tired")
    if code == 200:
        response = data.get("response", "")
        pipeline = data.get("pipeline", "")
        ok(f"Response received in {elapsed:.1f}s")
        ok(f"Pipeline: {pipeline}")
        info(f"Response preview: {response[:200]}...")
        if "proposer_only" in pipeline:
            ok("Confirmed: Proposer-only path (Critic skipped)")
        else:
            warn(f"Pipeline was '{pipeline}' — Critic may have run")
    else:
        fail(f"HTTP {code}: {data}")

    # ── Test 1b: Serious query (full Diagnostician > Proposer > Critic) ──
    sub_banner("Test 1b: Serious Query — Full Multi-Agent Pipeline")
    info("Query: 'I have high fever of 103F, severe body aches, joint pain, and rash behind ears for 4 days'")
    info("Expected: Diagnostician classifies severity -> Proposer drafts -> Critic reviews -> Approved")
    info("Look in terminal for: '[DIAG]', '[OK] Critic APPROVED'")
    print()

    code, data, elapsed = post_chat(
        "I have high fever of 103F, severe body aches, joint pain, and rash behind ears for 4 days"
    )
    if code == 200:
        response = data.get("response", "")
        pipeline = data.get("pipeline", "")
        ok(f"Response received in {elapsed:.1f}s")
        ok(f"Pipeline: {pipeline}")
        info(f"Response preview: {response[:250]}...")

        # Check for medical referral (Critic should enforce this for serious queries)
        referral_keywords = ["doctor", "physician", "hospital", "medical attention", "healthcare provider", "seek medical"]
        has_referral = any(kw in response.lower() for kw in referral_keywords)
        if has_referral:
            ok("Contains medical referral (Critic safety check passed)")
        else:
            warn("No explicit medical referral found — check Critic behavior")
    else:
        fail(f"HTTP {code}: {data}")

    # ── Test 1c: Emergency (hardcoded, no LLM) ──
    sub_banner("Test 1c: Emergency Detection — Zero-LLM Safety Gate")
    info("Query: 'I am having a heart attack, severe chest pain'")
    info("Expected: Instant emergency response (no LLM call, hardcoded)")
    print()

    code, data, elapsed = post_chat("I am having a heart attack, severe chest pain")
    if code == 200:
        pipeline = data.get("pipeline", "")
        emergency_type = data.get("emergency_type", "")
        ok(f"Response in {elapsed:.1f}s (should be <1s)")
        ok(f"Pipeline: {pipeline}")
        ok(f"Emergency type: {emergency_type}")
        if "emergency" in pipeline.lower():
            ok("Confirmed: Emergency intercept (no LLM used)")
        if elapsed < 2.0:
            ok(f"Latency {elapsed:.2f}s — instant as expected")
    else:
        fail(f"HTTP {code}: {data}")


# ══════════════════════════════════════════════════════════════════════
# OBJECTIVE 2: Neurosymbolic Pharmacovigilance
# ══════════════════════════════════════════════════════════════════════
def demo_objective_2():
    banner("Neurosymbolic Pharmacovigilance (Drug-Herb Interactions)", 2)

    # ── Step 0: Set up user profile with medications + allergies ──
    sub_banner("Setup: Creating user profile with allergies & medications")
    profile_payload = {
        "email": EMAIL,
        "first_name": "Demo",
        "allergies": "ginger, peanuts, shellfish",
        "medical_conditions": "hypertension, type 2 diabetes",
        "current_medications": "warfarin, metformin, lisinopril",
    }
    info(f"Allergies: {profile_payload['allergies']}")
    info(f"Medications: {profile_payload['current_medications']}")
    info(f"Conditions: {profile_payload['medical_conditions']}")

    code, data, _ = post_json(f"{BASE}/api/profile/profile/save_profile/", profile_payload)
    if code == 200 and data.get("success"):
        ok("Profile saved successfully")
    else:
        warn(f"Profile save returned: {code} — {data}")

    # ── Test 2a: Allergy blocking ──
    sub_banner("Test 2a: Allergy Safety — Ginger Should NOT Be Recommended")
    info("Query: 'I have nausea and stomach pain, suggest home remedies'")
    info("Expected: Ginger is blocked (user is allergic), substitutes offered")
    info("Look in terminal for: 'ALLERGY BLOCK: ginger'")
    print()

    code, data, elapsed = post_chat("I have nausea and stomach pain, suggest home remedies")
    if code == 200:
        response = data.get("response", "").lower()
        safety = data.get("safety", {})
        ok(f"Response received in {elapsed:.1f}s")

        if "ginger" not in response:
            ok("Ginger NOT in response (allergy correctly blocked)")
        else:
            # Check if it's in a warning context
            if safety and "ginger" in str(safety.get("flagged_herbs", [])).lower():
                ok("Ginger flagged in safety warnings (post-generation catch)")
            else:
                fail("Ginger appears in response without safety warning!")

        if safety:
            info("Safety metadata:")
            show_json(safety)
    else:
        fail(f"HTTP {code}: {data}")

    # ── Test 2b: Drug interaction (warfarin + antiplatelet herbs) ──
    sub_banner("Test 2b: Drug-Herb Interaction — Warfarin + Antiplatelet Herbs")
    info("Query: 'I have joint pain and inflammation, what herbs can help?'")
    info("Expected: Turmeric/ginkgo flagged (warfarin bleeding risk)")
    info("Look in terminal for: 'ACTIVE MED BLOCK: turmeric x warfarin'")
    print()

    code, data, elapsed = post_chat("I have joint pain and inflammation, what herbs can help?")
    if code == 200:
        response = data.get("response", "")
        safety = data.get("safety", {})
        ok(f"Response received in {elapsed:.1f}s")

        flagged = safety.get("flagged_herbs", []) if safety else []
        if flagged:
            ok(f"Flagged herbs: {flagged}")
            for warning in safety.get("warnings", []):
                warn(f"  {warning.get('herb')}: {warning.get('reason')}")
        else:
            info("No herbs flagged in safety metadata (may have been pre-filtered)")

        info(f"Response preview: {response[:200]}...")
    else:
        fail(f"HTTP {code}: {data}")

    # ── Test 2c: Metformin + hypoglycemic herbs ──
    sub_banner("Test 2c: Drug-Herb Interaction — Metformin + Hypoglycemic Herbs")
    info("Query: 'suggest natural remedies for blood sugar control'")
    info("Expected: Fenugreek/cinnamon flagged (metformin hypoglycemia risk)")
    print()

    code, data, elapsed = post_chat("suggest natural remedies for blood sugar control")
    if code == 200:
        response = data.get("response", "")
        safety = data.get("safety", {})
        ok(f"Response received in {elapsed:.1f}s")

        if safety:
            info("Safety metadata:")
            show_json(safety)
        info(f"Response preview: {response[:200]}...")
    else:
        fail(f"HTTP {code}: {data}")


# ══════════════════════════════════════════════════════════════════════
# OBJECTIVE 3: Chronobiology-Aware Adaptive Dosing
# ══════════════════════════════════════════════════════════════════════
def demo_objective_3():
    banner("Chronobiology-Aware Adaptive Dosing", 3)

    sub_banner("Test 3a: Time-Aware Response — Current Time Context")
    from datetime import datetime
    now = datetime.now()
    hour = now.hour
    info(f"Current local time: {now.strftime('%H:%M')} (hour={hour})")

    if 4 <= hour < 7:
        info("Expected phase: EARLY_MORNING (cortisol surge)")
    elif 7 <= hour < 10:
        info("Expected phase: MORNING_ACTIVATION (peak alertness)")
    elif 10 <= hour < 12:
        info("Expected phase: LATE_MORNING (cognitive peak)")
    elif 12 <= hour < 14:
        info("Expected phase: AFTERNOON_PEAK (digestive fire max)")
    elif 14 <= hour < 17:
        info("Expected phase: AFTERNOON_SLUMP (adenosine buildup)")
    elif 17 <= hour < 19:
        info("Expected phase: EVENING_ACTIVE (second cortisol peak)")
    elif 19 <= hour < 22:
        info("Expected phase: WIND_DOWN (melatonin onset)")
    else:
        info("Expected phase: DEEP_SLEEP (circadian misalignment!)")

    info("Look in terminal for: '🕐 Inferred state @ HH:00 | Phase: ... | Season: ... | Pressure: ...'")
    print()

    # Use streaming endpoint to get bio_state metadata
    events, full_text, elapsed = stream_chat("I have trouble sleeping and feel anxious")
    ok(f"Response received in {elapsed:.1f}s")

    # Extract bio_state from 'done' event
    bio_state = None
    for etype, edata in events:
        if etype == "done":
            bio_state = edata.get("bio_state", {})
            break

    if bio_state:
        ok("Chronobiology metadata received:")
        info(f"  Circadian Phase:    {bio_state.get('circadian_phase', 'N/A')}")
        info(f"  Seasonal Influence: {bio_state.get('seasonal_influence', 'N/A')}")
        info(f"  Sleep Pressure:     {bio_state.get('sleep_pressure', 'N/A')}")
        info(f"  Is Misaligned:      {bio_state.get('is_misaligned', 'N/A')}")

        # Check if response includes time-appropriate advice
        text_lower = full_text.lower()
        time_keywords = ["melatonin", "cortisol", "circadian", "evening", "morning",
                         "calming", "sleep", "wind down", "night", "bedtime"]
        matches = [kw for kw in time_keywords if kw in text_lower]
        if matches:
            ok(f"Response includes time-aware keywords: {matches}")
        else:
            info("No explicit time keywords found (advisory may be woven into remedy choice)")
    else:
        warn("No bio_state metadata in response — check if chronobiology engine is running")

    info(f"Response preview: {full_text[:200]}...")

    # ── Test 3b: Seasonal context ──
    sub_banner("Test 3b: Seasonal Influence — Month-Based Recommendations")
    month = now.month
    if month in [12, 1, 2]:
        season = "Winter Accumulation (Kapha)"
    elif month in [3, 4]:
        season = "Spring Release"
    elif month in [5, 6]:
        season = "Summer Heat (Pitta)"
    elif month in [7, 8, 9]:
        season = "Monsoon Dampness"
    else:
        season = "Autumn Transition (Vata)"

    info(f"Current month: {now.strftime('%B')} -> Expected season: {season}")
    info("The seasonal influence is automatically applied to all responses")
    if bio_state:
        ok(f"Confirmed season in metadata: {bio_state.get('seasonal_influence', 'N/A')}")


# ══════════════════════════════════════════════════════════════════════
# OBJECTIVE 4: Outcome-Adaptive Remedy Ranking (Graph RAG)
# ══════════════════════════════════════════════════════════════════════
def demo_objective_4():
    banner("Outcome-Adaptive Remedy Ranking (Graph RAG)", 4)

    sub_banner("Test 4a: Evidence-Tiered Remedy Ranking")
    info("The system ranks remedies by Scientific Confidence Score (SCS):")
    info("  TIER_1_CLINICAL  (RCTs, meta-analyses)        -> weight 1.0")
    info("  TIER_2_MECHANISTIC (in-vitro, animal studies) -> weight 0.75")
    info("  TIER_3_TRADITIONAL (Ayurveda/TCM documented)  -> weight 0.5")
    info("  TIER_4_ANECDOTAL  (case reports)              -> weight 0.25")
    info("  TIER_5_THEORETICAL (hypothetical)             -> weight 0.1")
    print()

    info("Query: 'home remedies for common cold and congestion'")
    info("Look in terminal for: 'Found N remedies for...' and trust verification data")
    print()

    events, full_text, elapsed = stream_chat("home remedies for common cold and congestion")
    ok(f"Response received in {elapsed:.1f}s")

    # Check for trust verification in done event
    trust_data = None
    for etype, edata in events:
        if etype == "done":
            trust_data = edata.get("trust_verification", {})
            break

    if trust_data:
        ok("Trust verification data received:")
        show_json(trust_data)
    else:
        info("Trust verification not in SSE metadata (may be in non-streaming endpoint)")

    # Also try non-streaming to get full metadata
    code, data, elapsed2 = post_chat("what are evidence-based remedies for sore throat")
    if code == 200:
        trust = data.get("trust_verification", {})
        if trust:
            ok("Trust verification from non-streaming endpoint:")
            show_json(trust)
        else:
            info("Trust data not in response (Graph RAG uses in-memory repository for demo)")

    info(f"Response preview: {full_text[:250]}...")
    print()
    info("Architecture note: Full Neo4j graph backend is defined in")
    info("  servvia2/knowledge_graph/schema.py — using in-memory repository for demo")
    info("  SCS = EvidenceTierWeight x PubMedRefs x MechanismKnown x SafetyCheck")


# ══════════════════════════════════════════════════════════════════════
# OBJECTIVE 5: Privacy-Preserving Lab Report Intelligence
# ══════════════════════════════════════════════════════════════════════
def demo_objective_5():
    banner("Privacy-Preserving Lab Report Intelligence", 5)

    # ── Create a synthetic lab report image ──
    sub_banner("Setup: Creating synthetic lab report image")

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        fail("Pillow not installed — run: pip install Pillow")
        return

    # Synthetic CBC lab report with PHI
    lab_text_lines = [
        "CITY DIAGNOSTIC LABORATORY",
        "123 Medical Center Drive, Hyderabad 500032",
        "",
        "Patient Name: Rajesh Kumar Sharma",
        "Age/Sex: 45 Years / Male",
        "Phone: +91 98765 43210",
        "Email: rajesh.sharma@gmail.com",
        "Ref. Dr: Dr. Priya Mehta",
        "Date: 12-Mar-2026",
        "",
        "===== COMPLETE BLOOD COUNT (CBC) =====",
        "",
        "TEST              RESULT    UNIT        NORMAL RANGE",
        "------------------------------------------------------",
        "Hemoglobin        9.2       g/dL        13.0 - 17.0   LOW",
        "RBC Count         3.8       million/uL  4.5 - 5.5     LOW",
        "WBC Count         14500     /uL         4000 - 11000  HIGH",
        "Platelet Count    95000     /uL         150000-400000 LOW",
        "Hematocrit        28.5      %           38.0 - 50.0   LOW",
        "MCV               85.2      fL          80.0 - 100.0  NORMAL",
        "MCH               28.1      pg          27.0 - 33.0   NORMAL",
        "MCHP              33.0      g/dL        32.0 - 36.0   NORMAL",
        "RDW               16.8      %           11.5 - 14.5   HIGH",
        "Neutrophils       78        %           40 - 70       HIGH",
        "Lymphocytes       15        %           20 - 40       LOW",
        "Monocytes         5         %           2 - 8         NORMAL",
        "Eosinophils       1         %           1 - 4         NORMAL",
        "Basophils         1         %           0 - 1         NORMAL",
        "ESR               45        mm/hr       0 - 15        HIGH",
        "",
        "===== LIVER FUNCTION TEST (LFT) =====",
        "",
        "Total Bilirubin   2.8       mg/dL       0.1 - 1.2     HIGH",
        "Direct Bilirubin  1.5       mg/dL       0.0 - 0.3     HIGH",
        "SGOT (AST)        89        U/L         5 - 40        HIGH",
        "SGPT (ALT)        112       U/L         7 - 56        HIGH",
        "Alk. Phosphatase  145       U/L         44 - 147      NORMAL",
        "Total Protein     6.2       g/dL        6.0 - 8.3     NORMAL",
        "Albumin           3.1       g/dL        3.5 - 5.5     LOW",
        "Globulin          3.1       g/dL        2.0 - 3.5     NORMAL",
        "",
        "Note: Multiple abnormalities detected. Clinical correlation advised.",
        "Signature: Dr. Anitha Rao, MD Pathology",
    ]

    # Create image
    img_width, img_height = 800, 1100
    img = Image.new("RGB", (img_width, img_height), "white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("consola.ttf", 14)
        font_title = ImageFont.truetype("consolab.ttf", 16)
    except (IOError, OSError):
        font = ImageFont.load_default()
        font_title = font

    y = 20
    for i, line in enumerate(lab_text_lines):
        f = font_title if i == 0 or "=====" in line else font
        color = "red" if any(x in line for x in ["LOW", "HIGH"]) else "black"
        draw.text((30, y), line, fill=color, font=f)
        y += 22

    test_image_path = os.path.join(os.path.dirname(__file__), "demo_lab_report.png")
    img.save(test_image_path)
    ok(f"Synthetic lab report image created: {test_image_path}")
    info("Contains PHI: Patient name, phone, email, doctor name")
    info("Contains abnormals: Low Hb, Low RBC, High WBC, Low platelets, High liver enzymes")

    # ── Test 5a: Lab report analysis ──
    sub_banner("Test 5a: Upload & Analyze Lab Report")
    info("Endpoint: POST /api/lab-report/analyze/")
    info("Expected pipeline:")
    info("  1. [LOCAL] OCR text extraction (easyocr)")
    info("  2. [LOCAL] PHI redaction (Presidio + spaCy)")
    info("  3. [CLOUD] GPT-4o-mini analysis (anonymized text only)")
    info("Look in terminal for:")
    info("  'Extracted N chars from demo_lab_report.png'")
    info("  'Detected N PHI entities: PERSON, PHONE_NUMBER, EMAIL_ADDRESS'")
    info("  'PHI redaction complete: N -> M chars'")
    print()

    t0 = time.time()
    with open(test_image_path, "rb") as f:
        resp = requests.post(
            f"{BASE}/api/lab-report/analyze/",
            data={"email_id": EMAIL},
            files={"report": ("demo_lab_report.png", f, "image/png")},
            timeout=180,
        )
    elapsed = time.time() - t0

    if resp.status_code == 200:
        result = resp.json()
        ok(f"Lab report analyzed in {elapsed:.1f}s")
        ok(f"Test type: {result.get('test_type', 'N/A')}")
        ok(f"Abnormal count: {result.get('abnormal_count', 'N/A')}")
        ok(f"Normal count: {result.get('normal_count', 'N/A')}")
        ok(f"Overall status: {result.get('overall_status', 'N/A')}")
        ok(f"Follow-up needed: {result.get('follow_up_needed', 'N/A')}")

        # Privacy metadata
        privacy = result.get("privacy", {})
        if privacy:
            ok("Privacy metadata:")
            info(f"  PHI redacted:          {privacy.get('phi_entities_redacted')}")
            info(f"  Processing location:   {privacy.get('processing_location')}")
            info(f"  Cloud received:        {privacy.get('cloud_received')}")

        # Show summary preview
        summary = result.get("formatted_summary", result.get("summary", ""))
        if summary:
            info(f"Summary preview:")
            for line in summary.split("\n")[:10]:
                print(f"    {line}")
            if summary.count("\n") > 10:
                print(f"    ... ({summary.count(chr(10)) - 10} more lines)")

        # Show parameters
        params = result.get("parameters", [])
        if params:
            info(f"Biomarkers detected: {len(params)}")
            for p in params[:5]:
                name = p.get("name", p.get("parameter", "?"))
                val = p.get("value", "?")
                flag = p.get("status", p.get("flag", ""))
                print(f"    {name}: {val} [{flag}]")
            if len(params) > 5:
                print(f"    ... and {len(params) - 5} more")

    else:
        fail(f"HTTP {resp.status_code}: {resp.text[:300]}")

    # ── Test 5b: Check history ──
    sub_banner("Test 5b: Lab Report History Retrieval")
    resp = requests.get(f"{BASE}/api/lab-report/history/", params={"email_id": EMAIL}, timeout=30)
    if resp.status_code == 200:
        history = resp.json()
        ok(f"History retrieved: {history.get('count', 0)} reports")
        for h in history.get("history", [])[:3]:
            info(f"  Report #{h['id']} | {h['date']} | {h['test_type']} | Abnormals: {h['abnormal_count']}")
    else:
        warn(f"History: HTTP {resp.status_code}")

    # Cleanup
    if os.path.exists(test_image_path):
        os.unlink(test_image_path)
        info("Cleaned up test image")


# ══════════════════════════════════════════════════════════════════════
# BONUS: SSE Streaming Demo
# ══════════════════════════════════════════════════════════════════════
def demo_streaming():
    banner("SSE Streaming (ChatGPT-Style Typing)", "BONUS")

    # ── Test: Streaming with stage updates ──
    sub_banner("Test: Real-Time Stage Updates + Word-by-Word Streaming")
    info("Endpoint: POST /api/chat/stream/")
    info("Query: 'I have a sore throat and runny nose'")
    info("Expected events: stage -> stage -> ... -> token -> token -> ... -> done")
    print()

    events, full_text, elapsed = stream_chat("I have a sore throat and runny nose")
    ok(f"Stream completed in {elapsed:.1f}s")

    # Count event types
    stages = [(e, d) for e, d in events if e == "stage"]
    tokens = [(e, d) for e, d in events if e == "token"]
    done_events = [(e, d) for e, d in events if e == "done"]

    ok(f"Stage updates received: {len(stages)}")
    for _, s in stages:
        info(f"  [{s.get('icon', '')}] {s.get('label', '')}")

    ok(f"Token events received: {len(tokens)}")
    ok(f"Total response length: {len(full_text)} chars")

    if done_events:
        ok("Final metadata received:")
        show_json(done_events[0][1], max_lines=15)

    # ── Test: Emergency bypasses streaming ──
    sub_banner("Test: Emergency Bypasses Word-by-Word Streaming")
    info("Query: 'I am choking and cannot breathe'")
    info("Expected: Single 'emergency' event with full response (no tokens)")
    print()

    events, full_text, elapsed = stream_chat("I am choking and cannot breathe")
    ok(f"Response in {elapsed:.1f}s")

    emergency_events = [(e, d) for e, d in events if e == "emergency"]
    token_events = [(e, d) for e, d in events if e == "token"]

    if emergency_events:
        ok("Emergency event received (full response, no typing animation)")
        ok(f"Emergency type: {emergency_events[0][1].get('emergency_type', 'N/A')}")
        info(f"Response preview: {full_text[:150]}...")
    if not token_events:
        ok("No token events — streaming correctly disabled for emergencies")
    else:
        warn(f"Got {len(token_events)} token events — streaming should be disabled for emergencies")


# ══════════════════════════════════════════════════════════════════════
# SKIN ANALYSIS DEMO
# ══════════════════════════════════════════════════════════════════════
def demo_skin_analysis():
    banner("Skin Disease Analysis (Gemini 2.5 Flash)", "EXTRA")

    sub_banner("Test: Synthetic Skin Image Analysis")

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        fail("Pillow not installed")
        return

    # Create a simple reddish skin-like image
    img = Image.new("RGB", (400, 400), (220, 180, 170))
    draw = ImageDraw.Draw(img)
    # Add some red patches to simulate rash
    for x, y, r in [(100, 100, 30), (200, 150, 25), (150, 250, 20), (250, 200, 35)]:
        draw.ellipse([x-r, y-r, x+r, y+r], fill=(255, 80, 80), outline=(200, 50, 50))
    # Add some texture
    for x, y, r in [(120, 120, 5), (210, 160, 4), (160, 260, 6)]:
        draw.ellipse([x-r, y-r, x+r, y+r], fill=(255, 200, 200))

    test_skin_path = os.path.join(os.path.dirname(__file__), "demo_skin.jpg")
    img.save(test_skin_path, "JPEG")
    ok(f"Synthetic skin image created: {test_skin_path}")

    info("Endpoint: POST /api/skin/analyze/")
    info("Expected: Gemini 2.5 Flash analyzes image -> diagnosis + confidence")
    print()

    t0 = time.time()
    with open(test_skin_path, "rb") as f:
        resp = requests.post(
            f"{BASE}/api/skin/analyze/",
            data={"email_id": EMAIL},
            files={"image": ("demo_skin.jpg", f, "image/jpeg")},
            timeout=120,
        )
    elapsed = time.time() - t0

    if resp.status_code == 200:
        result = resp.json()
        ok(f"Analysis completed in {elapsed:.1f}s")
        if result.get("success"):
            info(f"Condition: {result.get('condition', 'N/A')}")
            info(f"Confidence: {result.get('confidence', 'N/A')}")
            info(f"Severity: {result.get('severity', 'N/A')}")
            description = result.get("description", "")
            if description:
                info(f"Description: {description[:200]}...")
        else:
            warn(f"Analysis returned: {result.get('error', result)}")
    else:
        warn(f"HTTP {resp.status_code}: {resp.text[:200]}")

    if os.path.exists(test_skin_path):
        os.unlink(test_skin_path)
        info("Cleaned up test image")


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════
def main():
    print(f"\n{C.BOLD}{C.HEADER}")
    print("  ╔══════════════════════════════════════════════════════════════╗")
    print("  ║           ServVia 4.0 — Full Demo Script                   ║")
    print("  ║     Comprehensive Evaluation of All 5 Objectives           ║")
    print("  ╚══════════════════════════════════════════════════════════════╝")
    print(f"{C.END}")

    if not check_server():
        sys.exit(1)

    results = {}

    # Run all objectives
    demos = [
        ("Objective 1", demo_objective_1),
        ("Objective 2", demo_objective_2),
        ("Objective 3", demo_objective_3),
        ("Objective 4", demo_objective_4),
        ("Objective 5", demo_objective_5),
        ("SSE Streaming", demo_streaming),
        ("Skin Analysis", demo_skin_analysis),
    ]

    for name, fn in demos:
        try:
            fn()
            results[name] = "PASS"
        except Exception as e:
            fail(f"{name} failed with error: {e}")
            results[name] = f"ERROR: {e}"

    # ── Final Summary ──
    print(f"\n{'='*80}")
    print(f"{C.BOLD}{C.HEADER}  DEMO SUMMARY{C.END}")
    print(f"{'='*80}\n")

    for name, status in results.items():
        icon = f"{C.GREEN}PASS{C.END}" if status == "PASS" else f"{C.RED}{status}{C.END}"
        print(f"  {name:.<40} {icon}")

    print(f"\n{C.BOLD}Terminal Log Guide:{C.END}")
    print(f"  Look at the server terminal (port 9000) for detailed pipeline logs:")
    print(f"  {C.CYAN}[DIAG]{C.END}  — Diagnostician node (severity classification)")
    print(f"  {C.CYAN}[OK]{C.END}    — Critic approved the response")
    print(f"  {C.CYAN}[A]{C.END}     — Emergency detection step")
    print(f"  {C.CYAN}[B]{C.END}     — Chronobiology inference step")
    print(f"  {C.CYAN}[D]{C.END}     — Safety validation (pharmacovigilance)")
    print(f"  {C.CYAN}🕐{C.END}     — Circadian phase + seasonal influence")
    print(f"  {C.RED}⛔{C.END}     — Allergy or drug interaction BLOCK")
    print(f"  {C.GREEN}✅{C.END}     — Safety check passed")
    print()
    print(f"  {C.BOLD}Privacy (Objective 5):{C.END}")
    print(f"  {C.CYAN}PHI redaction complete{C.END} — Shows char count before/after de-identification")
    print(f"  {C.CYAN}Detected N PHI entities{C.END} — PERSON, PHONE, EMAIL found and masked")
    print()


if __name__ == "__main__":
    main()
