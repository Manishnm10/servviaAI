from django.contrib import admin
from .models import SkinAnalysis


@admin.register(SkinAnalysis)
class SkinAnalysisAdmin(admin.ModelAdmin):
    list_display = ['email_id', 'diagnosis', 'confidence_score', 'created_at']
    list_filter = ['diagnosis', 'created_at']
    search_fields = ['email_id', 'diagnosis']

