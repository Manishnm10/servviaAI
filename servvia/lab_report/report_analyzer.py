"""
Lab Report Analyzer using Gemini 2.0 Flash
- Extracts and analyzes lab reports (image/PDF)
- Produces structured JSON + detailed markdown summary
"""

import io
import os
import json
import logging
import tempfile
from typing import Any, Dict, Optional

from PIL import Image
import google.generativeai as genai

# Optional: handle absence of django_core.config gracefully
try:
    from django_core.config import ENV_CONFIG  # type: ignore
except ImportError:  # pragma: no cover - depends on your project
    ENV_CONFIG = {}

logger = logging.getLogger(__name__)


class LabReportAnalyzer:
    """
    Gemini-powered lab report analyzer.

    Responsibilities:
    - Extract text from lab report (image or PDF)
    - Ask Gemini for detailed, structured JSON analysis
    - Provide a markdown-formatted summary ready for UI display
    """

    DEFAULT_MODEL = "gemini-2.0-flash"  # Use stable model ID for production

    def __init__(
        self,
        model_name: Optional[str] = None,
        request_timeout: int = 90,
    ) -> None:
        """
        Initialize Gemini API client and model.

        Args:
            model_name: Optional override for Gemini model name.
            request_timeout: Timeout (seconds) for Gemini requests.
        """
        api_key = (
            ENV_CONFIG.get("GOOGLE_API_KEY")
            or ENV_CONFIG.get("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )

        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY or GEMINI_API_KEY not found in environment/config"
            )

        self.request_timeout = request_timeout
        genai.configure(api_key=api_key)

        self.model_name = model_name or ENV_CONFIG.get(
            "GEMINI_LAB_REPORT_MODEL", self.DEFAULT_MODEL
        )
        self.model = genai.GenerativeModel(self.model_name)

        logger.info(
            "✅ LabReportAnalyzer initialized (model=%s, timeout=%ss)",
            self.model_name,
            self.request_timeout,
        )

    # -------------------------------------------------------------------------
    # TEXT EXTRACTION
    # -------------------------------------------------------------------------

    def extract_text_from_pdf(self, report_file) -> str:
        """
        Extract text from a lab report (image or PDF).

        Args:
            report_file: Django UploadedFile (or file-like) containing image/PDF.

        Returns:
            Extracted text as a string (may be empty on failure).
        """
        try:
            # Read file data once
            file_data = report_file.read()
            if not file_data:
                logger.warning("Empty file received for lab report extraction.")
                return ""

            # Reset file pointer (safe for Django UploadedFile reuse)
            try:
                report_file.seek(0)
            except Exception:
                pass

            # Try to treat as image first
            try:
                image = Image.open(io.BytesIO(file_data))

                # Ensure compatible mode
                if image.mode != "RGB":
                    image = image.convert("RGB")

                prompt = (
                    "Extract ALL text from this lab report image.\n\n"
                    "Include:\n"
                    "- Test names\n"
                    "- Values\n"
                    "- Units\n"
                    "- Reference ranges\n"
                    "- Dates\n"
                    "- Patient information (if visible)\n\n"
                    "Return the extracted text as-is, preserving structure."
                )

                logger.info("📄 Attempting image-based text extraction via Gemini Vision...")
                response = self.model.generate_content(
                    [prompt, image],
                    request_options={"timeout": self.request_timeout},
                )

                extracted_text = (response.text or "").strip()
                logger.info(
                    "✅ Extracted %d characters from lab report image",
                    len(extracted_text),
                )
                return extracted_text

            except Exception as img_error:
                # Not an image or Pillow could not open it; treat as PDF
                logger.warning(
                    "Not an image or image extraction failed (%s). "
                    "Falling back to PDF extraction.",
                    img_error,
                )

                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".pdf"
                ) as tmp:
                    tmp.write(file_data)
                    tmp_path = tmp.name

                prompt = (
                    "Extract all text from this lab report PDF, "
                    "preserving structure and table content."
                )

                try:
                    logger.info("📄 Uploading PDF to Gemini for text extraction...")
                    uploaded_file = genai.upload_file(path=tmp_path)

                    response = self.model.generate_content(
                        [prompt, uploaded_file],
                        request_options={"timeout": self.request_timeout},
                    )

                    extracted_text = (response.text or "").strip()
                    logger.info(
                        "✅ Extracted %d characters from lab report PDF",
                        len(extracted_text),
                    )
                    return extracted_text

                finally:
                    # Clean up local temp file
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        logger.warning(
                            "Failed to delete temporary PDF file: %s", tmp_path
                        )

        except Exception as e:
            logger.error("❌ Text extraction failed: %s", e, exc_info=True)
            return ""

    # -------------------------------------------------------------------------
    # ANALYSIS
    # -------------------------------------------------------------------------

    def summarize_report(
        self,
        extracted_text: str,
        email_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze lab report text and generate a comprehensive, patient-friendly summary.

        Args:
            extracted_text: Raw text extracted from the lab report.
            email_id: Optional user email for logging/correlation.

        Returns:
            Dict with structure:
            {
                "success": bool,
                "analysis": dict (parsed JSON from Gemini),
                "summary": str (formatted markdown),
                "abnormal_values": list,
                "recommendations": list,
                "critical_flags": list,
                "visual_indicators": {
                    "normal_count": int,
                    "abnormal_count": int,
                    "critical_count": int,
                },
                "pattern_analysis": str,
                "overall_health_assessment": str,
                "urgency_level": str,
                "follow_up_needed": bool,
                "error": str (optional on failure)
            }
        """
        try:
            if not extracted_text:
                logger.warning("summarize_report called with empty extracted_text.")
                return {
                    "success": False,
                    "error": "No text extracted from report",
                }

            logger.info(
                "🔬 Analyzing lab report with Gemini (email_id=%s)...", email_id
            )

            # Large, structured prompt requiring JSON output
            prompt = f"""
You are an expert medical AI assistant. Analyze this lab report and provide an extremely detailed,
educational, and actionable summary.

EXTRACTED LAB REPORT TEXT:
{extracted_text}

YOUR TASK:
Return a comprehensive analysis in EXACTLY this JSON format (no extra keys, no trailing commas):

{{
  "test_type": "Complete Blood Count with Lipid Profile",
  "report_date": "Extract date from report, or null if not available",
  "patient_name": "Extract if visible, else null",
  "parameters": [
    {{
      "name": "Test Name",
      "value": "Actual Value",
      "unit": "Unit",
      "normal_range": "Reference Range",
      "status": "Low/Normal/High/Critical",
      "severity": "Normal/Mild/Moderate/Severe",
      "icon": "🟢/🟡/🟠/🔴",
      "clinical_significance": "What this test measures and why it matters",
      "your_result_interpretation": "Detailed interpretation of THIS specific result",
      "possible_causes": ["Cause 1", "Cause 2", "Cause 3"],
      "symptoms_to_watch": ["Symptom 1", "Symptom 2"],
      "dietary_recommendations": ["Food 1", "Food 2"],
      "lifestyle_changes": ["Change 1", "Change 2"]
    }}
  ],
  "abnormal_count": 3,
  "normal_count": 15,
  "critical_count": 0,
  "formatted_summary": "WRITE A VERY DETAILED MARKDOWN SUMMARY HERE - SEE FORMAT BELOW",
  "overall_health_assessment": "Detailed paragraph about overall health based on all results",
  "pattern_analysis": "Identify any patterns or connections between abnormal values",
  "critical_flags": ["Any critical values that need immediate attention"],
  "recommendations": [
    "🥗 Detailed dietary recommendation with specific foods",
    "🏃 Exercise recommendation",
    "💊 Supplement suggestions (if appropriate)",
    "👨‍⚕️ When to see a doctor",
    "📅 Follow-up testing timeline"
  ],
  "follow_up_needed": true,
  "urgency_level": "Routine/Soon/Urgent/Emergency",
  "overall_status": "Short status phrase summarizing the overall picture"
}}

CRITICAL:
- The "formatted_summary" field must be a VERY DETAILED markdown string with this structure:

## 📋 Lab Report Analysis for [Patient Name]

### 🏥 Report Overview
- **Test Date:** [Date]
- **Test Type:** [Types of tests included]
- **Total Parameters:** [X] tested | [Y] normal | [Z] abnormal

---

### 📊 Executive Summary

[3–4 sentences summarizing the overall findings. Mention the most significant findings first.
Be clear about what's normal and what needs attention.]

---

### 🔬 Detailed Parameter Analysis

#### 🟢 NORMAL RESULTS (brief overview)

| Parameter | Your Value | Normal Range | Status |
|-----------|------------|--------------|--------|
| [Name] | [Value] | [Range] | ✅ Normal |

#### 🟡/🟠/🔴 ABNORMAL RESULTS (detailed analysis for each)

**1. [Parameter Name]: [Value] [Unit] — [Status Icon] [Status]**

📌 **What This Test Measures:**
[Explain what this parameter measures in simple terms]

📈 **Your Result:**
- Your value: [X]
- Normal range: [Y]
- Deviation: [How far from normal, percentage if applicable]

🔍 **Clinical Significance:**
[Explain what this abnormality might indicate - be thorough but not alarming]

❓ **Possible Causes:**
- [Cause 1 with brief explanation]
- [Cause 2 with brief explanation]
- [Cause 3 with brief explanation]

⚠️ **Symptoms to Watch For:**
- [Symptom 1]
- [Symptom 2]

🥗 **Dietary Recommendations:**
- [Specific food 1 and why it helps]
- [Specific food 2 and why it helps]
- [Foods to avoid and why]

💪 **Lifestyle Modifications:**
- [Specific actionable advice]

---

[Repeat for each abnormal parameter]

---

### 🔗 Pattern Analysis

[Describe any connections between abnormal values.]

---

### 🎯 Actionable Recommendations

**Immediate Actions (This Week):**
1. [Specific action]
2. [Specific action]

**Short-Term Goals (1–3 Months):**
1. [Specific goal]
2. [Specific goal]

**Long-Term Lifestyle Changes:**
1. [Sustainable change]
2. [Sustainable change]

---

### 📅 Follow-Up Plan

- **Recommended retest:** [Timeframe]
- **Specialist consultation:** [If needed, which type]
- **Monitoring:** [What to track at home]

---

### ⚠️ Important Disclaimer

This AI-generated analysis is for educational purposes only.
Always consult with your healthcare provider for proper medical interpretation and treatment decisions.

IMPORTANT OUTPUT RULES:
- Return ONLY valid JSON (no markdown, no comments outside the JSON).
- Do NOT wrap JSON in backticks.
- Do NOT include any additional text before or after the JSON.
"""

            response = self.model.generate_content(
                prompt,
                request_options={"timeout": self.request_timeout},
            )

            response_text = (response.text or "").strip()
            analysis_obj = self._parse_json_response(response_text)

            if analysis_obj is None:
                logger.warning("JSON parsing failed, returning raw Gemini response.")
                return {
                    "success": True,
                    "analysis": {"test_type": "Lab Report"},
                    "summary": response_text,
                    "abnormal_values": [],
                    "recommendations": [],
                    "critical_flags": [],
                    "visual_indicators": {},
                    "pattern_analysis": "",
                    "overall_health_assessment": "",
                    "urgency_level": "Routine",
                    "follow_up_needed": False,
                }

            logger.info(
                "✅ Detailed analysis complete: test_type=%s, abnormal=%s, critical=%s",
                analysis_obj.get("test_type"),
                analysis_obj.get("abnormal_count"),
                analysis_obj.get("critical_count"),
            )

            return {
                "success": True,
                "analysis": analysis_obj,
                "summary": analysis_obj.get("formatted_summary", ""),
                "abnormal_values": analysis_obj.get("parameters", []),
                "recommendations": analysis_obj.get("recommendations", []),
                "critical_flags": analysis_obj.get("critical_flags", []),
                "visual_indicators": {
                    "normal_count": analysis_obj.get("normal_count", 0),
                    "abnormal_count": analysis_obj.get("abnormal_count", 0),
                    "critical_count": analysis_obj.get("critical_count", 0),
                },
                "pattern_analysis": analysis_obj.get("pattern_analysis", ""),
                "overall_health_assessment": analysis_obj.get(
                    "overall_health_assessment", ""
                ),
                "urgency_level": analysis_obj.get("urgency_level", "Routine"),
                "follow_up_needed": analysis_obj.get("follow_up_needed", False),
            }

        except Exception as e:
            logger.error("❌ Report analysis failed: %s", e, exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    # -------------------------------------------------------------------------
    # INTERNAL HELPERS
    # -------------------------------------------------------------------------

    def _parse_json_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse Gemini's JSON response.

        Handles cases where the model might accidentally include backticks or
        markdown fences, but prefers direct JSON.

        Args:
            response_text: Raw string returned by Gemini.

        Returns:
            Parsed JSON dict, or None on failure.
        """
        if not response_text:
            return None

        try:
            # If response is already pure JSON
            if response_text.strip().startswith("{"):
                return json.loads(response_text)

            # Handle markdown code fences
            if "```json" in response_text:
                json_text = response_text.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in response_text:
                json_text = response_text.split("```", 1)[1].split("```", 1)[0]
            elif "{" in response_text and "}" in response_text:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                json_text = response_text[start:end]
            else:
                logger.error("No JSON-like content found in response.")
                return None

            return json.loads(json_text.strip())

        except json.JSONDecodeError as e:
            logger.error("❌ JSON parsing error: %s", e)
            logger.error("Response preview (first 500 chars): %s", response_text[:500])
            return None

    # -------------------------------------------------------------------------
    # EMBEDDING TEXT GENERATION
    # -------------------------------------------------------------------------

    def generate_embedding_text(self, analysis_result: Dict[str, Any]) -> str:
        """
        Generate a text representation suitable for vector embeddings.

        Args:
            analysis_result: Dict as returned by summarize_report().

        Returns:
            A single text block capturing key clinical content.
        """
        if not analysis_result or not analysis_result.get("success"):
            return ""

        data = analysis_result.get("analysis", {}) or {}

        embedding_lines = [
            f"Lab Report: {data.get('test_type', 'Unknown')}",
            f"Date: {data.get('report_date', 'Unknown')}",
            "",
            "Test Results:",
        ]

        for param in data.get("parameters", []):
            name = param.get("name", "Unknown")
            value = param.get("value", "")
            unit = param.get("unit", "")
            status = param.get("status", "Unknown")
            explanation = (
                param.get("clinical_significance")
                or param.get("your_result_interpretation")
                or ""
            )

            line = f"- {name}: {value} {unit} ({status})"
            if status and status.lower() != "normal" and explanation:
                line += f" - {explanation}"
            embedding_lines.append(line)

        # Prefer markdown summary; fall back to any available summary fields
        formatted_summary = data.get("formatted_summary") or data.get("summary") or ""
        if formatted_summary:
            embedding_lines.append("")
            embedding_lines.append("Summary:")
            embedding_lines.append(formatted_summary)

        return "\n".join(embedding_lines).strip()

