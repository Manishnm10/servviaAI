#!/bin/bash
echo "🚀 Setting up Servvia..."

# Create backend structure
mkdir -p farmstack-backend/servvia/{models,serializers,views,management/commands}
mkdir -p farmstack-backend/kafka_{consumer,producer}

# Create models
cat > farmstack-backend/servvia/models.py << 'MODELS_EOF'
from django.db import models
from django.contrib.auth.models import User
import uuid

class UserMedicalProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    medical_conditions = models.JSONField(default=list)
    current_medications = models.JSONField(default=list)
    allergies = models.JSONField(default=list)
    age_group = models.CharField(max_length=20)
    is_profile_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def get_contraindications(self):
        return list(self.allergies)

class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_id = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE)
    role = models.CharField(max_length=20)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class MedicalImageAnalysis(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='medical_images/')
    analysis_result = models.JSONField(null=True)
    severity_level = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
MODELS_EOF

echo "✅ Setup complete!"
