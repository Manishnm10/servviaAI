from django.db import models
from django.utils import timezone

class UserProfile(models.Model):
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    
    allergies = models.TextField(blank=True, null=True)
    medical_conditions = models.TextField(blank=True, null=True)
    current_medications = models.TextField(blank=True, null=True)
    
    is_profile_complete = models.BooleanField(default=False)
    profile_completed_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'user_profiles'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.email} - {self.first_name or 'Unknown'}"
    
    def get_allergies_list(self):
        if self.allergies:
            return [a.strip() for a in self.allergies.split(',') if a.strip()]
        return []
    
    def get_conditions_list(self):
        if self.medical_conditions:
            return [c.strip() for c in self.medical_conditions.split(',') if c.strip()]
        return []
    
    def get_medications_list(self):
        if self.current_medications:
            return [m.strip() for m in self.current_medications.split(',') if m.strip()]
        return []
    
    def mark_profile_complete(self):
        self.is_profile_complete = True
        self.profile_completed_at = timezone.now()
        self.save()


class MedicationHistory(models.Model):
    """
    Temporal tracking of user medication history for pharmacovigilance.
    Captures start/stop dates, dosage, and status for interaction analysis.
    """
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='medication_history')
    medication_name = models.CharField(max_length=200, db_index=True)
    generic_name = models.CharField(max_length=200, blank=True)
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)  # e.g., "twice daily"
    route = models.CharField(max_length=50, default='oral')  # oral, topical, injection, etc.
    start_date = models.DateTimeField()
    stop_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('active', 'Active'),
        ('discontinued', 'Discontinued'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
    ], default='active')
    prescribed_by = models.CharField(max_length=200, blank=True)
    reason_for_taking = models.TextField(blank=True)  # condition being treated
    reason_for_discontinuation = models.TextField(blank=True)
    side_effects_experienced = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'medication_history'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.user.email} - {self.medication_name} ({self.status})"

    def is_recently_started(self, days=14):
        """Check if medication was started within the specified window."""
        if not self.start_date:
            return False
        from datetime import timedelta
        return (timezone.now() - self.start_date).days <= days

    def days_since_stopped(self):
        """Return days since medication was stopped, or None if still active."""
        if not self.stop_date:
            return None
        return (timezone.now() - self.stop_date).days


class AllergyHistory(models.Model):
    """
    Temporal tracking of user allergies with onset dates and severity.
    Enables cross-reactivity detection and temporal safety analysis.
    """
    ALLERGEN_TYPE_CHOICES = [
        ('food', 'Food'),
        ('medication', 'Medication'),
        ('herb', 'Herb/Supplement'),
        ('environmental', 'Environmental'),
        ('latex', 'Latex'),
        ('other', 'Other'),
    ]

    SEVERITY_CHOICES = [
        ('mild', 'Mild'),
        ('moderate', 'Moderate'),
        ('severe', 'Severe'),
        ('life_threatening', 'Life-Threatening'),
    ]

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='allergy_history')
    allergen = models.CharField(max_length=200, db_index=True)
    allergen_type = models.CharField(max_length=50, choices=ALLERGEN_TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    onset_date = models.DateField(null=True, blank=True)
    first_reaction_date = models.DateField(null=True, blank=True)
    symptoms = models.TextField()  # JSON list of symptoms
    testing_method = models.CharField(max_length=100, blank=True)  # skin prick, blood test, etc.
    confirmed_by_testing = models.BooleanField(default=False)
    cross_reactive_allergens = models.TextField(blank=True)  # JSON list
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'allergy_history'
        ordering = ['-onset_date', '-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.allergen} ({self.severity})"

    def requires_epipen(self):
        """Check if allergy is severe enough to warrant emergency medication."""
        return self.severity in ('severe', 'life_threatening')

    def is_newly_developed(self, days=30):
        """Check if allergy developed recently (within specified days)."""
        if not self.onset_date:
            return False
        from datetime import timedelta
        return (timezone.now().date() - self.onset_date).days <= days


class SymptomOnset(models.Model):
    """
    Temporal tracking of symptom onset for acute vs chronic classification.
    Critical for determining remedy eligibility and safety windows.
    """
    PATTERN_CHOICES = [
        ('constant', 'Constant'),
        ('intermittent', 'Intermittent'),
        ('worsening', 'Worsening'),
        ('improving', 'Improving'),
        ('fluctuating', 'Fluctuating'),
    ]

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='symptom_onsets')
    symptom_description = models.CharField(max_length=300)
    body_system = models.CharField(max_length=100)  # cardiovascular, respiratory, etc.
    onset_date = models.DateTimeField()
    severity_at_onset = models.IntegerField(choices=[(i, i) for i in range(1, 11)])  # 1-10 scale
    current_severity = models.IntegerField(choices=[(i, i) for i in range(1, 11)], null=True, blank=True)
    duration_days = models.IntegerField(null=True, blank=True)
    is_chronic = models.BooleanField(default=False)
    pattern = models.CharField(max_length=50, choices=PATTERN_CHOICES)
    associated_conditions = models.TextField(blank=True)  # JSON list
    medications_tried = models.TextField(blank=True)  # JSON list
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'symptom_onsets'
        ordering = ['-onset_date']

    def __str__(self):
        return f"{self.user.email} - {self.symptom_description} ({self.acuity_classification()})"

    def acuity_classification(self):
        """
        Classify symptom acuity based on duration:
        - Acute: < 7 days
        - Subacute: 7-30 days
        - Chronic: > 30 days
        """
        if not self.duration_days:
            days = (timezone.now() - self.onset_date).days
        else:
            days = self.duration_days

        if days < 7:
            return 'acute'
        elif days <= 30:
            return 'subacute'
        else:
            return 'chronic'

    def days_since_onset(self):
        """Calculate days since symptom first appeared."""
        return (timezone.now() - self.onset_date).days
