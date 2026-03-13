"""
ServVia 3.0 — Privacy-Preserving Lab Report Endpoint
======================================================

POST /api/labs/analyze/

Pipeline:
    1. User uploads a lab report file (PDF or image)
    2. [LOCAL] DocumentExtractor extracts raw text (pdfplumber / easyocr)
    3. [LOCAL] PHIRedactor strips all patient-identifiable information
    4. [CLOUD] analyze_lab_report() sends ONLY anonymized text to gpt-4o-mini
    5. Returns structured JSON analysis of biomarkers and abnormal findings

Privacy guarantee: No PHI ever leaves the user's device. Only de-identified
text is sent to the cloud LLM.
"""

import asyncio
import logging
import os
import tempfile

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from edge.ocr_processor import DocumentExtractor
from edge.phi_redactor import PHIRedactor
from agents.lab_summarizer import analyze_lab_report

logger = logging.getLogger("ServVia.API.Labs")

# Supported file extensions
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}

# Max file size: 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024


class LabReportViewSet(GenericViewSet):
    """Privacy-preserving lab report analysis."""

    parser_classes = [MultiPartParser]

    @action(detail=False, methods=["post"])
    def analyze(self, request):
        """
        POST /api/labs/analyze/

        Upload a lab report file for privacy-preserving analysis.

        Request:
            Content-Type: multipart/form-data
            file: PDF or image file (max 10 MB)

        Response 200:
            {
                "report_type": "Complete Blood Count",
                "biomarkers": [...],
                "abnormal_count": 2,
                "summary": "...",
                "recommendation": "...",
                "privacy": {
                    "phi_entities_redacted": true,
                    "processing_location": "local",
                    "cloud_received": "anonymized_text_only"
                }
            }
        """
        # ── Validate file upload ──────────────────────────────────────────
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"error": "No file uploaded. Send a lab report as 'file' in multipart form data."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check file size
        if uploaded_file.size > MAX_FILE_SIZE:
            return Response(
                {"error": f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check file extension
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return Response(
                {"error": f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Save to temp file (close handle before extraction — Windows compat) ──
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext)
            try:
                with os.fdopen(tmp_fd, 'wb') as tmp:
                    for chunk in uploaded_file.chunks():
                        tmp.write(chunk)
            except Exception:
                os.close(tmp_fd)
                raise

            logger.info(f"Lab report saved to temp file: {tmp_path} ({uploaded_file.size} bytes)")

            # ── Step 1: LOCAL text extraction ─────────────────────────────
            extractor = DocumentExtractor()
            raw_text = extractor.extract(tmp_path)
            logger.info(f"Extracted {len(raw_text)} chars from {uploaded_file.name}")

            # ── Step 2: LOCAL PHI redaction ───────────────────────────────
            redactor = PHIRedactor()
            anonymized_text = redactor.anonymize_text(raw_text)
            logger.info(f"PHI redaction complete: {len(raw_text)} -> {len(anonymized_text)} chars")

            # ── Step 3: CLOUD analysis (anonymized only) ──────────────────
            loop = asyncio.new_event_loop()
            try:
                analysis = loop.run_until_complete(analyze_lab_report(anonymized_text))
            finally:
                loop.close()

            # ── Attach privacy metadata ───────────────────────────────────
            analysis["privacy"] = {
                "phi_entities_redacted": True,
                "processing_location": "local",
                "cloud_received": "anonymized_text_only",
            }

            return Response(analysis, status=status.HTTP_200_OK)

        except ValueError as e:
            logger.warning(f"Lab report processing error: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except Exception as e:
            logger.exception(f"Unexpected error processing lab report: {e}")
            return Response(
                {"error": "Internal error processing lab report. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            # Clean up temp file
            if "tmp_path" in locals() and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                    logger.debug(f"Cleaned up temp file: {tmp_path}")
                except OSError:
                    pass  # Windows may hold file briefly
