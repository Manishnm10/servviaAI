from django. db import models
from django.conf import settings
from django.utils import timezone
import uuid

class UserMedicalProfile(models.Model):
    AGE_GROUPS = [
        ('child', 'Child (0-12)'),
        ('teen', 'Teen (13-17)'),
        ('adult', 'Adult (18-64)'),
        ('senior', 'Senior (65+)')
    ]

    user = models.OneToOneField(settings. AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='medical_profile')
    medical_conditions = models.JSONField(default=list, blank=True)
    current_medications = models.JSONField(default=list, blank=True)
    allergies = models.JSONField(default=list, blank=True)
    age_group = models. CharField(max_length=20, choices=AGE_GROUPS, blank=True)
    dietary_restrictions = models. JSONField(default=list, blank=True)
    pregnancy_status = models. BooleanField(default=False)
    is_profile_complete = models.BooleanField(default=False)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_medical_profiles'

    def get_contraindications(self):
        contraindications = list(self.allergies)
        conditions_lower = [c.lower() for c in self.medical_conditions]

        if 'diabetes' in conditions_lower:
            contraindications.extend(['honey', 'sugar', 'sweet fruits'])
        if 'hypertension' in conditions_lower:
            contraindications.extend(['salt', 'sodium', 'licorice'])

        return list(set(contraindications))

class ChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_sessions')
    session_id = models. UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=255, blank=True)
    created_at = models. DateTimeField(auto_now_add=True)
    updated_at = models. DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chat_sessions'
        ordering = ['-updated_at']

class ChatMessage(models. Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System')
    ]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models. TextField()
    image_url = models. URLField(blank=True, null=True)
    tokens_used = models. IntegerField(default=0)
    model_used = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chat_messages'
        ordering = ['created_at']

class MedicalImageAnalysis(models.Model):
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High - Seek Medical Help')
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='medical_images')
    image = models.ImageField(upload_to='medical_images/%Y/%m/%d/')
    analysis_result = models.JSONField(blank=True, null=True)
    detected_conditions = models.JSONField(default=list, blank=True)
    suggested_remedies = models.JSONField(default=list, blank=True)
    requires_medical_attention = models.BooleanField(default=False)
    severity_level = models.CharField(max_length=20, choices=SEVERITY_LEVELS, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'medical_image_analyses'
        ordering = ['-created_at']

class LabReportAnalysis(models.Model):
    """Lab Report Analysis Model"""
    REPORT_TYPES = [
        ('cbc', 'Complete Blood Count'),
        ('metabolic', 'Metabolic Panel'),
        ('lipid', 'Lipid Panel'),
        ('thyroid', 'Thyroid Function'),
        ('liver', 'Liver Function'),
        ('kidney', 'Kidney Function'),
        ('general', 'General Lab Report')
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lab_reports')
    report_file = models.FileField(upload_to='lab_reports/%Y/%m/%d/')
    report_type = models. CharField(max_length=20, choices=REPORT_TYPES, blank=True)
    extracted_text = models.TextField(blank=True)
    analysis_result = models.JSONField(blank=True, null=True)
    summary = models.TextField(blank=True)
    abnormal_findings = models.JSONField(default=list, blank=True)
    personalized_recommendations = models.JSONField(default=list, blank=True)
    requires_doctor_consultation = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'lab_report_analyses'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Lab Report - {self.user.email} - {self.report_type}"


class MedicalKnowledgeBase(models.Model):
    SOURCE_TYPES = [
        ('who', 'WHO Guidelines'),
        ('pubmed', 'PubMed Research'),
        ('fda', 'FDA Information'),
        ('cdc', 'CDC Updates'),
        ('manual', 'Manual Entry')
    ]

    title = models.CharField(max_length=500)
    content = models.TextField()
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    source_url = models.URLField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    qdrant_id = models.CharField(max_length=100, blank=True)
    ingested_via_kafka = models. BooleanField(default=False)
    kafka_topic = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'medical_knowledge_base'
        ordering = ['-created_at']