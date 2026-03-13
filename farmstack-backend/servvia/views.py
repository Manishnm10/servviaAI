from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
import openai
from django.conf import settings
import base64
import json

from .models import UserMedicalProfile, ChatSession, ChatMessage, MedicalImageAnalysis
from .serializers import (
    UserMedicalProfileSerializer, ChatSessionSerializer,
    ChatMessageSerializer, MedicalImageAnalysisSerializer
)

class UserMedicalProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserMedicalProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserMedicalProfile.objects.filter(user=self.request.user)
    
    def get_object(self):
        profile, _ = UserMedicalProfile.objects.get_or_create(user=self.request.user)
        return profile
    
    @action(detail=False, methods=['post'])
    def complete_onboarding(self, request):
        profile = self.get_object()
        
        profile.medical_conditions = request.data.get('medical_conditions', [])
        profile.current_medications = request.data.get('current_medications', [])
        profile.allergies = request.data.get('allergies', [])
        profile.age_group = request.data.get('age_group', '')
        profile.dietary_restrictions = request.data.get('dietary_restrictions', [])
        profile.pregnancy_status = request.data.get('pregnancy_status', False)
        profile.is_profile_complete = True
        profile.onboarding_completed_at = timezone.now()
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
        return ChatSession.objects.filter(user=self.request.user)
    
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

SAFETY: Always recommend medical consultation for serious symptoms. Never diagnose.

USER PROFILE:
- Conditions: {', '.join(profile.medical_conditions) if profile else 'None'}
- Medications: {', '.join(profile.current_medications) if profile else 'None'}
- Allergies: {', '.join(profile.allergies) if profile else 'None'}

AVOID: {', '.join(contraindications) if contraindications else 'None'}

Provide personalized, safe home remedy suggestions."""

        chat_history = [{"role": m.role, "content": m.content} for m in session.messages.order_by('created_at')]
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
            content=response.choices[0].message.content,
            tokens_used=response.usage.total_tokens,
            model_used='gpt-4'
        )
        
        return Response(ChatMessageSerializer(assistant_message).data)

class MedicalImageViewSet(viewsets.ModelViewSet):
    serializer_class = MedicalImageAnalysisSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return MedicalImageAnalysis.objects.filter(user=self.request.user)
    
    def create(self, request):
        image = request.FILES.get('image')
        if not image:
            return Response({'error': 'No image provided'}, status=400)
        
        analysis = MedicalImageAnalysis.objects.create(user=request.user, image=image)
        
        try:
            profile = request.user.medical_profile
        except:
            profile = None
        
        vision_prompt = f"""Analyze this medical image and provide JSON with:
- description: what you see
- severity: low/medium/high
- needs_doctor: true/false
- remedies: array of safe home remedies

{"User has: " + ', '.join(profile.medical_conditions) if profile else ""}
{"Avoid: " + ', '.join(profile.get_contraindications()) if profile else ""}"""
        
        with open(analysis.image.path, "rb") as img:
            image_base64 = base64.b64encode(img.read()).decode('utf-8')
        
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": vision_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]
            }],
            max_tokens=500
        )
        
        result = json.loads(response.choices[0].message.content)
        analysis.analysis_result = result
        analysis.detected_conditions = [result.get('description', '')]
        analysis.suggested_remedies = result.get('remedies', [])
        analysis.severity_level = result.get('severity', 'medium')
        analysis.requires_medical_attention = result.get('needs_doctor', False)
        analysis.save()
        
        return Response(MedicalImageAnalysisSerializer(analysis).data, status=201)
