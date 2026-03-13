"""
Lab Report Views — Privacy-Preserving Pipeline
================================================

Uses the ServVia 4.0 pipeline:
    1. [LOCAL] DocumentExtractor (pdfplumber / easyocr) extracts raw text
    2. [LOCAL] PHIRedactor strips patient-identifiable information
    3. [CLOUD] LLM analyzes ONLY anonymized text (Groq fallback on 429)

Endpoints:
    POST /api/lab-report/analyze/         — JSON response (backwards compat)
    POST /api/lab-report/analyze/stream/  — SSE streaming (real-time updates)
    GET  /api/lab-report/history/         — Report history
"""

import asyncio
import json
import logging
import os
import queue
import tempfile
import threading
import time as _time

from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import LabReport
from edge.ocr_processor import DocumentExtractor
from edge.phi_redactor import PHIRedactor
from agents.lab_summarizer import (
    analyze_lab_report,
    stream_lab_report_analysis,
    _format_markdown_summary,
)

logger = logging.getLogger(__name__)

# Reuse across requests — easyocr reader is expensive to initialize
_extractor = None
_redactor = None


def _get_extractor():
    global _extractor
    if _extractor is None:
        _extractor = DocumentExtractor()
    return _extractor


def _get_redactor():
    global _redactor
    if _redactor is None:
        _redactor = PHIRedactor()
    return _redactor


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}


# ═══════════════════════════════════════════════════════════════════════════
# SHARED — Extract text + redact PHI (used by both endpoints)
# ═══════════════════════════════════════════════════════════════════════════

def _extract_and_redact(report_files):
    """
    Extract text from uploaded files and redact PHI.
    Returns (anonymized_text, raw_text, page_count) or raises ValueError.
    """
    extractor = _get_extractor()
    redactor = _get_redactor()
    all_extracted_text = ""

    for idx, report_file in enumerate(report_files, 1):
        ext = os.path.splitext(report_file.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        tmp_path = None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext)
            try:
                with os.fdopen(tmp_fd, 'wb') as tmp:
                    for chunk in report_file.chunks():
                        tmp.write(chunk)
            except Exception:
                os.close(tmp_fd)
                raise

            logger.info(f"Processing page {idx}/{len(report_files)}: {report_file.name}")
            extracted_text = extractor.extract(tmp_path)

            if extracted_text:
                all_extracted_text += f"\n\n=== PAGE {idx} ===\n\n{extracted_text}"
            else:
                logger.warning(f"No text extracted from page {idx}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    if not all_extracted_text.strip():
        raise ValueError("Could not extract text. Ensure images/PDFs are clear.")

    logger.info(f"Extracted {len(all_extracted_text)} chars from {len(report_files)} page(s)")

    anonymized_text = redactor.anonymize_text(all_extracted_text)
    logger.info(
        f"PHI redaction complete: {len(all_extracted_text)} -> "
        f"{len(anonymized_text)} chars"
    )

    return anonymized_text, all_extracted_text, len(report_files)


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 1: POST /api/lab-report/analyze/ — JSON response
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
def analyze_lab_report_view(request):
    """Endpoint to upload and analyze lab reports via the pipeline."""
    try:
        email = request.data.get('email_id')
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        report_files = request.FILES.getlist('report')
        if not report_files:
            single_file = request.FILES.get('report')
            if single_file:
                report_files = [single_file]
            else:
                return Response(
                    {'error': 'At least one report file is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        logger.info(f"Analyzing {len(report_files)} lab report page(s) for {email}")

        # Steps 1 & 2: LOCAL extraction + PHI redaction
        anonymized_text, raw_text, page_count = _extract_and_redact(report_files)

        # Step 3: CLOUD analysis (anonymized text only)
        loop = asyncio.new_event_loop()
        try:
            analysis_result = loop.run_until_complete(analyze_lab_report(anonymized_text))
        finally:
            loop.close()

        # Save to database
        formatted_summary = analysis_result.get('formatted_summary', '')
        lab_report = LabReport.objects.create(
            email_id=email,
            report_file=report_files[0],
            extracted_text=raw_text,
            summary=formatted_summary,
            analysis=analysis_result,
            abnormal_values=analysis_result.get('biomarkers', [])
        )

        logger.info(f"Lab report saved: ID {lab_report.id} ({page_count} pages)")

        return Response({
            'success': True,
            'report_id': lab_report.id,
            'pages_processed': page_count,
            'test_type': analysis_result.get('report_type', 'Lab Report'),
            'summary': formatted_summary,
            'formatted_summary': formatted_summary,
            'abnormal_count': analysis_result.get('abnormal_count', 0),
            'normal_count': analysis_result.get('normal_count', 0),
            'parameters': analysis_result.get('biomarkers', []),
            'recommendations': [analysis_result.get('recommendation', '')],
            'overall_status': analysis_result.get('urgency_level', 'routine'),
            'follow_up_needed': analysis_result.get('follow_up_needed', False),
            'privacy': {
                'phi_entities_redacted': True,
                'processing_location': 'local',
                'cloud_received': 'anonymized_text_only',
            },
        })

    except ValueError as e:
        logger.warning(f"Lab report processing error: {e}")
        return Response({'error': str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    except Exception as e:
        logger.error(f"Lab report analysis error: {e}", exc_info=True)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 2: POST /api/lab-report/analyze/stream/ — SSE streaming
# ═══════════════════════════════════════════════════════════════════════════

@csrf_exempt
def stream_lab_report_view(request):
    """
    Server-Sent Events streaming endpoint for lab report analysis.

    POST /api/lab-report/analyze/stream/
    Body: multipart/form-data with email_id + report file(s)

    Events:
        stage  — Pipeline progress: {"id": str, "label": str, "icon": str}
        token  — Response word:     {"text": str}
        done   — Final metadata:    {report_id, test_type, parameters, ...}
        error  — Error:             {"message": str}
    """
    if request.method != "POST":
        return StreamingHttpResponse(
            _sse("error", {"message": "POST required"}),
            content_type="text/event-stream",
            status=405,
        )

    email = request.POST.get("email_id", "").strip()
    report_files = request.FILES.getlist("report")
    if not report_files:
        single_file = request.FILES.get("report")
        if single_file:
            report_files = [single_file]

    if not email or not report_files:
        return StreamingHttpResponse(
            _sse("error", {"message": "Missing email_id or report file"}),
            content_type="text/event-stream",
            status=400,
        )

    event_q = queue.Queue()

    def _pipeline_worker():
        """Run OCR → PHI → LLM streaming in a background thread."""
        try:
            # ── Stage 1: OCR ──
            event_q.put(("stage", {
                "id": "ocr",
                "label": "Extracting text from report...",
                "icon": "fa-eye",
            }))

            try:
                anonymized_text, raw_text, page_count = _extract_and_redact(report_files)
            except ValueError as e:
                event_q.put(("error", {"message": str(e)}))
                return

            event_q.put(("stage", {
                "id": "phi_done",
                "label": "Personal information removed",
                "icon": "fa-shield-alt",
            }))

            # ── Stage 2: LLM streaming analysis ──
            event_q.put(("stage", {
                "id": "analysis",
                "label": "Analyzing lab results...",
                "icon": "fa-microscope",
            }))

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    _run_streaming_analysis(anonymized_text, event_q)
                )
            finally:
                loop.close()

            if result is None:
                event_q.put(("error", {"message": "LLM analysis failed"}))
                return

            # ── Stage 3: Save to DB ──
            formatted_summary = result.get("formatted_summary", "")
            lab_report = LabReport.objects.create(
                email_id=email,
                report_file=report_files[0],
                extracted_text=raw_text,
                summary=formatted_summary,
                analysis=result,
                abnormal_values=result.get("biomarkers", []),
            )

            # ── Stream formatted summary word-by-word ──
            event_q.put(("stage", {
                "id": "streaming",
                "label": "",
                "icon": "fa-pen",
            }))
            event_q.put(("stream_summary", formatted_summary))

            # ── Done event with full metadata ──
            event_q.put(("done", {
                "report_id": lab_report.id,
                "pages_processed": page_count,
                "test_type": result.get("report_type", "Lab Report"),
                "abnormal_count": result.get("abnormal_count", 0),
                "normal_count": result.get("normal_count", 0),
                "parameters": result.get("biomarkers", []),
                "recommendations": [result.get("recommendation", "")],
                "overall_status": result.get("urgency_level", "routine"),
                "follow_up_needed": result.get("follow_up_needed", False),
                "privacy": {
                    "phi_entities_redacted": True,
                    "processing_location": "local",
                    "cloud_received": "anonymized_text_only",
                },
            }))

        except Exception as e:
            logger.error(f"Stream pipeline error: {e}", exc_info=True)
            event_q.put(("error", {"message": f"Pipeline error: {type(e).__name__}"}))
        finally:
            event_q.put(("end", None))

    def _event_generator():
        """SSE generator — reads from queue, yields events to client."""
        thread = threading.Thread(target=_pipeline_worker, daemon=True)
        thread.start()

        while True:
            try:
                event_type, data = event_q.get(timeout=5)
            except queue.Empty:
                # Heartbeat keeps connection alive during long processing
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
                # Smooth word-by-word streaming with natural pacing
                words = data.split(" ")
                word_count = len(words)
                # Adaptive speed: shorter reports feel natural, longer ones move faster
                if word_count < 200:
                    base_delay = 0.018
                elif word_count < 400:
                    base_delay = 0.010
                else:
                    base_delay = 0.005

                batch = []
                for i, word in enumerate(words):
                    batch.append(word)
                    # Flush batch at punctuation or every 3 words for smooth flow
                    is_last = (i == word_count - 1)
                    at_punctuation = word.rstrip().endswith((".", "!", "?", ":", "---"))
                    at_batch_limit = len(batch) >= 3

                    if is_last or at_punctuation or at_batch_limit:
                        text = " ".join(batch)
                        if not is_last:
                            text += " "
                        yield _sse("token", {"text": text})
                        batch = []

                        # Natural pauses at sentence boundaries
                        if at_punctuation:
                            _time.sleep(base_delay * 3)
                        else:
                            _time.sleep(base_delay)
            elif event_type == "done":
                yield _sse("done", data)

        thread.join(timeout=5)

    resp = StreamingHttpResponse(_event_generator(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


async def _run_streaming_analysis(anonymized_text: str, event_q: queue.Queue):
    """Run the streaming LLM analysis, collecting chunks silently."""
    try:
        result = None
        async for event_type, data in stream_lab_report_analysis(anonymized_text):
            if event_type == "complete":
                result = data["result"]
        return result
    except Exception as e:
        logger.error(f"Streaming analysis error: {e}", exc_info=True)
        return None


def _sse(event: str, data) -> str:
    """Format a single SSE event."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 3: GET /api/lab-report/history/ — Report history
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
def get_lab_report_history(request):
    """Get user's lab report history"""
    try:
        email = request.query_params.get('email_id')
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        reports = LabReport.objects.filter(email_id=email).order_by('-created_at')[:10]

        results = []
        for r in reports:
            summary_preview = r.summary[:200] + '...' if len(r.summary) > 200 else r.summary

            results.append({
                'id': r.id,
                'date': r.created_at.strftime('%Y-%m-%d %H:%M'),
                'test_type': r.analysis.get('report_type', 'Lab Report'),
                'abnormal_count': r.analysis.get('abnormal_count', 0),
                'summary': summary_preview,
                'overall_status': r.analysis.get('urgency_level', '')
            })

        return Response({
            'success': True,
            'count': len(results),
            'history': results
        })

    except Exception as e:
        logger.error(f"History retrieval error: {e}", exc_info=True)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
