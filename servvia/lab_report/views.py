"""
Lab Report Views — Privacy-Preserving Clinical Co-Pilot Pipeline
=================================================================

Uses the ServVia 5.0 pipeline:
    1. [LOCAL] DocumentExtractor (pdfplumber / easyocr) extracts raw text
    2. [LOCAL] IdentityExtractor pulls patient demographics (before redaction)
    3. [LOCAL] PHIRedactor strips patient-identifiable information
    4. [CLOUD] Co-Pilot LLM analyzes anonymized text + historical context

Endpoints:
    POST /api/lab-report/analyze/         — JSON response (backwards compat)
    POST /api/lab-report/analyze/stream/  — SSE streaming (real-time updates)
    GET  /api/lab-report/history/         — Report history

    === NEW (Co-Pilot) ===
    POST /api/lab-report/identify/        — Step 1: upload + identity fingerprint + profile match
    POST /api/lab-report/confirm/         — Step 2: confirm profile + run Co-Pilot analysis
    GET  /api/lab-report/profiles/        — List patient profiles for a user
    POST /api/lab-report/profiles/        — Create a new patient profile
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

from .models import LabReport, PatientProfile, BiomarkerSnapshot
from .profile_matcher import match_profile, update_profile_from_fingerprint, AUTO_ASSIGN_THRESHOLD
from edge.ocr_processor import DocumentExtractor
from edge.phi_redactor import PHIRedactor
from edge.identity_extractor import extract_identity
from agents.lab_summarizer import (
    analyze_lab_report,
    analyze_lab_report_copilot,
    stream_lab_report_analysis,
    _format_markdown_summary,
)
from user_profile.models import UserProfile

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


# ===============================================================================
# SHARED — Extract text + redact PHI (used by both endpoints)
# ===============================================================================

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


def _get_report_files(request):
    """Extract report files from request, handling single or multi upload."""
    report_files = request.FILES.getlist('report')
    if not report_files:
        single_file = request.FILES.get('report')
        if single_file:
            report_files = [single_file]
    return report_files


# ===============================================================================
# ENDPOINT 1: POST /api/lab-report/analyze/ — JSON response (LEGACY, UNCHANGED)
# ===============================================================================

@api_view(['POST'])
def analyze_lab_report_view(request):
    """Endpoint to upload and analyze lab reports via the pipeline."""
    try:
        email = request.data.get('email_id')
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        report_files = _get_report_files(request)
        if not report_files:
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


# ===============================================================================
# ENDPOINT 2: POST /api/lab-report/analyze/stream/ — SSE streaming (LEGACY)
# ===============================================================================

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
    session_id = request.POST.get("session_id", "").strip()
    report_files = request.FILES.getlist("report")
    if not report_files:
        single_file = request.FILES.get("report")
        if single_file:
            report_files = [single_file]

    # Set session scope so lab results land in the right conversation session
    if email and session_id:
        try:
            from core_temporal.conversation.manager import conversation_manager
            conversation_manager.set_session(email, session_id)
        except Exception:
            pass

    if not email or not report_files:
        return StreamingHttpResponse(
            _sse("error", {"message": "Missing email_id or report file"}),
            content_type="text/event-stream",
            status=400,
        )

    event_q = queue.Queue()

    def _pipeline_worker():
        """Run OCR -> PHI -> LLM streaming in a background thread."""
        try:
            # -- Stage 1: OCR --
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

            # -- Stage 2: LLM streaming analysis --
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

            # -- Stage 3: Save to DB --
            formatted_summary = result.get("formatted_summary", "")
            lab_report = LabReport.objects.create(
                email_id=email,
                report_file=report_files[0],
                extracted_text=raw_text,
                summary=formatted_summary,
                analysis=result,
                abnormal_values=result.get("biomarkers", []),
            )

            # -- Inject lab results into conversation context --
            try:
                from core_temporal.conversation.manager import conversation_manager
                # Build a concise lab context for conversation memory
                abnormal_count = result.get("abnormal_count", 0)
                normal_count = result.get("normal_count", 0)
                biomarkers = result.get("biomarkers", [])
                abnormal_names = [
                    b.get("name", "") for b in biomarkers
                    if b.get("status", "").lower() != "normal"
                ] if isinstance(biomarkers, list) else []

                lab_context_msg = (
                    f"[LAB REPORT ANALYZED — {result.get('report_type', 'Lab Report')}]\n"
                    f"Parameters: {abnormal_count + normal_count} tested | "
                    f"{normal_count} normal | {abnormal_count} abnormal\n"
                )
                if abnormal_names:
                    lab_context_msg += f"Abnormal: {', '.join(abnormal_names)}\n"
                lab_context_msg += f"Urgency: {result.get('urgency_level', 'routine')}\n"
                lab_context_msg += f"Recommendation: {result.get('recommendation', 'Consult physician')}"

                conversation_manager.add_message(
                    email, 'user', f"[User uploaded a lab report for analysis]",
                    metadata={"type": "lab_upload"}
                )
                conversation_manager.add_message(
                    email, 'assistant', lab_context_msg,
                    metadata={
                        "type": "lab_analysis",
                        "report_id": lab_report.id,
                        "abnormal_values": abnormal_names,
                    }
                )
                logger.info(f"Lab results saved to conversation context for {email}")
            except Exception as e:
                logger.warning(f"Failed to save lab context to conversation: {e}")

            # -- Stream formatted summary word-by-word --
            event_q.put(("stage", {
                "id": "streaming",
                "label": "",
                "icon": "fa-pen",
            }))
            event_q.put(("stream_summary", formatted_summary))

            # -- Done event with full metadata --
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
                # Word-by-word streaming — matches chat pattern exactly
                words = data.split(" ")
                word_count = len(words)
                # Adaptive speed: same formula as chat stream
                base_delay = 0.015 if word_count < 300 else (0.008 if word_count < 700 else 0.004)

                for i, word in enumerate(words):
                    yield _sse("token", {"text": word + (" " if i < word_count - 1 else "")})
                    if word.endswith((".", "!", "?", ":")):
                        _time.sleep(base_delay * 2.5)
                    elif word.endswith((",", ";", "—")):
                        _time.sleep(base_delay * 1.5)
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
    from contextlib import aclosing
    try:
        result = None
        async with aclosing(stream_lab_report_analysis(anonymized_text)) as gen:
            async for event_type, data in gen:
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


# ===============================================================================
# ENDPOINT 3: GET /api/lab-report/history/ — Report history (LEGACY, UNCHANGED)
# ===============================================================================

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


# ===============================================================================
# ENDPOINT 4: POST /api/lab-report/identify/ — Identity fingerprint + routing
# ===============================================================================

@api_view(['POST'])
def identify_lab_report_view(request):
    """
    Step 1 of the Co-Pilot flow: upload report, extract identity, match profiles.

    POST /api/lab-report/identify/
    Body: multipart/form-data with email_id + report file(s)

    Returns one of:
        {"status": "profile_matched", "profile_id": N, "confidence": 0.95, ...}
        {"status": "profile_confirm", "candidates": [...], "identity": {...}, ...}
        {"status": "profile_new", "identity": {...}, ...}
    """
    try:
        email = request.data.get('email_id')
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        report_files = _get_report_files(request)
        if not report_files:
            return Response(
                {'error': 'At least one report file is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(f"[Co-Pilot] Identity phase for {email}, {len(report_files)} file(s)")

        # Step 1: Extract raw text (LOCAL)
        extractor = _get_extractor()
        redactor = _get_redactor()
        all_raw_text = ""

        for idx, report_file in enumerate(report_files, 1):
            ext = os.path.splitext(report_file.name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                return Response(
                    {'error': f"Unsupported file type: {ext}"},
                    status=status.HTTP_400_BAD_REQUEST,
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

                extracted = extractor.extract(tmp_path)
                if extracted:
                    all_raw_text += f"\n\n=== PAGE {idx} ===\n\n{extracted}"
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

        if not all_raw_text.strip():
            return Response(
                {'error': 'Could not extract text from the uploaded file(s).'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # Step 2: Extract identity from RAW text (before PHI redaction)
        loop = asyncio.new_event_loop()
        try:
            fingerprint = loop.run_until_complete(extract_identity(all_raw_text))
        finally:
            loop.close()

        # Step 3: Redact PHI for storage
        anonymized_text = redactor.anonymize_text(all_raw_text)

        # Step 4: Create a pending (unconfirmed) LabReport
        lab_report = LabReport.objects.create(
            email_id=email,
            report_file=report_files[0],
            extracted_text=all_raw_text,
            identity_meta=fingerprint.to_dict(),
            profile_confirmed=False,
        )

        # Step 5: Match against existing profiles
        try:
            user_profile = UserProfile.objects.get(email=email)
            profiles = list(PatientProfile.objects.filter(user_profile=user_profile))
        except UserProfile.DoesNotExist:
            profiles = []

        identity_data = fingerprint.to_dict()

        if not profiles:
            # No profiles exist — ask user to create one
            return Response({
                'status': 'profile_new',
                'pending_report_id': lab_report.id,
                'identity': identity_data,
                'message': 'No patient profiles found. Please create one to continue.',
            })

        best_profile, confidence, candidates = match_profile(fingerprint, profiles)

        if confidence >= AUTO_ASSIGN_THRESHOLD:
            return Response({
                'status': 'profile_matched',
                'pending_report_id': lab_report.id,
                'profile_id': best_profile.id,
                'profile_label': best_profile.label,
                'confidence': confidence,
                'identity': identity_data,
                'message': f'Auto-matched to "{best_profile.label}" (confidence: {confidence})',
            })
        else:
            return Response({
                'status': 'profile_confirm',
                'pending_report_id': lab_report.id,
                'candidates': candidates,
                'identity': identity_data,
                'message': 'Could not confidently match a profile. Please select or create one.',
            })

    except ValueError as e:
        logger.warning(f"[Co-Pilot] Identity phase error: {e}")
        return Response({'error': str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    except Exception as e:
        logger.error(f"[Co-Pilot] Identity phase error: {e}", exc_info=True)
        return Response(
            {'error': 'An error occurred during identity extraction. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ===============================================================================
# ENDPOINT 5: POST /api/lab-report/confirm/ — Confirm profile + run Co-Pilot
# ===============================================================================

@api_view(['POST'])
def confirm_and_analyze_view(request):
    """
    Step 2 of the Co-Pilot flow: confirm profile, run full analysis.

    POST /api/lab-report/confirm/
    Body (JSON):
        {
            "pending_report_id": 42,
            "profile_id": 5,         // existing profile ID
            // OR
            "create_profile": true,   // create new profile
            "profile_label": "Dad's Health"
        }

    Returns: Full Co-Pilot analysis with triage, action plan, delta tracking.
    """
    try:
        report_id = request.data.get('pending_report_id')
        if not report_id:
            return Response(
                {'error': 'pending_report_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch the pending report
        try:
            lab_report = LabReport.objects.get(id=report_id, profile_confirmed=False)
        except LabReport.DoesNotExist:
            return Response(
                {'error': 'Pending report not found or already processed.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        email = lab_report.email_id

        # Resolve or create profile
        profile_id = request.data.get('profile_id')
        create_profile = request.data.get('create_profile', False)

        if create_profile:
            # Create a new patient profile
            try:
                user_profile = UserProfile.objects.get(email=email)
            except UserProfile.DoesNotExist:
                # Auto-create UserProfile if needed
                user_profile = UserProfile.objects.create(email=email)

            label = request.data.get('profile_label', 'My Health')
            identity_meta = lab_report.identity_meta or {}

            patient_profile, created = PatientProfile.objects.get_or_create(
                user_profile=user_profile,
                label=label,
                defaults={
                    'patient_name': identity_meta.get('patient_name') or '',
                    'age': identity_meta.get('age'),
                    'sex': identity_meta.get('sex') or '',
                    'external_ids': {
                        k: v for k, v in {
                            'patient_id': identity_meta.get('patient_id'),
                            'SRF_ID': identity_meta.get('srf_id'),
                        }.items() if v
                    },
                },
            )
            if not created:
                return Response(
                    {'error': f'A profile with label "{label}" already exists. Use its profile_id instead.'},
                    status=status.HTTP_409_CONFLICT,
                )
        elif profile_id:
            try:
                patient_profile = PatientProfile.objects.get(id=profile_id)
            except PatientProfile.DoesNotExist:
                return Response(
                    {'error': 'Profile not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            # Enrich profile with newly extracted identity
            from edge.identity_extractor import IdentityFingerprint
            fp = IdentityFingerprint(**lab_report.identity_meta) if lab_report.identity_meta else None
            if fp:
                update_profile_from_fingerprint(patient_profile, fp)
        else:
            return Response(
                {'error': 'Either profile_id or create_profile is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Link report to profile
        lab_report.patient_profile = patient_profile
        lab_report.profile_confirmed = True

        # PHI redaction
        redactor = _get_redactor()
        anonymized_text = redactor.anonymize_text(lab_report.extracted_text)

        # Fetch historical snapshots for this profile (last 3)
        historical_snapshots = []
        past_snapshots = BiomarkerSnapshot.objects.filter(
            patient_profile=patient_profile
        ).order_by('-report_date', '-created_at')[:3]

        for snap in past_snapshots:
            historical_snapshots.append(snap.biomarkers_json)

        # Run Co-Pilot analysis
        loop = asyncio.new_event_loop()
        try:
            analysis_result = loop.run_until_complete(
                analyze_lab_report_copilot(anonymized_text, historical_snapshots)
            )
        except ValueError as e:
            logger.error(f"[Co-Pilot] Analysis failed: {e}")
            return Response(
                {'error': f'Analysis failed: {e}'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except Exception as e:
            logger.error(f"[Co-Pilot] Analysis error: {e}", exc_info=True)
            return Response(
                {'error': 'The AI analysis engine encountered an error. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            loop.close()

        # Save analysis to report
        formatted_summary = analysis_result.get('formatted_summary', '')
        lab_report.summary = formatted_summary
        lab_report.analysis = analysis_result
        lab_report.abnormal_values = analysis_result.get('biomarkers', [])
        lab_report.save()

        # Create BiomarkerSnapshot for longitudinal memory
        BiomarkerSnapshot.objects.create(
            patient_profile=patient_profile,
            lab_report=lab_report,
            report_date=_parse_report_date(analysis_result.get('report_date')),
            biomarkers_json=analysis_result.get('biomarkers', []),
            abnormal_count=analysis_result.get('abnormal_count', 0),
        )

        logger.info(
            f"[Co-Pilot] Analysis complete for report {lab_report.id}, "
            f"profile '{patient_profile.label}'"
        )

        return Response({
            'success': True,
            'report_id': lab_report.id,
            'profile_id': patient_profile.id,
            'profile_label': patient_profile.label,
            'test_type': analysis_result.get('report_type', 'Lab Report'),
            'summary': formatted_summary,
            'formatted_summary': formatted_summary,
            'system_groups': analysis_result.get('system_groups', []),
            'triage': analysis_result.get('triage', {}),
            'action_plan': analysis_result.get('action_plan', {}),
            'delta_tracking': analysis_result.get('delta_tracking', []),
            'abnormal_count': analysis_result.get('abnormal_count', 0),
            'normal_count': analysis_result.get('normal_count', 0),
            'urgency_level': analysis_result.get('urgency_level', 'routine'),
            'privacy': {
                'phi_entities_redacted': True,
                'processing_location': 'local',
                'cloud_received': 'anonymized_text_only',
            },
        })

    except Exception as e:
        logger.error(f"[Co-Pilot] Confirm+Analyze error: {e}", exc_info=True)
        return Response(
            {'error': 'An unexpected error occurred. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def _parse_report_date(date_str):
    """Best-effort parse of report date string into a date object."""
    if not date_str:
        return None
    from datetime import datetime
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %B %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


# ===============================================================================
# ENDPOINT 6: GET/POST /api/lab-report/profiles/ — Patient profile management
# ===============================================================================

@api_view(['GET', 'POST'])
def patient_profiles_view(request):
    """
    GET  /api/lab-report/profiles/?email_id=...  — List profiles
    POST /api/lab-report/profiles/               — Create a new profile
    """
    if request.method == 'GET':
        return _list_profiles(request)
    return _create_profile(request)


def _list_profiles(request):
    """List all patient profiles for a user."""
    try:
        email = request.query_params.get('email_id')
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user_profile = UserProfile.objects.get(email=email)
        except UserProfile.DoesNotExist:
            return Response({'success': True, 'profiles': []})

        profiles = PatientProfile.objects.filter(user_profile=user_profile)
        results = []
        for p in profiles:
            report_count = LabReport.objects.filter(patient_profile=p).count()
            results.append({
                'id': p.id,
                'label': p.label,
                'patient_name': p.patient_name,
                'age': p.age,
                'sex': p.sex,
                'report_count': report_count,
                'created_at': p.created_at.strftime('%Y-%m-%d'),
            })

        return Response({'success': True, 'profiles': results})

    except Exception as e:
        logger.error(f"Profile list error: {e}", exc_info=True)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _create_profile(request):
    """Create a new patient profile."""
    try:
        email = request.data.get('email_id')
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        label = request.data.get('label', 'My Health')

        try:
            user_profile = UserProfile.objects.get(email=email)
        except UserProfile.DoesNotExist:
            user_profile = UserProfile.objects.create(email=email)

        if PatientProfile.objects.filter(user_profile=user_profile, label=label).exists():
            return Response(
                {'error': f'A profile with label "{label}" already exists.'},
                status=status.HTTP_409_CONFLICT,
            )

        patient_profile = PatientProfile.objects.create(
            user_profile=user_profile,
            label=label,
            patient_name=request.data.get('patient_name', ''),
            age=request.data.get('age'),
            sex=request.data.get('sex', ''),
        )

        return Response({
            'success': True,
            'profile': {
                'id': patient_profile.id,
                'label': patient_profile.label,
                'patient_name': patient_profile.patient_name,
                'age': patient_profile.age,
                'sex': patient_profile.sex,
            },
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Profile creation error: {e}", exc_info=True)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
