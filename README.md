# ServVia — Neuro-Symbolic AI Healthcare Platform

ServVia is a privacy-first, AI-powered healthcare intelligence platform that combines multi-agent reasoning, knowledge graphs, chronobiology, and pharmacovigilance to deliver safe, evidence-based clinical guidance. The platform supports clinical chat, lab report analysis, and skin disease detection — all with a strong emphasis on patient privacy and safety.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Variables](#environment-variables)
  - [Running Server 1 — AI Healthcare (Port 9000)](#running-server-1--ai-healthcare-port-9000)
  - [Running Server 2 — Data Platform (Port 9001)](#running-server-2--data-platform-port-9001)
  - [Running the Frontend (Port 3000)](#running-the-frontend-port-3000)
- [Core Features](#core-features)
  - [Multi-Agent Clinical Reasoning (ServVia 4.0)](#multi-agent-clinical-reasoning-servvia-40)
  - [Lab Report Co-Pilot](#lab-report-co-pilot)
  - [Skin Disease Detection](#skin-disease-detection)
  - [Pharmacovigilance & Drug-Herb Safety](#pharmacovigilance--drug-herb-safety)
  - [Chronobiology Engine](#chronobiology-engine)
  - [Graph RAG Knowledge Retrieval](#graph-rag-knowledge-retrieval)
  - [Privacy — PHI Redaction Pipeline](#privacy--phi-redaction-pipeline)
  - [Emergency Safety Layer](#emergency-safety-layer)
- [API Reference](#api-reference)
  - [Clinical Chat](#clinical-chat)
  - [Lab Report Co-Pilot API](#lab-report-co-pilot-api)
  - [Skin Analysis](#skin-analysis)
  - [User Profile](#user-profile)
- [Project Structure](#project-structure)
- [Data Models](#data-models)
- [Configuration](#configuration)

---

## Architecture Overview

ServVia is split into two Django servers sharing a monorepo:

```
servviaAI/
├── servvia/              # Server 1 — AI Healthcare Core  (Port 9000)
├── servvia-backend/      # Server 2 — Data Platform        (Port 9001)
└── servvia-frontend/     # Next.js Frontend                (Port 3000)
```

### Server 1 — AI Healthcare Core

Handles all AI inference, clinical reasoning, and patient-facing APIs. It is built around a **neuro-symbolic pipeline** that layers symbolic rules (pharmacology, chronobiology) on top of LLM reasoning.

```
Request
  └─► Emergency Detection (hardcoded, no LLM)
        └─► Multi-Agent Graph (LangGraph)
              ├─► Diagnostician   (intent classification + RAG retrieval)
              ├─► Proposer        (remedy/treatment generation)
              ├─► Critic          (evidence validation + drug-herb safety check)
              └─► Fallback        (Groq llama-3.3-70b if primary fails)
                    └─► Chronobiology overlay (timing/season context)
                          └─► Neurosymbolic Validator (temporal drug interactions)
                                └─► Trust Engine (confidence grading)
                                      └─► Response
```

### Server 2 — Data Platform

Manages datasets, participant onboarding, data connectors (MySQL, Google Drive, YouTube), and vector database ingestion (Qdrant). Powers the RAG knowledge base that Server 1 queries.

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Backend framework** | Django 4.2.4 (Server 1), Django 4.1.5 (Server 2) |
| **REST API** | Django REST Framework 3.14.0 |
| **Primary LLM** | OpenAI gpt-4o-mini |
| **Fallback LLM** | Groq llama-3.3-70b-versatile |
| **Vision LLM** | Google Gemini API |
| **Edge AI** | Moondream via Ollama (local inference) |
| **Agent framework** | LangGraph 1.0.10 + LangChain Core 1.2.16 |
| **Knowledge graph** | Neo4j 5.14.0 |
| **Vector database** | Qdrant 1.8.0 |
| **Document OCR** | pdfplumber 0.11.0, easyocr 1.7.1 |
| **Privacy / PHI** | Microsoft Presidio + spaCy en_core_web_lg |
| **Data validation** | Pydantic 2.9.2 |
| **Task queue** | Celery 5.3.1 + Redis |
| **Frontend** | Next.js 16.1.6, React 19.2.3, Tailwind CSS 4, TypeScript 5 |
| **Numeric** | NumPy 1.26.4 (pinned <2 for PyTorch compatibility) |

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- Redis (for Celery task queue)
- Neo4j (for Graph RAG — optional, degrades gracefully)
- Qdrant (for vector search — optional, degrades gracefully)
- Ollama (for edge skin classifier — optional, degrades to Gemini)

### Environment Variables

Create a `.env` file in `servvia/`:

```env
# LLM Keys
OPEN_AI_KEY=sk-...
GROQ_API_KEY=gsk_...
GOOGLE_API_KEY=...

# Django
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG_MODE=true
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Databases (optional — required for Graph RAG and vector search)
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=...
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

### Running Server 1 — AI Healthcare (Port 9000)

```bash
cd servvia
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:9000
```

The Django-served frontend is available at `http://localhost:9000/`.

### Running Server 2 — Data Platform (Port 9001)

> **Note:** The root `venv/` at `servviaAI/` is nearly empty and should not be used for Server 2. Use system Python 3.10 directly.

```bash
# If the root venv is active, deactivate it first
deactivate

cd servvia-backend
python manage.py runserver 0.0.0.0:9001
```

Swagger API docs are available at `http://localhost:9001/doc/`.

### Running the Frontend (Port 3000)

```bash
cd servvia-frontend
npm install
npm run dev
```

---

## Core Features

### Multi-Agent Clinical Reasoning (ServVia 4.0)

**File:** `servvia/agents/graph.py`

A LangGraph `StateGraph` orchestrates four specialized agents in sequence:

| Agent | Role |
|---|---|
| **Diagnostician** | Classifies intent, retrieves relevant evidence via RAG |
| **Proposer** | Generates remedy/treatment proposals with dosage and timing |
| **Critic** | Validates proposals against evidence, flags drug-herb interactions |
| **Fallback** | Activates if primary pipeline fails — uses Groq llama-3.3-70b |

The pipeline supports up to **2 revision loops** before falling back. All agent outputs are typed with Pydantic models for safe data flow between nodes.

### Lab Report Co-Pilot

**Files:** `servvia/lab_report/views.py`, `servvia/agents/lab_summarizer.py`, `servvia/edge/`

A two-step, privacy-first lab report analysis system:

**Step 1 — Identify** (`POST /api/lab-report/identify/`)
1. Extract text from PDF or scanned image (pdfplumber / easyocr)
2. Run `IdentityExtractor` to capture patient name, age, sex, IDs — **before** redaction
3. Run `PHIRedactor` to mask names, emails, phone numbers
4. Fuzzy-match against existing `PatientProfile` records

**Step 2 — Confirm & Analyze** (`POST /api/lab-report/confirm/`)
1. User confirms patient identity
2. `LabSummarizer` agent analyzes anonymized report text
3. Returns structured JSON: biomarker groups, abnormal flags, triage priority, recommendations
4. Stores `BiomarkerSnapshot` for longitudinal delta tracking

Supports multiple patient profiles per account (e.g., "Dad's Health", "Self") and tracks trends across reports over time.

### Skin Disease Detection

**Files:** `servvia/skin_analysis/views.py`, `servvia/edge/skin_classifier.py`

Dual-path architecture for skin analysis:

| Path | Model | When |
|---|---|---|
| **Edge AI** | Qwen3.5-2B via Ollama | Primary — local, low latency, privacy-preserving |
| **Cloud AI** | Google Gemini API | Fallback if Ollama unavailable |

Both paths return: diagnosis, confidence score, and actionable recommendations. Results are stored in `SkinAnalysis` with full history per user.

### Pharmacovigilance & Drug-Herb Safety

**File:** `servvia/neurosymbolic/temporal_validator.py`

Validates every remedy proposal against the patient's medication profile:

- **12+ monitored herbs:** ginger, turmeric, garlic, ashwagandha, licorice, ginseng, St. John's Wort, valerian, kava, ginkgo, echinacea, grapefruit
- **4 severity levels:**
  - `CRITICAL` — hard block, remedy rejected
  - `HIGH` — warning with override option
  - `MODERATE` — caution note added
  - `LOW` — informational
- **Timing constraints:** IMMEDIATE, DELAYED_1HR, DELAYED_4HR, DELAYED_12HR, CUMULATIVE
- **Symptom acuity detection:** Acute (<7 days), subacute (7–30 days), chronic (>30 days) — influences dosing strategy

### Chronobiology Engine

**File:** `servvia/chronobiology/inference.py`

Optimizes remedy timing using biological and seasonal context:

- **Circadian phases:** morning, afternoon, evening, night
- **Ayurvedic seasons:** Shishira (winter), Vasanta (spring), Grishma (summer), Varsha (monsoon), Sharad (autumn), Hemanta (late autumn)
- **Remedy category timing:** digestives (post-meal), sleep aids (evening), anti-inflammatories (morning/evening)

### Graph RAG Knowledge Retrieval

**Files:** `servvia/graph_rag/client.py`, `servvia/graph_rag/schema.py`, `servvia/graph_rag/updater.py`

Extends standard RAG with a Neo4j knowledge graph to improve evidence retrieval:

- Herb-disease outcome relationships stored as graph edges
- Adaptive ranking based on query context and past outcomes
- `GraphRAGClient` handles query → subgraph traversal → evidence assembly
- `GraphUpdater` enriches the graph as new reports and outcomes are processed

### Privacy — PHI Redaction Pipeline

**Files:** `servvia/edge/phi_redactor.py`, `servvia/edge/identity_extractor.py`

All patient-uploaded documents pass through local PHI redaction before any LLM sees them:

| Entity | Action | Reason |
|---|---|---|
| PERSON | Masked → `[PERSON_1]` | PII |
| EMAIL_ADDRESS | Masked → `[EMAIL_1]` | PII |
| PHONE_NUMBER | Masked → `[PHONE_1]` | PII (lab values filtered to avoid false positives) |
| DATE_TIME | **Kept** | Clinical relevance |
| LOCATION | **Kept** | Clinical relevance |

The `IdentityExtractor` runs **before** redaction to capture patient demographics for profile matching, using regex-first patterns with LLM fallback.

### Emergency Safety Layer

A hardcoded (no LLM) safety net runs before every clinical query. If life-threatening symptoms are detected (cardiac, neurological, anaphylaxis keywords), the pipeline immediately returns a hardcoded emergency response directing the user to seek immediate care — bypassing all AI inference.

---

## API Reference

All endpoints are on Server 1 (`http://localhost:9000`).

### Clinical Chat

#### `POST /api/chat/get_answer_for_text_query/`
Submit a clinical question and receive a structured AI response.

**Request:**
```json
{
  "email": "user@example.com",
  "query": "I have persistent fatigue and joint pain for the past 3 weeks",
  "user_profile_context": {
    "allergies": ["penicillin"],
    "current_medications": ["metformin 500mg"],
    "medical_conditions": ["type 2 diabetes"]
  }
}
```

**Response:**
```json
{
  "response": "...",
  "remedies": [],
  "evidence_grade": "MODERATE",
  "safety_flags": [],
  "chronobiology_context": { "phase": "morning", "season": "Vasanta" }
}
```

#### `POST /api/chat/stream/`
Same as above but returns a **Server-Sent Events (SSE)** stream for real-time output.

---

### Lab Report Co-Pilot API

#### `POST /api/lab-report/identify/`
Upload a lab report and extract patient identity for profile matching.

**Request:** `multipart/form-data`
- `email` — user email
- `report_file` — PDF or image file(s)

**Response:**
```json
{
  "identity_meta": {
    "name": "John Doe",
    "age": 45,
    "sex": "M",
    "patient_id": "SRF-12345",
    "report_date": "2026-03-15"
  },
  "profile_match": {
    "profile_id": 3,
    "label": "Dad's Health",
    "confidence": 0.92
  }
}
```

#### `POST /api/lab-report/confirm/`
Confirm patient identity and retrieve full analysis.

**Request:**
```json
{
  "email": "user@example.com",
  "patient_profile_id": 3,
  "confirmed": true
}
```

**Response:**
```json
{
  "biomarkers": {
    "CBC": [
      { "name": "Hemoglobin", "value": "10.2", "unit": "g/dL", "status": "LOW", "reference": "13.5–17.5" }
    ]
  },
  "triage_priority": "MODERATE",
  "abnormal_count": 3,
  "recommendations": ["..."],
  "delta": {
    "Hemoglobin": { "previous": 11.4, "current": 10.2, "trend": "WORSENING" }
  }
}
```

#### `GET /api/lab-report/history/?email=<email>`
Returns paginated history of all lab reports for a user.

#### `GET /api/lab-report/profiles/?email=<email>`
Returns all patient profiles linked to an account.

#### `POST /api/lab-report/profiles/`
Create a new patient profile (e.g., "Dad's Health").

---

### Skin Analysis

#### `POST /api/skin/analyze/`
Upload a skin image for AI-powered diagnosis.

**Request:** `multipart/form-data`
- `email` — user email
- `image` — image file (JPEG, PNG)

**Response:**
```json
{
  "diagnosis": "Atopic Dermatitis",
  "confidence_score": 0.87,
  "recommendations": ["Avoid known irritants", "Apply fragrance-free moisturizer twice daily"],
  "edge_used": true
}
```

#### `POST /api/skin/analyze/stream/`
Streaming version with real-time progress updates via SSE.

#### `GET /api/skin/history/?email=<email>`
Returns all past skin analysis records for a user.

---

### User Profile

#### `GET / POST /api/profile/profile/`
Manage the user's medical profile (allergies, conditions, medications).

```json
{
  "email": "user@example.com",
  "allergies": ["penicillin", "shellfish"],
  "medical_conditions": ["hypertension", "type 2 diabetes"],
  "current_medications": ["metformin 500mg", "lisinopril 10mg"]
}
```

### Health Check

#### `GET /api/ping/`
Returns `{"status": "ok"}`.

---

## Project Structure

```
servvia/
├── agents/
│   ├── graph.py              # LangGraph multi-agent pipeline (Diagnostician → Proposer → Critic)
│   ├── lab_summarizer.py     # Lab Co-Pilot: biomarker extraction, triage, delta tracking
│   └── prompts.py            # System and user prompt templates
├── api/
│   ├── views.py              # Main chat endpoint + routing logic
│   ├── lab_views.py          # Legacy lab analysis endpoint
│   └── urls.py
├── core/
│   └── models.py             # Pydantic models (MedicationRecord, RemedyProposal, etc.)
├── core_temporal/
│   ├── trust_engine/         # Evidence grading (HIGH, MODERATE, LOW)
│   ├── knowledge_graph/      # Herb-disease evidence linking
│   ├── agentic_rag/          # Intent-driven retrieval
│   ├── conversation/         # 2-hour context cache
│   └── intent/               # Query classification
├── chronobiology/
│   └── inference.py          # Circadian + Ayurvedic seasonal timing engine
├── django_core/
│   ├── settings.py           # Django configuration
│   └── config.py             # App-level configuration
├── edge/
│   ├── ocr_processor.py      # pdfplumber + easyocr document extraction
│   ├── phi_redactor.py       # Presidio PHI masking (local, no cloud)
│   ├── identity_extractor.py # Regex + LLM patient demographics extraction
│   └── skin_classifier.py    # Ollama edge inference for skin images
├── graph_rag/
│   ├── client.py             # Neo4j Graph RAG query client
│   ├── schema.py             # Graph node/edge schema definitions
│   └── updater.py            # Outcome-adaptive graph enrichment
├── lab_report/
│   ├── views.py              # Co-Pilot endpoints (identify, confirm, profiles)
│   ├── models.py             # PatientProfile, LabReport, BiomarkerSnapshot
│   └── profile_matcher.py    # Fuzzy identity matching across profiles
├── legacy_healthcare/
│   ├── rag_service/          # OpenAI embeddings + Qdrant retrieval chain
│   └── language_service/     # TTS and translation services
├── neurosymbolic/
│   └── temporal_validator.py # Drug-herb interaction validator with timing constraints
├── skin_analysis/
│   ├── views.py              # Skin analysis endpoints
│   ├── models.py             # SkinAnalysis model
│   └── disease_detector.py   # Gemini-based disease detection
└── user_profile/
    ├── views.py              # Profile management endpoints
    └── models.py             # UserProfile model
```

---

## Data Models

### Core Pydantic Models (`core/models.py`)

| Model | Key Fields |
|---|---|
| `MedicationRecord` | drug_name, start_date, end_date, is_active (computed) |
| `RemedyProposal` | remedy, dosage, frequency, duration, contraindications |
| `UserMedicalProfile` | allergies, medications, conditions, location |
| `ValidationResult` | verdict (safe / unsafe / caution), evidence, confidence |

### Django ORM Models

| Model | App | Key Fields |
|---|---|---|
| `UserProfile` | user_profile | email, allergies, medical_conditions, current_medications |
| `PatientProfile` | lab_report | user_profile FK, label, name, age, sex, SRF_ID, UHID, MRN |
| `LabReport` | lab_report | email, patient_profile FK, file, extracted_text, summary, analysis JSON |
| `BiomarkerSnapshot` | lab_report | lab_report FK, biomarker_name, value, unit, status, timestamp |
| `SkinAnalysis` | skin_analysis | email, image, diagnosis, confidence_score, recommendations |

---

## Configuration

### Key Django Settings

| Setting | Environment Variable | Default |
|---|---|---|
| `SECRET_KEY` | `DJANGO_SECRET_KEY` | Auto-generated (warning printed) |
| `DEBUG` | `DJANGO_DEBUG_MODE` | `false` |
| `ALLOWED_HOSTS` | `ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0` |
| `CORS_ALLOW_ALL_ORIGINS` | — | `true` in debug mode |

### LLM Model Selection

| Task | Primary | Fallback |
|---|---|---|
| Clinical reasoning | gpt-4o-mini (OpenAI) | llama-3.3-70b (Groq) |
| Skin analysis | Qwen3.5-2B (Ollama, local) | Gemini API (Google) |
| Embeddings / RAG | OpenAI text-embedding-ada-002 | — |

All API keys are loaded from environment variables. The system logs warnings and degrades gracefully if keys are missing rather than failing at startup.

### NumPy Version Pin

NumPy is pinned to `==1.26.4` because PyTorch (used by easyocr) is compiled against NumPy 1.x. Do not upgrade NumPy without a corresponding PyTorch upgrade.
