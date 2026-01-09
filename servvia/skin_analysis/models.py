from django.db import models


class SkinAnalysis(models.Model):
    email_id = models.EmailField()
    image = models.ImageField(upload_to='skin_images/')
    diagnosis = models.CharField(max_length=255, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)
    recommendations = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Skin Analyses"

    def __str__(self):
        return f"{self.email_id} - {self.diagnosis} ({self.created_at.strftime('%Y-%m-%d')})"

