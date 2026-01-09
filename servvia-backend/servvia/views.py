from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework. permissions import IsAuthenticated
from django.utils import timezone
import openai
from django.conf import settings
import os

from .models import UserMedicalProfile, ChatSession, ChatMessage, MedicalImageAnalysis, LabReportAnalysis
from .serializers import (
    UserMedicalProfileSerializer, ChatSessionSerializer,
    ChatMessageSerializer, MedicalImageAnalysisSerializer, LabReportAnalysisSerializer
)
from .ai_service import EnhancedMedicalAI

class UserMedicalProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserMedicalProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserMedicalProfile.objects.filter(user=self.request.user)
    
    def get_object(self):
        profile, _ = UserMedicalProfile. objects.get_or_create(user=self.request.user)
        return profile
    
    @action(detail=False, methods=['post'])
    def complete_onboarding(self, request):
        profile = self.get_object()
        
        profile.medical_conditions = request.data.get('medical_conditions', [])
        profile.current_medications = request.data.get('current_medications', [])
        profile.allergies = request. data.get('allergies', [])
        profile.age_group = request.data.get('age_group', '')
        profile.dietary_restrictions = request.data.get('dietary_restrictions', [])
        profile.pregnancy_status = request.data.get('pregnancy_status', False)
        profile.is_profile_complete = True
        profile. onboarding_completed_at = timezone.now()
        profile.save()
        
        return Response(UserMedicalProfileSerializer(profile).data)
    
    @action(detail=False, methods=['get'])
    def check_status(self, request):
        profile = self.get_object()
        return Response({
            'is_complete': profile.is_profile_complete,
            'profile': UserMedicalProfileSerializer(profile).data
        })

class ChatViewSet(viewsets.ModelViewSet):
    serializer_class = ChatSessionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return ChatSession.objects. filter(user=self.request. user)
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        session = self.get_object()
        user_message = request.data.get('message', '')
        
        ChatMessage.objects.create(session=session, role='user', content=user_message)
        
        try:
            profile = request.user.medical_profile
            contraindications = profile.get_contraindications()
        except:
            profile = None
            contraindications = []
        
        system_prompt = f"""You are Servvia, a compassionate medical assistant specializing in home remedies. 

SAFETY: Always recommend medical consultation for serious symptoms.  Never diagnose.

USER PROFILE:
- Conditions: {', '.join(profile.medical_conditions) if profile else 'None'}
- Medications: {', '.join(profile.current_medications) if profile else 'None'}
- Allergies: {', '.join(profile.allergies) if profile else 'None'}

AVOID: {', '.join(contraindications) if contraindications else 'None'}

Provide personalized, safe home remedy suggestions."""

        chat_history = [{"role": m.role, "content": m. content} for m in session.messages. order_by('created_at')]
        messages = [{"role": "system", "content": system_prompt}] + chat_history
        
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=500
        )
        
        assistant_message = ChatMessage.objects.create(
            session=session,
            role='assistant',
            content=response. choices[0].message.content,
            tokens_used=response.usage.total_tokens,
            model_used='gpt-4'
        )
        
        return Response(ChatMessageSerializer(assistant_message). data)

class MedicalImageViewSet(viewsets.ModelViewSet):
    """Enhanced Medical Image Analysis for Skin Conditions"""
    serializer_class = MedicalImageAnalysisSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return MedicalImageAnalysis.objects.filter(user=self.request.user)
    
    def create(self, request):
        image = request.FILES.get('image')
        if not image:
            return Response({'error': 'No image provided'}, status=400)
        
        # Create initial record
        analysis = MedicalImageAnalysis.objects.create(user=request.user, image=image)
        
        # Get user profile
        try:
            profile = request.user.medical_profile
        except:
            profile = None
        
        # Use enhanced AI service
        ai_service = EnhancedMedicalAI()
        result = ai_service.analyze_skin_condition(analysis.image. path, profile)
        
        # Update analysis with results
        analysis.analysis_result = result
        analysis.detected_conditions = [result.get('condition_name', 'Unknown')]
        analysis.suggested_remedies = result.get('safe_home_remedies', [])
        analysis.severity_level = result.get('severity', 'medium')
        analysis.requires_medical_attention = result.get('needs_immediate_attention', False)
        analysis.save()
        
        return Response(MedicalImageAnalysisSerializer(analysis).data, status=201)


class LabReportViewSet(viewsets.ModelViewSet):
    """Lab Report Analysis and Summarization"""
    serializer_class = LabReportAnalysisSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return LabReportAnalysis.objects.filter(user=self.request.user)
    
    def create(self, request):
        report_file = request.FILES.get('report_file')
        if not report_file:
            return Response({'error': 'No report file provided'}, status=400)
        
        # Create record
        analysis = LabReportAnalysis.objects.create(
            user=request.user,
            report_file=report_file
        )
        
        # Get user profile
        try:
            profile = request.user.medical_profile
        except:
            profile = None
        
        # Analyze report
        ai_service = EnhancedMedicalAI()
        file_path = analysis.report_file.path
        file_extension = os.path.splitext(file_path)[1]
        
        result = ai_service.analyze_lab_report(file_path, file_extension, profile)
        
        if 'error' in result:
            analysis.delete()  # Clean up failed analysis
            return Response({'error': result['error']}, status=400)
        
        # Update analysis
        analysis.extracted_text = result.get('extracted_text', '')
        analysis. report_type = result.get('report_type', 'general')
        analysis.summary = result.get('summary', '')
        analysis.abnormal_findings = result.get('abnormal_findings', [])
        analysis.personalized_recommendations = result.get('personalized_recommendations', [])
        analysis.requires_doctor_consultation = result.get('needs_doctor_consultation', False)
        analysis. analysis_result = result
        analysis.save()
        
        return Response(LabReportAnalysisSerializer(analysis).data, status=201)