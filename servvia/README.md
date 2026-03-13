# ServVia Neuro-Symbolic AI Healthcare

ServVia is a privacy-first, multi-agent clinical AI assistant. It supports symptom analysis, pharmacovigilance, chronobiology-aware dosing, lab report intelligence, and skin disease detection.

## Key Features

- **Multi-Agent Pipeline**: LangGraph-orchestrated Diagnostician → Proposer → Critic agents with revision loop and circuit breaker
- **Pharmacovigilance**: Neurosymbolic drug-herb interaction detection with allergen blocking
- **Chronobiology**: Circadian-phase and seasonal-aware remedy recommendations
- **Lab Report Co-Pilot**: Privacy-preserving OCR → PHI redaction → structured biomarker extraction with longitudinal delta tracking
- **Skin Analysis**: Gemini-powered skin disease detection

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

Copy `example.env` to `.env` and fill in your API keys:

```
OPEN_AI_KEY=...
GROQ_API_KEY=...
GOOGLE_API_KEY=...
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/get_answer_for_text_query/` | Clinical chat |
| POST | `/api/chat/stream/` | SSE streaming chat |
| POST | `/api/lab-report/identify/` | Co-Pilot step 1: identity fingerprint |
| POST | `/api/lab-report/confirm/` | Co-Pilot step 2: confirm + full analysis |
| POST | `/api/lab-report/analyze/` | Legacy lab report analysis |
| GET  | `/api/lab-report/history/` | Report history |
| GET  | `/api/lab-report/profiles/` | Patient profiles |
| POST | `/api/skin/analyze/` | Skin disease detection |
| POST | `/api/labs/analyze/` | Legacy lab ViewSet |
