from django.contrib import admin
from .models import LabReport


@admin.register(LabReport)
class LabReportAdmin(admin.ModelAdmin):
    list_display = ['email_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['email_id']

