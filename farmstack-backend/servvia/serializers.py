from rest_framework import serializers
from .models import UserMedicalProfile, ChatSession, ChatMessage, MedicalImageAnalysis

class UserMedicalProfileSerializer(serializers.ModelSerializer):
    contraindications = serializers.SerializerMethodField()
    
    class Meta:
        model = UserMedicalProfile
        fields = '__all__'
        read_only_fields = ['user', 'created_at', 'updated_at']
    
    def get_contraindications(self, obj):
        return obj.get_contraindications()

class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = '__all__'

class ChatSessionSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = '__all__'
    
    def get_message_count(self, obj):
        return obj.messages.count()

class MedicalImageAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalImageAnalysis
        fields = '__all__'
        read_only_fields = ['user', 'analysis_result', 'detected_conditions']
