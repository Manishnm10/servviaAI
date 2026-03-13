from django.db import models


class LabReport(models.Model):
    email_id = models.EmailField()
    report_file = models.FileField(upload_to='lab_reports/')
    extracted_text = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    analysis = models.JSONField(default=dict, blank=True)
    abnormal_values = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email_id} - Lab Report ({self.created_at.strftime('%Y-%m-%d')})"

