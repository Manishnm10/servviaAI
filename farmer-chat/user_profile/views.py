from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework import status
from django.utils import timezone
from .models import UserProfile
import logging

logger = logging.getLogger(__name__)

class UserProfileViewSet(GenericViewSet):
    authentication_classes = []
    
    @action(detail=False, methods=['post'])
    def check_profile(self, request):
        """Check if profile exists - accepts both email and email_id"""
        email = request.data.get('email') or request.data.get('email_id')
        
        if not email:
            return Response({'error': True, 'message': 'Email required'}, status=400)
        
        try:
            profile = UserProfile.objects.get(email=email)
            profile.last_login = timezone.now()
            profile.save()
            
            return Response({
                'exists': True,
                'is_complete': profile.is_profile_complete,
                'profile': {
                    'email': profile.email,
                    'first_name': profile.first_name,
                    'allergies': profile.allergies,
                    'medical_conditions': profile.medical_conditions,
                    'current_medications': profile.current_medications,
                }
            })
        except UserProfile.DoesNotExist:
            return Response({'exists': False, 'is_complete': False})
    
    @action(detail=False, methods=['post'])
    def get_profile(self, request):
        """Get profile data - NEW endpoint for frontend"""
        email = request.data.get('email') or request.data.get('email_id')
        
        if not email:
            return Response({'error': True, 'message': 'Email required'}, status=400)
        
        try:
            profile = UserProfile.objects.get(email=email)
            return Response({
                'exists': True,
                'profile': {
                    'email': profile.email,
                    'first_name': profile.first_name,
                    'allergies': profile.allergies,
                    'medical_conditions': profile.medical_conditions,
                    'current_medications': profile.current_medications,
                }
            })
        except UserProfile.DoesNotExist:
            return Response({'exists': False, 'profile': {}})
    
    @action(detail=False, methods=['post'])
    def save_profile(self, request):
        """Save profile - NEW endpoint for frontend"""
        email = request.data.get('email') or request.data.get('email_id')
        first_name = request.data.get('first_name', '')
        allergies = request.data.get('allergies', '')
        medical_conditions = request.data.get('medical_conditions', '')
        current_medications = request.data.get('current_medications', '')
        
        if not email:
            return Response({'error': True, 'message': 'Email required'}, status=400)
        
        try:
            profile, created = UserProfile.objects.update_or_create(
                email=email,
                defaults={
                    'first_name': first_name,
                    'allergies': allergies,
                    'medical_conditions': medical_conditions,
                    'current_medications': current_medications,
                }
            )
            
            profile.mark_profile_complete()
            
            action_text = 'created' if created else 'updated'
            logger.info(f"Profile {action_text} for {email}")
            
            return Response({
                'success': True,
                'message': f'Profile {action_text} successfully',
                'created': created,
                'profile': {
                    'email': profile.email,
                    'first_name': profile.first_name,
                    'allergies': profile.allergies,
                    'medical_conditions': profile.medical_conditions,
                    'current_medications': profile.current_medications,
                }
            })
        except Exception as e:
            logger.error(f"Profile error: {e}", exc_info=True)
            return Response({'error': True, 'message': str(e)}, status=500)
    
    @action(detail=False, methods=['post'])
    def create_or_update_profile(self, request):
        """Legacy endpoint - kept for compatibility"""
        return self.save_profile(request)
