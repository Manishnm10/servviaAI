from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import LabReport
from .report_analyzer import LabReportAnalyzer
import logging

logger = logging.getLogger(__name__)

_analyzer = None


def get_analyzer():
    global _analyzer
    if _analyzer is None:
        _analyzer = LabReportAnalyzer()
    return _analyzer


@api_view(['POST'])
def analyze_lab_report(request):
    """Endpoint to upload and analyze lab reports"""
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

        analyzer = get_analyzer()
        all_extracted_text = ""

        # Process each uploaded page
        for idx, report_file in enumerate(report_files, 1):
            logger.info(f"Processing page {idx}/{len(report_files)}")

            extracted_text = analyzer.extract_text_from_pdf(report_file)

            if extracted_text:
                all_extracted_text += f"\n\n=== PAGE {idx} ===\n\n{extracted_text}"
            else:
                logger.warning(f"No text extracted from page {idx}")

        if not all_extracted_text.strip():
            return Response(
                {'error': 'Could not extract text. Ensure images/PDFs are clear.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(f"Extracted {len(all_extracted_text)} characters from {len(report_files)} page(s)")

        analysis_result = analyzer.summarize_report(all_extracted_text, email)

        if not analysis_result.get('success'):
            return Response(
                {'error': analysis_result.get('error', 'Analysis failed')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Save to database
        lab_report = LabReport.objects.create(
            email_id=email,
            report_file=report_files[0],
            extracted_text=all_extracted_text,
            summary=analysis_result.get('summary', ''),
            analysis=analysis_result.get('analysis', {}),
            abnormal_values=analysis_result.get('abnormal_values', [])
        )

        logger.info(f"Lab report saved: ID {lab_report.id} ({len(report_files)} pages)")

        formatted_summary = analysis_result.get('summary', '')
        if not formatted_summary or formatted_summary == 'undefined':
            formatted_summary = (
                analysis_result.get('analysis', {}).get('summary', 'No summary available')
            )

        response_data = {
            'success': True,
            'report_id': lab_report.id,
            'pages_processed': len(report_files),
            'test_type': analysis_result.get('analysis', {}).get('test_type', 'Lab Report'),
            'report_date': analysis_result.get('analysis', {}).get('report_date', ''),
            'summary': formatted_summary,
            'formatted_summary': formatted_summary,
            'abnormal_count': analysis_result.get('analysis', {}).get('abnormal_count', 0),
            'normal_count': analysis_result.get('visual_indicators', {}).get('normal_count', 0),
            'critical_count': analysis_result.get('visual_indicators', {}).get('critical_count', 0),
            'parameters': analysis_result.get('abnormal_values', []),
            'recommendations': analysis_result.get('recommendations', []),
            'critical_flags': analysis_result.get('critical_flags', []),
            'overall_status': analysis_result.get('analysis', {}).get('overall_status', ''),
            'follow_up_needed': analysis_result.get('analysis', {}).get('follow_up_needed', False),
        }

        return Response(response_data)

    except Exception as e:
        logger.error(f"Lab report analysis error: {e}", exc_info=True)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
                'test_type': r.analysis.get('test_type', 'Lab Report'),
                'abnormal_count': r.analysis.get('abnormal_count', 0),
                'summary': summary_preview,
                'overall_status': r.analysis.get('overall_status', '')
            })

        return Response({
            'success': True,
            'count': len(results),
            'history': results
        })

    except Exception as e:
        logger.error(f"History retrieval error: {e}", exc_info=True)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

