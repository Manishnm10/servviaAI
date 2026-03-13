from rest_framework. decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import SkinAnalysis
from .disease_detector import SkinDiseaseDetector, detect_skin_disease_gemini, validate_skin_image
import logging
import tempfile
import os
from PIL import Image
import io

logger = logging.getLogger(__name__)

# Initialize detector lazily
_detector = None

def get_detector():
    global _detector
    if _detector is None: 
        _detector = SkinDiseaseDetector()
    return _detector

@api_view(['POST'])
def analyze_skin_image(request):
    """Endpoint to upload and analyze skin images"""
    temp_path = None
    
    try:
        email = request.data.get('email_id')
        if not email:
            return Response({
                'success': False,
                'error': 'Email is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        image_file = request.FILES.get('image')
        if not image_file:
            return Response({
                'success': False,
                'error': 'Image file is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save image to temp file for validation
        try:
            image_data = image_file.read()
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if needed
            if image.mode != 'RGB': 
                image = image.convert('RGB')
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='. jpg') as tmp:
                image.save(tmp.name)
                temp_path = tmp. name
        except Exception as e: 
            logger.error(f"Image processing error: {e}")
            return Response({
                'success': False,
                'error':  'Invalid image file.  Please upload a valid JPG or PNG image.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate that this is actually a skin image
        logger. info("🔍 Validating uploaded image...")
        validation = validate_skin_image(temp_path)
        
        if not validation['is_skin_image']:
            logger.warning(f"⚠️ Invalid image type:  {validation['reason']}")
            
            # Clean up temp file
            try: 
                os.unlink(temp_path)
            except:
                pass
            
            return Response({
                'success': False,
                'error': validation['reason'],
                'error_type': 'invalid_image_type',
                'suggestion': 'Please upload a clear photograph of the affected skin area.  Documents, lab reports, screenshots, and text images are not supported.'
            }, status=status. HTTP_400_BAD_REQUEST)
        
        logger.info("✅ Image validation passed - proceeding with analysis")

        # Use detect_skin_disease_gemini directly with temp_path
        result = detect_skin_disease_gemini(temp_path)

        # Clean up temp file
        try:
            os.unlink(temp_path)
        except:
            pass

        # Check if detection was successful
        if not result. get('success'):
            error_message = result.get('error', 'Unable to analyze image')
            logger.error(f"Detection failed: {error_message}")
    
            return Response({
                'success':  False,
                'error': error_message
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Extract results
        disease = result.get('disease', 'Unknown')
        confidence_score = result.get('confidence_score', 0.0)
        recommendations_list = result.get('recommendations', [])
        
        # Add additional metadata
        severity = result.get('severity', 'Unknown')
        urgency_note = result.get('urgency_note', '')
        description = result.get('description', '')

        # Format recommendations with proper line breaks and numbering
        formatted_recommendations = ""
        if recommendations_list:
            for i, rec in enumerate(recommendations_list, 1):
                formatted_recommendations += f"{i}. {rec}\n"

        # Add ambiguity note for commonly confused conditions
        ambiguity_note = ""
        if disease in ["Heat Rash (Prickly Heat)", "Hives (Urticaria)"]:
            ambiguity_note = (
                "\n\n🔍 **Note:** Heat Rash and Hives look very similar in photos.\n\n"
                "• Heat Rash: Usually after sweating/heat exposure, tiny uniform bumps\n\n"
                "• Hives: Usually after allergic reaction, raised welts that come and go\n\n"
                "Consider your recent activities to help determine which condition you have."
            )

        # Build final recommendations with ambiguity note
        recommendations = formatted_recommendations + ambiguity_note

        # Save analysis to database
        # Reset file pointer for saving
        image_file.seek(0)

        analysis = SkinAnalysis. objects.create(
            email_id=email,
            image=image_file,
            diagnosis=disease,
            confidence_score=confidence_score,
            recommendations=recommendations
        )

        logger.info(f"✅ Analysis saved for {email}:  {disease} ({confidence_score*100:.1f}%)")

        return Response({
            'success': True,
            'diagnosis':  disease,
            'confidence':  round(confidence_score * 100, 2),
            'severity': severity,
            'description':  description,
            'recommendations': recommendations,
            'urgency_note': urgency_note,
            'analysis_id': analysis.id,
            'visual_analysis': result.get('visual_analysis', {}),
            'distinguishing_features': result.get('distinguishing_features', ''),
            'differential_diagnosis': result.get('differential_diagnosis', []),
            'timestamp': result.get('timestamp', '')
        })
        
    except Exception as e: 
        logger.error(f"Skin analysis error: {e}", exc_info=True)
        
        # Clean up temp file if it exists
        if temp_path: 
            try:
                os. unlink(temp_path)
            except:
                pass
        
        return Response({
            'success': False,
            'error': f'An unexpected error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_skin_analysis_history(request):
    """Get user's skin analysis history"""
    try:
        email = request.query_params.get('email_id')
        
        if not email:
            return Response({
                'success': False,
                'error': 'Email is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        analyses = SkinAnalysis.objects. filter(email_id=email).order_by('-created_at')[: 10]
        
        results = [{
            'id': a.id,
            'diagnosis':  a.diagnosis,
            'confidence':  round(a.confidence_score * 100, 2),
            'date': a.created_at.strftime('%Y-%m-%d %H:%M'),
            'image_url': request.build_absolute_uri(a.image.url) if a.image else None
        } for a in analyses]
        
        return Response({
            'success': True,
            'history': results,
            'count': len(results)
        })
        
    except Exception as e:
        logger.error(f"History retrieval error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
