"""
ServVia 4.0 — 25-Symptom Test Suite
====================================
Tests both minor (PATH A) and serious (PATH B) symptom queries
against the full Diagnostician → Proposer → Critic pipeline.
"""

import asyncio
import aiohttp
import json
import time
import sys
import os

# Fix Windows console encoding for emoji output
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:9000/api/chat/get_answer_for_text_query/"
EMAIL = "mohammedayaan2193@gmail.com"

# ─── 25 TEST CASES ─────────────────────────────────────────────────────────
TEST_CASES = [
    # === SIMPLE / MINOR (PATH A) — 13 cases ===
    {"id": 1,  "type": "MINOR", "query": "I have a sore throat"},
    {"id": 2,  "type": "MINOR", "query": "I have a mild headache"},
    {"id": 3,  "type": "MINOR", "query": "I have a runny nose and sneezing"},
    {"id": 4,  "type": "MINOR", "query": "I have a mild cough"},
    {"id": 5,  "type": "MINOR", "query": "I have an upset stomach"},
    {"id": 6,  "type": "MINOR", "query": "I can't sleep at night, insomnia"},
    {"id": 7,  "type": "MINOR", "query": "I'm feeling stressed and anxious"},
    {"id": 8,  "type": "MINOR", "query": "I have acidity and bloating after meals"},
    {"id": 9,  "type": "MINOR", "query": "I have a minor skin rash and itching"},
    {"id": 10, "type": "MINOR", "query": "I have a mild cold with congestion"},
    {"id": 11, "type": "MINOR", "query": "I have muscle soreness after exercise"},
    {"id": 12, "type": "MINOR", "query": "I have a mild toothache"},
    {"id": 13, "type": "MINOR", "query": "I feel nauseous after eating"},

    # === SERIOUS / MULTI-SYMPTOM (PATH B) — 12 cases ===
    {"id": 14, "type": "SERIOUS", "query": "I have a sudden high-grade fever, severe headache, intense joint and muscle pain, rash, nausea, and vomiting"},
    {"id": 15, "type": "SERIOUS", "query": "I have high fever for 5 days with body rash and bleeding gums"},
    {"id": 16, "type": "SERIOUS", "query": "I have chest pain with shortness of breath and dizziness"},
    {"id": 17, "type": "SERIOUS", "query": "I have severe headache with confusion and vision changes"},
    {"id": 18, "type": "SERIOUS", "query": "I have high fever with yellowing of eyes and dark urine"},
    {"id": 19, "type": "SERIOUS", "query": "I have persistent fever with severe abdominal pain and diarrhea for a week"},
    {"id": 20, "type": "SERIOUS", "query": "I have sudden weakness on one side of my body with slurred speech"},
    {"id": 21, "type": "SERIOUS", "query": "I have high fever, chills, severe body aches, and a stiff neck"},
    {"id": 22, "type": "SERIOUS", "query": "I have been vomiting blood with severe stomach pain"},
    {"id": 23, "type": "SERIOUS", "query": "I have high fever with joint swelling, rash on my face, and extreme fatigue for 2 weeks"},
    {"id": 24, "type": "SERIOUS", "query": "I have difficulty breathing, wheezing, and my lips are turning blue"},
    {"id": 25, "type": "SERIOUS", "query": "I have severe headache, high fever, neck stiffness, and sensitivity to light"},
]


async def run_single_test(session, test_case, results):
    """Run a single test case and collect results."""
    tc_id = test_case["id"]
    tc_type = test_case["type"]
    query = test_case["query"]

    print(f"  [{tc_id:2d}/25] {tc_type:7s} | {query[:60]}...", flush=True)

    start = time.time()
    try:
        async with session.post(
            BASE_URL,
            json={"email_id": EMAIL, "query": query},
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            elapsed = time.time() - start
            status_code = resp.status
            body = await resp.json()

            response_text = body.get("response", "")
            pipeline = body.get("pipeline", "unknown")
            trust_data = body.get("trust_verification", {})
            bio_state = body.get("bio_state", {})
            agent_verified = body.get("agent_verified", False)

            # ── Checks ──
            has_empathy = bool(response_text and not response_text.strip().startswith("#"))
            has_remedies = "Remedy" in response_text or "remedy" in response_text or "Relief" in response_text
            has_doctor_ref = "doctor" in response_text.lower() or "medical care" in response_text.lower() or "medical evaluation" in response_text.lower()
            has_diagnosis = "Clinical Assessment" in response_text or "consistent with" in response_text
            has_evidence = "Scientific Validation" in response_text or "Verified Remedies" in response_text
            has_er_signs = "Emergency Room" in response_text or "emergency" in response_text.lower()
            is_fallback = "safety fallback" in response_text.lower()

            # ── Determine pass/fail ──
            if tc_type == "MINOR":
                passed = (
                    status_code == 200
                    and has_empathy
                    and has_remedies
                    and not is_fallback
                )
                fail_reasons = []
                if status_code != 200: fail_reasons.append(f"HTTP {status_code}")
                if not has_empathy: fail_reasons.append("no empathy opening")
                if not has_remedies: fail_reasons.append("no remedies")
                if is_fallback: fail_reasons.append("FALLBACK triggered")
            else:  # SERIOUS
                passed = (
                    status_code == 200
                    and has_empathy
                    and has_doctor_ref
                    and not is_fallback
                )
                fail_reasons = []
                if status_code != 200: fail_reasons.append(f"HTTP {status_code}")
                if not has_empathy: fail_reasons.append("no empathy opening")
                if not has_doctor_ref: fail_reasons.append("no doctor recommendation")
                if not has_diagnosis: fail_reasons.append("no diagnosis")
                if not has_remedies: fail_reasons.append("no symptom remedies")
                if is_fallback: fail_reasons.append("FALLBACK triggered")

            result = {
                "id": tc_id,
                "type": tc_type,
                "query": query,
                "status": status_code,
                "elapsed_s": round(elapsed, 1),
                "passed": passed,
                "fail_reasons": fail_reasons,
                "pipeline": pipeline,
                "agent_verified": agent_verified,
                "has_empathy": has_empathy,
                "has_remedies": has_remedies,
                "has_doctor_ref": has_doctor_ref,
                "has_diagnosis": has_diagnosis,
                "has_evidence": has_evidence,
                "has_er_signs": has_er_signs,
                "is_fallback": is_fallback,
                "verified_herbs": trust_data.get("verified_herbs", []),
                "unverified_herbs": trust_data.get("unverified_herbs", []),
                "response_length": len(response_text),
                "response_preview": response_text[:200],
            }
            results.append(result)

            status_icon = "PASS" if passed else "FAIL"
            print(f"           {status_icon} | {elapsed:.1f}s | pipeline={pipeline} | len={len(response_text)}", flush=True)
            if fail_reasons:
                print(f"           Issues: {', '.join(fail_reasons)}", flush=True)

    except Exception as e:
        elapsed = time.time() - start
        print(f"           ERROR | {elapsed:.1f}s | {str(e)[:100]}", flush=True)
        results.append({
            "id": tc_id,
            "type": tc_type,
            "query": query,
            "status": 0,
            "elapsed_s": round(elapsed, 1),
            "passed": False,
            "fail_reasons": [f"Exception: {str(e)[:100]}"],
            "pipeline": "error",
            "response_preview": "",
        })


async def main():
    print("=" * 70)
    print("  ServVia 4.0 — 25-Symptom Test Suite")
    print("=" * 70)
    print(f"  Target: {BASE_URL}")
    print(f"  Email:  {EMAIL}")
    print("=" * 70)
    print()

    results = []

    async with aiohttp.ClientSession() as session:
        # Run tests sequentially (to avoid overloading the server)
        for tc in TEST_CASES:
            await run_single_test(session, tc, results)

    # ── Summary Report ──
    print()
    print("=" * 70)
    print("  TEST REPORT SUMMARY")
    print("=" * 70)

    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    failed = total - passed
    minor_results = [r for r in results if r.get("type") == "MINOR"]
    serious_results = [r for r in results if r.get("type") == "SERIOUS"]
    minor_passed = sum(1 for r in minor_results if r.get("passed"))
    serious_passed = sum(1 for r in serious_results if r.get("passed"))

    avg_time = sum(r.get("elapsed_s", 0) for r in results) / max(total, 1)
    minor_avg = sum(r.get("elapsed_s", 0) for r in minor_results) / max(len(minor_results), 1)
    serious_avg = sum(r.get("elapsed_s", 0) for r in serious_results) / max(len(serious_results), 1)

    print(f"\n  Overall: {passed}/{total} passed ({passed/total*100:.0f}%)")
    print(f"  Minor (PATH A): {minor_passed}/{len(minor_results)} passed")
    print(f"  Serious (PATH B): {serious_passed}/{len(serious_results)} passed")
    print(f"\n  Avg response time: {avg_time:.1f}s (Minor: {minor_avg:.1f}s | Serious: {serious_avg:.1f}s)")

    # ── Feature Coverage ──
    print("\n  Feature Coverage:")
    empathy_count = sum(1 for r in results if r.get("has_empathy"))
    remedy_count = sum(1 for r in results if r.get("has_remedies"))
    doctor_count = sum(1 for r in serious_results if r.get("has_doctor_ref"))
    diagnosis_count = sum(1 for r in serious_results if r.get("has_diagnosis"))
    evidence_count = sum(1 for r in results if r.get("has_evidence"))
    er_count = sum(1 for r in serious_results if r.get("has_er_signs"))
    fallback_count = sum(1 for r in results if r.get("is_fallback"))

    print(f"    Empathetic opening:    {empathy_count}/{total}")
    print(f"    Home remedies:         {remedy_count}/{total}")
    print(f"    Doctor referral (B):   {doctor_count}/{len(serious_results)}")
    print(f"    Diagnosis (B):         {diagnosis_count}/{len(serious_results)}")
    print(f"    Evidence scores:       {evidence_count}/{total}")
    print(f"    ER warning signs (B):  {er_count}/{len(serious_results)}")
    print(f"    Fallbacks triggered:   {fallback_count}/{total}")

    # ── Failed Tests Detail ──
    failed_tests = [r for r in results if not r.get("passed")]
    if failed_tests:
        print(f"\n  Failed Tests ({len(failed_tests)}):")
        for r in failed_tests:
            print(f"    [{r['id']:2d}] {r['type']:7s} | {r['query'][:50]}...")
            print(f"         Reasons: {', '.join(r.get('fail_reasons', ['unknown']))}")

    # ── Individual Test Results ──
    print("\n" + "=" * 70)
    print("  INDIVIDUAL TEST RESULTS")
    print("=" * 70)
    for r in results:
        status = "PASS" if r.get("passed") else "FAIL"
        print(f"\n  [{r['id']:2d}] {status} | {r['type']:7s} | {r.get('elapsed_s', 0):.1f}s")
        print(f"      Query: {r['query']}")
        print(f"      Pipeline: {r.get('pipeline', 'N/A')} | Agent verified: {r.get('agent_verified', 'N/A')}")
        if r.get("verified_herbs"):
            print(f"      Verified herbs: {', '.join(r['verified_herbs'])}")
        if r.get("unverified_herbs"):
            print(f"      Unverified herbs: {', '.join(r['unverified_herbs'])}")
        if r.get("fail_reasons"):
            print(f"      Issues: {', '.join(r['fail_reasons'])}")
        preview = r.get("response_preview", "")
        if preview:
            print(f"      Response preview: {preview[:150]}...")

    # ── Save JSON report ──
    report_path = "test_report_25.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"summary": {
            "total": total, "passed": passed, "failed": failed,
            "minor_passed": minor_passed, "minor_total": len(minor_results),
            "serious_passed": serious_passed, "serious_total": len(serious_results),
            "avg_response_time_s": round(avg_time, 1),
        }, "results": results}, f, indent=2, ensure_ascii=False)
    print(f"\n  Full JSON report saved to: {report_path}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
