from django.db import models
from user_profile.models import UserProfile


class PatientProfile(models.Model):
    """
    Sub-profile architecture: one UserProfile can manage multiple patients.
    E.g., "My Health", "Dad's Health", "Mom's Health".
    """
    user_profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='patient_profiles',
    )
    label = models.CharField(max_length=100, default='My Health')
    patient_name = models.CharField(max_length=200, blank=True)
    age = models.IntegerField(null=True, blank=True)
    sex = models.CharField(
        max_length=10,
        choices=[('M', 'Male'), ('F', 'Female'), ('Other', 'Other')],
        blank=True,
    )
    external_ids = models.JSONField(
        default=dict, blank=True,
        help_text='Stores SRF_ID, UHID, MRN, etc. as key-value pairs',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'patient_profiles'
        ordering = ['-updated_at']
        unique_together = [('user_profile', 'label')]

    def __str__(self):
        name = self.patient_name or self.label
        return f"{self.user_profile.email} — {name}"


class LabReport(models.Model):
    """Stores lab report files and analysis results."""
    email_id = models.EmailField()
    patient_profile = models.ForeignKey(
        PatientProfile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='lab_reports',
    )
    report_file = models.FileField(upload_to='lab_reports/')
    extracted_text = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    analysis = models.JSONField(default=dict, blank=True)
    abnormal_values = models.JSONField(default=list, blank=True)
    identity_meta = models.JSONField(
        default=dict, blank=True,
        help_text='Extracted patient demographics: name, age, sex, IDs',
    )
    profile_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email_id} - Lab Report ({self.created_at.strftime('%Y-%m-%d')})"


class BiomarkerSnapshot(models.Model):
    """
    Longitudinal memory: stores the structured biomarker extraction from each
    report, linked to a PatientProfile for delta/trend tracking.
    """
    patient_profile = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='biomarker_snapshots',
    )
    lab_report = models.OneToOneField(
        LabReport,
        on_delete=models.CASCADE,
        related_name='biomarker_snapshot',
    )
    report_date = models.DateField(null=True, blank=True)
    biomarkers_json = models.JSONField(
        default=list,
        help_text='Full structured biomarker array from LLM extraction',
    )
    abnormal_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'biomarker_snapshots'
        ordering = ['-report_date', '-created_at']

    def __str__(self):
        return f"{self.patient_profile} — Snapshot ({self.report_date or 'unknown date'})"
