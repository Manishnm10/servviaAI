# ServVia Objective 1: Temporal Neurosymbolic Reasoning for Pharmacovigilance

## Architecture Summary

### Current System Overview

ServVia is a neurosymbolic AI healthcare platform with the following architectural layers:

**1. Trust Engine Layer** (`/servvia2/trust_engine/`)
- `engine.py`: Core validation with embedded evidence database (GRADE standards), contraindications, and interaction tracking
- `confidence_calculator.py`: Scientific Confidence Score (SCS) calculator using EvidenceTier weights
- Evidence levels: HIGH, MODERATE, LOW_TO_MODERATE, LOW, VERY_LOW, INSUFFICIENT

**2. Knowledge Graph Layer** (`/servvia2/knowledge_graph/`)
- `schema.py`: Defines EvidenceTier enum (TIER_1_CLINICAL to TIER_5_THEORETICAL) with weights
- `models.py`: HerbRepository, DiseaseRepository, EvidenceRepository with in-memory storage
- Evidence linking herbs to conditions with PubMed citations

**3. Safety/Interaction Layer**
- `execute_rag.py`: Contains `InteractionDatabase` class with embedded herb-drug interactions
- Severity levels: CRITICAL, HIGH, MODERATE, MINOR, NONE
- Covers: ginger, turmeric, garlic, ashwagandha, licorice, ginseng, St. John's Wort, valerian, kava, ginkgo, echinacea, grapefruit

**4. User Context Layer**
- `user_profile/models.py`: UserProfile with allergies, medical_conditions, current_medications (all TextField, comma-separated)
- `conversation/manager.py`: ConversationManager tracking conditions, herbs, medications with addition/removal detection
- Context stored in Django cache + memory with 2-hour timeout

**5. Chronobiology Layer** (`/servvia2/chronobiology/`)
- `engine.py`: CircadianEngine with remedy timing (digestive, sleep_aid, anti_inflammatory, etc.)
- Seasonal context (Ayurvedic seasons: Shishira, Vasanta, Grishma, Varsha, Sharad, Hemanta)

**6. Agentic RAG Layer** (`/servvia2/agentic_rag/`)
- `controller.py`: ServViaAgenticRAG processes queries with user allergies, conditions, location
- Validates remedies against user context before generation

---

## Objective 1: Temporal Neurosymbolic Reasoning for Pharmacovigilance

### Goal
Implement a temporal reasoning layer that validates remedy recommendations against:
- User-specific medication histories (when medications were started/stopped)
- Allergy onset and severity patterns
- Symptom onset timing (acute vs chronic conditions)
- Drug-herb interaction timing (some interactions are time-dependent)

This validation occurs **BEFORE** LLM generation, acting as a safety gate.

---

## Step-by-Step Implementation Plan

### Phase 1: Data Model Extensions (Database Schema Changes)

**Step 1.1: Create Medication History Model**
- **New File**: `/user_profile/medication_history.py`
- Track medication start date, stop date, dosage, frequency, prescribing physician
- Fields: user (FK), medication_name, dosage, start_date, stop_date (nullable), status (active/discontinued/paused), reason_for_discontinuation

**Step 1.2: Create Allergy History Model**
- **New File**: `/user_profile/allergy_history.py`
- Track allergy onset date, severity, symptoms experienced, confirmed_by_testing
- Fields: user (FK), allergen, severity (mild/moderate/severe/life_threatening), onset_date, symptoms, testing_method

**Step 1.3: Create Symptom Onset Tracking Model**
- **New File**: `/user_profile/symptom_history.py`
- Track when symptoms first appeared, duration, severity over time
- Fields: user (FK), symptom_description, onset_date, severity_at_onset, current_severity, duration_days, is_chronic

**Step 1.4: Migration Files**
- Generate Django migrations for all new models
- Create migration: `0002_add_temporal_models.py`

### Phase 2: Temporal Knowledge Graph Extensions

**Step 2.1: Extend Knowledge Graph Schema**
- **Modify**: `/servvia2/knowledge_graph/schema.py`
- Add `TemporalContraindicationRule` dataclass with timing constraints
- Add `InteractionTiming` enum: IMMEDIATE, DELAYED_1HR, DELAYED_4HR, DELAYED_12HR, CUMULATIVE
- Add fields to DrugInteractionRule: onset_time, peak_interaction_window, duration_of_concern

**Step 2.2: Create Temporal Reasoning Engine**
- **New File**: `/servvia2/temporal_reasoning/engine.py`
- Core logic for temporal validation
- Methods:
  - `validate_with_medication_history(herb, medication_history)`
  - `check_temporal_contraindications(herb, user_profile, current_time)`
  - `assess_symptom_timing_eligibility(herb, symptom_onset_data)`
  - `calculate_safety_window(medication_start_date, herb_type)`

**Step 2.3: Create Timing Constants and Rules**
- **New File**: `/servvia2/temporal_reasoning/constants.py`
- Define temporal rules:
  - Minimum medication stabilization period (e.g., 2 weeks for new BP meds)
  - Herb washout periods (e.g., 7 days after stopping St. John's Wort)
  - Symptom acuity thresholds (acute <7 days, subacute 7-30 days, chronic >30 days)
  - Interaction time windows for each herb-drug pair

### Phase 3: Integration with Existing Pipeline

**Step 3.1: Modify Conversation Manager**
- **Modify**: `/servvia2/conversation/manager.py`
- Add temporal extraction from queries ("started taking aspirin 3 days ago")
- Add methods: `extract_temporal_entities()`, `update_medication_timeline()`
- Track medication changes with timestamps in context

**Step 3.2: Modify Trust Engine**
- **Modify**: `/servvia2/trust_engine/engine.py`
- Add `validate_temporal_safety()` method
- Integrate temporal reasoning before evidence lookup
- Add temporal warnings to ValidationResult dataclass

**Step 3.3: Modify Agentic RAG Controller**
- **Modify**: `/servvia2/agentic_rag/controller.py`
- In `process()` method, add temporal validation step before scoring
- Fetch user's medication/symptom history from database
- Pass temporal context to remedy scoring

**Step 3.4: Modify Execute RAG Pipeline**
- **Modify**: `/rag_service/execute_rag.py`
- After Step 2 (Entity Extraction), add Step 2.5: Temporal Context Retrieval
- Before Step 5 (Generation), add Step 4.5: Temporal Safety Validation

### Phase 4: API and Views Integration

**Step 4.1: Create Temporal API Endpoints**
- **New File**: `/user_profile/temporal_views.py`
- `POST /api/temporal/medication` - Log medication start/stop
- `GET /api/temporal/medication-history` - Retrieve medication timeline
- `POST /api/temporal/symptom` - Log symptom onset
- `GET /api/temporal/safety-check` - Real-time safety validation endpoint

**Step 4.2: Extend User Profile Views**
- **Modify**: `/user_profile/views.py`
- Add temporal data to profile responses
- Include medication timeline in user context API

### Phase 5: Testing and Validation

**Step 5.1: Create Test Suite**
- **New File**: `/tests/test_temporal_reasoning.py`
- Test cases:
  - User started warfarin 1 week ago → turmeric should be flagged HIGH risk
  - User stopped St. John's Wort 3 days ago → SSRI interaction still valid
  - Acute symptom (<3 days) → different remedy eligibility than chronic
  - Allergy onset tracking → cross-reactivity detection

**Step 5.2: Create Validation Scripts**
- **New File**: `/scripts/validate_temporal_rules.py`
- Script to verify temporal rules against clinical guidelines

---

## Exact File Paths Summary

### New Files to Create:
```
/user_profile/medication_history.py
/user_profile/allergy_history.py
/user_profile/symptom_history.py
/user_profile/temporal_views.py
/servvia2/temporal_reasoning/__init__.py
/servvia2/temporal_reasoning/engine.py
/servvia2/temporal_reasoning/constants.py
/tests/test_temporal_reasoning.py
/scripts/validate_temporal_rules.py
```

### Existing Files to Modify:
```
/servvia2/knowledge_graph/schema.py           # Add temporal dataclasses
/servvia2/conversation/manager.py             # Add temporal extraction
/servvia2/trust_engine/engine.py              # Add temporal validation
/servvia2/agentic_rag/controller.py             # Add temporal step
/rag_service/execute_rag.py                     # Add temporal pipeline steps
/user_profile/views.py                          # Add temporal endpoints
```

### Migration Files:
```
/user_profile/migrations/0002_add_temporal_models.py
```

---

## Database Schema Details

### MedicationHistory Model
```python
class MedicationHistory(models.Model):
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
```

### AllergyHistory Model
```python
class AllergyHistory(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='allergy_history')
    allergen = models.CharField(max_length=200, db_index=True)
    allergen_type = models.CharField(max_length=50, choices=[
        ('food', 'Food'),
        ('medication', 'Medication'),
        ('herb', 'Herb/Supplement'),
        ('environmental', 'Environmental'),
        ('latex', 'Latex'),
        ('other', 'Other'),
    ])
    severity = models.CharField(max_length=20, choices=[
        ('mild', 'Mild'),
        ('moderate', 'Moderate'),
        ('severe', 'Severe'),
        ('life_threatening', 'Life-Threatening'),
    ])
    onset_date = models.DateField(null=True, blank=True)
    first_reaction_date = models.DateField(null=True, blank=True)
    symptoms = models.TextField()  # JSON list of symptoms
    testing_method = models.CharField(max_length=100, blank=True)  # skin prick, blood test, etc.
    confirmed_by_testing = models.BooleanField(default=False)
    cross_reactive_allergens = models.TextField(blank=True)  # JSON list
    created_at = models.DateTimeField(auto_now_add=True)
```

### SymptomOnset Model
```python
class SymptomOnset(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='symptom_onsets')
    symptom_description = models.CharField(max_length=300)
    body_system = models.CharField(max_length=100)  # cardiovascular, respiratory, etc.
    onset_date = models.DateTimeField()
    severity_at_onset = models.IntegerField(choices=[(i, i) for i in range(1, 11)])  # 1-10 scale
    current_severity = models.IntegerField(choices=[(i, i) for i in range(1, 11)], null=True)
    duration_days = models.IntegerField(null=True)
    is_chronic = models.BooleanField(default=False)
    pattern = models.CharField(max_length=50, choices=[
        ('constant', 'Constant'),
        ('intermittent', 'Intermittent'),
        ('worsening', 'Worsening'),
        ('improving', 'Improving'),
        ('fluctuating', 'Fluctuating'),
    ])
    associated_conditions = models.TextField(blank=True)  # JSON list
    medications_tried = models.TextField(blank=True)  # JSON list
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

---

## Implementation Notes

### Critical Safety Rules (To Be Implemented)

1. **Medication Stabilization Window**: New medications (<14 days) have higher interaction risk
2. **Herb Washout Periods**: Some herbs require 7-14 days washout before starting contraindicated meds
3. **Acute Symptom Window**: Symptoms <72 hours old may require different remedy approach than chronic
4. **Cumulative Interaction Risk**: Long-term herb use + new medication = different risk profile than short-term use
5. **Time-of-Day Sensitivity**: Some interactions are timing-dependent (e.g., morning vs evening dosing)

### Integration Points

- Temporal validation must run **before** LLM generation in the pipeline
- Results should be cached per user session to reduce database load
- Warnings should be displayed prominently in the response formatter
- Conversation manager must extract and track temporal mentions automatically

---

## Success Criteria

1. System correctly flags turmeric for user who started warfarin <14 days ago
2. System correctly warns about St. John's Wort interaction 7 days after discontinuation
3. System differentiates remedy recommendations based on acute (<7 days) vs chronic (>30 days) symptoms
4. System tracks and warns about cross-reactive allergies with temporal context
5. All temporal data persists across sessions with proper Django caching
6. Zero hallucinated temporal data - all dates must come from user input or verified sources

---

**Document Status**: Architecture Review Complete  
**Next Step**: Await approval to begin Phase 1 implementation
