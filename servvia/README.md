# ServVia — Neuro-Symbolic AI Healthcare Platform

ServVia is a privacy-first, multi-agent clinical AI assistant. It combines edge computing, cloud AI, and neuro-symbolic reasoning for symptom analysis, pharmacovigilance, chronobiology-aware dosing, lab report intelligence, and skin disease detection.

## Architecture

```
User ──► Django (port 9000)
           ├── Multi-Agent Pipeline (Diagnostician → Proposer → Critic)
           ├── Skin Analysis Module (Edge AI / Cloud AI — user-selected)
           ├── Lab Report Co-Pilot (OCR → PHI Redaction → Biomarker Extraction)
           ├── Neuro-Symbolic Safety Layer (Drug-Herb Interactions)
           └── Chronobiology Engine (Circadian & Seasonal Dosing)
```

## Key Features

### Clinical Chat — Multi-Agent Pipeline
- LangGraph-orchestrated agent chain with Diagnostician → Proposer → Critic revision loop and circuit breaker
- Conversation memory with context windowing
- SSE streaming responses with real-time token delivery

### Skin Disease Detection
- **21 supported conditions** with differential diagnosis logic
- **Edge AI mode** — fully private, on-device analysis via local vision model. No image data leaves the machine.
- **Cloud AI mode** — higher accuracy cloud vision analysis with automatic rate-limit failover to a secondary cloud provider
- User selects Edge or Cloud before upload — **strict separation, no silent fallback between modes**
- Trust Engine validates treatment recommendations against user allergies and medications
- Real-time SSE streaming with stage-by-stage progress

### Lab Report Co-Pilot
- Privacy-preserving pipeline: local OCR → PHI redaction (masks names, phones, emails — preserves dates and locations for clinical context) → structured biomarker extraction
- Fuzzy patient profile matching for multi-patient routing
- Longitudinal delta tracking across reports
- System-grouped, tiered triage with priority flagging

### Pharmacovigilance — Neuro-Symbolic Safety
- Drug-herb interaction detection with evidence-tier scoring
- Allergen blocking based on user health profile
- Contraindication severity classification (critical, major, moderate)

### Chronobiology Engine
- Circadian-phase aware remedy timing recommendations
- Seasonal adjustment for dosing guidance
- Deterministic, zero-LLM computation

## Server Setup

```bash
cd servvia
python -m venv venv
source venv/Scripts/activate     # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:9000
```

## Environment

Copy `example.env` to `.env` and configure:

```
# Cloud AI providers
GEMINI_API_KEY=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_API_VERSION=...

# Model selection
MODEL_MASTER=...
MODEL_CHAT=...

# Google Cloud (TTS, translation)
GOOGLE_APPLICATION_CREDENTIALS=...
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/get_answer_for_text_query/` | Clinical chat |
| POST | `/api/chat/stream/` | SSE streaming chat |
| POST | `/api/skin/analyze/` | Skin disease detection |
| POST | `/api/skin/analyze/stream/` | Skin analysis with SSE streaming |
| POST | `/api/lab-report/identify/` | Lab Co-Pilot step 1: identity fingerprint |
| POST | `/api/lab-report/confirm/` | Lab Co-Pilot step 2: confirm + full analysis |
| GET  | `/api/lab-report/history/` | Report history |
| GET  | `/api/lab-report/profiles/` | Patient profiles |

### Skin Analysis Request

```
POST /api/skin/analyze/stream/
Content-Type: multipart/form-data

Fields:
  email_id      — user email
  image         — skin image file
  analysis_mode — "edge" or "cloud"
```

## Project Structure

```
servvia/
├── agents/            # LangGraph multi-agent pipeline
├── api/               # Core API views & middleware
├── chronobiology/     # Circadian & seasonal engine
├── core_temporal/     # Trust Engine, conversation manager
├── edge/              # Edge AI — local skin classifier, OCR, PHI redactor
├── lab_report/        # Lab Co-Pilot pipeline
├── neurosymbolic/     # Temporal safety validator
├── skin_analysis/     # Cloud skin disease detection & streaming views
├── templates/         # Frontend (Django-served SPA)
└── django_core/       # Settings, config, URL routing
```
