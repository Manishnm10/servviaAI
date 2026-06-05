# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**ServVia — Neuro-Symbolic Agentic AI Healthcare Platform**

## Repository Structure

Two Django servers, one monorepo:

- **`servvia/`** — ServVia Neuro-Symbolic Agentic AI Healthcare Core (Port 9000, Django 4.2.4, SQLite)
- **`servvia-backend/`** — Data Platform (Port 9001, Django 4.1.5, PostgreSQL)
- **`servvia-frontend/`** — Next.js frontend (Port 3000, not the primary UI)

The primary UI is Django-served at `servvia/templates/index.html` (single-page app, all CSS/JS inline).

## Commands

```bash
# Start Server 1 (AI Healthcare)
cd servvia && python manage.py runserver 0.0.0.0:9000

# Start Server 2 (Data Platform) — use system Python, NOT root venv
cd servvia-backend && C:\Users\cools\AppData\Local\Programs\Python\Python310\python.exe manage.py runserver 0.0.0.0:9001

# Start both (Windows)
servviaAI_servers.bat

# Migrations (Server 1)
cd servvia && python manage.py makemigrations && python manage.py migrate

# Frontend (not primary UI)
cd servvia-frontend && npm run dev
```

There is a root-level venv at `servviaAI/venv/` that auto-activates in bash — it is nearly empty and NOT the correct environment. Server 1 uses `servvia/venv/` or system Python. Server 2 uses system Python directly.

## Pipeline Architecture (Server 1)

All clinical requests flow through `api/views.py::stream_chat_view` → `_run_pipeline()`:

```
Request → Emergency Detection (hardcoded, no LLM)
  → Chronobiology (deterministic circadian/seasonal state)
  → Conversation Context (conversation_manager + recent lab reports from DB)
  → RAG Retrieval + Graph RAG (parallel, Qdrant + Neo4j)
  → Diagnostician (GPT-4.1, serious queries only)
  → Proposer → Critic → max 2 revisions (LangGraph multi-agent)
  → Trust Engine (evidence scoring, PubMed citations)
  → Safety Validation (temporal drug-herb interaction check)
  → Response streaming (word-by-word SSE)
```

Follow-up detection (`_is_conversational_followup()`) skips Trust Engine and Safety Validation for casual responses like "yes", "thank you", "how long will it take".

## Key Files

| File | Purpose |
|---|---|
| `servvia/api/views.py` | Main pipeline orchestrator (~75KB). `stream_chat_view`, `_run_pipeline`, safety validation, SSE streaming |
| `servvia/agents/graph.py` | LangGraph multi-agent: Diagnostician → Proposer → Critic with Groq fallback |
| `servvia/agents/prompts.py` | All LLM prompt templates (DIAGNOSTICIAN, PROPOSER, CRITIC, FALLBACK) |
| `servvia/agents/lab_summarizer.py` | Lab report LLM analysis with structured JSON output |
| `servvia/lab_report/views.py` | Lab report endpoints: OCR → PHI redaction → LLM → SSE streaming |
| `servvia/skin_analysis/views.py` | Skin analysis: Edge AI (Ollama) or Cloud (Gemini) |
| `servvia/edge/ocr_processor.py` | Local PDF/image text extraction (pdfplumber + easyocr) |
| `servvia/edge/phi_redactor.py` | PHI redaction via Presidio + spaCy (PERSON, PHONE, EMAIL only) |
| `servvia/edge/identity_extractor.py` | Patient demographics extraction (regex + LLM, runs BEFORE redaction) |
| `servvia/neurosymbolic/temporal_validator.py` | Drug-herb interaction database with washout periods |
| `servvia/chronobiology/inference.py` | Deterministic circadian/seasonal inference (zero LLM) |
| `servvia/core_temporal/conversation/manager.py` | Session-scoped conversation history (Django cache, 2hr TTL) |
| `servvia/core_temporal/trust_engine/engine.py` | Evidence grading (GRADE standards) + PubMed citations |
| `servvia/legacy_healthcare/rag_service/execute_rag.py` | RAG pipeline: context extraction → query rephrasing → retrieval |
| `servvia/api/voice_asr.py` | Voice speech-to-text: Gemini primary + Whisper fallback, language auto-detect |
| `servvia/api/language_support.py` | Single source of truth for language metadata (STT/TTS BCP-47 + generate-in-language directive) |
| `servvia/api/medical_asr_prompt.py` | Medical priming prompt biasing ASR toward correct symptom terms and Indian-language script |
| `servvia/templates/index.html` | Primary frontend (Django-served SPA) |
| `servvia/django_core/settings.py` | Server 1 Django settings |
| `servvia/django_core/config.py` | Environment variable loading |

## SSE Streaming

All three features (chat, skin, lab report) use Server-Sent Events:

- **Backend**: `StreamingHttpResponse` with `queue.Queue` bridging a pipeline thread to the SSE generator. Word-by-word emission with adaptive `time.sleep()` pacing.
- **Frontend**: `fetch()` + `ReadableStream`, `setInterval` render loop calling `marked.parse()`
- **Chat/Skin**: 70ms render interval, full `marked.parse()` on accumulated text
- **Lab Report**: Two-div incremental render (`frozenDiv` + `activeDiv`). Completed sections (split at `\n\n` or at `\n` when content exceeds 250 chars) are rendered once into `frozenDiv` and never re-parsed. Tables in `activeDiv` are shown as preformatted text until their section completes. This prevents DOM thrashing from heavy markdown (tables, emojis).

## Safety-Critical Patterns

- **Emergency detection** is hardcoded (no LLM) and runs first — never remove or weaken
- **PHI redaction** happens locally before any cloud API call. DATE_TIME and LOCATION are intentionally NOT masked (clinical context)
- **Identity extraction** runs BEFORE PHI redaction to capture demographics
- **Allergen substitution** is proactive and silent — banned ingredients replaced without mentioning them
- **Drug-herb interactions** in `temporal_validator.py` use hardcoded rules with washout periods and severity levels (CRITICAL/HIGH/MODERATE/LOW)
- **Conversation context** is session-scoped — `sessionId` (generated on page load via `crypto.randomUUID()`) ensures page refresh clears state
- **Assistant responses** are saved back to `conversation_manager` so follow-ups work. Lab report results are also injected into conversation context after analysis.

## Models

**Django ORM** (Server 1):
- `user_profile.UserProfile` — allergies/conditions/medications as CSV with `get_*_list()` helpers
- `user_profile.MedicationHistory` — temporal medication tracking with start/stop dates
- `lab_report.LabReport` — extracted text, analysis JSON, abnormal values
- `lab_report.PatientProfile` — multi-patient support ("My Health", "Dad's Health")
- `lab_report.BiomarkerSnapshot` — longitudinal biomarker delta tracking

**Pydantic** (`core/models.py`): `RemedyProposal`, `ValidationResult`, `UserMedicalProfile`, `BiologicalState`

## LLM Configuration

- **Primary**: Azure OpenAI (GPT-4.1, GPT-4.1-mini) via `AZURE_OPENAI_*` env vars
- **Fallback**: Groq (llama-3.3-70b for diagnostician/critic/lab, llama-3.1-8b for proposer) — triggers on HTTP 429 or Azure content filter
- **Vision**: Google Gemini API (skin analysis cloud mode)
- **Edge**: Ollama with local models (skin analysis edge mode)
- **Key deps**: `langgraph 1.0.10`, `openai 2.24.0`, `google-genai 1.65.0`, `pdfplumber`, `easyocr`, `presidio-analyzer`, `spacy` + `en_core_web_lg`, `neo4j 5.14.0`, `pydantic 2.9.2`. numpy pinned to 1.26.4 (PyTorch compat).

## Multilingual Voice (Speech-to-Text)

Voice queries are transcribed via `POST /api/chat/transcribe/` (multipart `audio` clip) → `api/voice_asr.py`:

- **Auto-detect, no selector**: language is detected from the audio, never hinted by the UI.
- **Engine priority**: Google Gemini (`gemini-2.5-flash-lite`, primary — most robust for native script of kn/hi/ta/te; accepts WAV/mp3/ogg/flac) → OpenAI Whisper (fallback; accepts webm/wav directly).
- **Medical priming**: both engines are seeded with `medical_asr_prompt.py` — symptom phrases in romanized + native script that bias the model toward correct terminology and the correct Indian language (e.g. stops Kannada being mis-detected as Hindi).
- **Generate-in-language**: the transcript is returned in its native script, so the chat pipeline detects the language and the LLM replies in that same language (`build_language_directive` in `language_support.py`). No translation round-trip.

## Dual Frontend Rule

**When making any UI-facing change, always update BOTH frontends:**
- `servvia/templates/index.html` — Django-served SPA (primary, production)
- `servvia-frontend/src/app/page.tsx` — Next.js frontend (port 3000)

Both must stay in sync. The Next.js frontend proxies API calls through `/api/proxy/[...path]/route.ts` → `localhost:9000`.

### API Endpoint URLs (Next.js proxy paths)
- Chat stream: `/api/proxy/chat/stream/` (body: `{email_id, query, session_id}`)
- Chat fallback: `/api/proxy/chat/get_answer_for_text_query/` (body: `{email_id, query}`)
- Voice transcribe: `/api/proxy/chat/transcribe/` (FormData: `audio` clip → `{text, language}`)
- Skin analysis: `/api/proxy/skin/analyze/stream/` (FormData: `email_id, session_id, image, analysis_mode`)
- Lab report: `/api/proxy/lab-report/analyze/stream/` (FormData: `email_id, session_id, report[]`)
- Profile check: `/api/proxy/profile/profile/check_profile/` (body: `{email_id}`)
- Profile save: `/api/proxy/profile/profile/create_or_update_profile/` (body: `{email_id, first_name, allergies, medical_conditions, current_medications}`)

## Environment

Secrets in `servvia/.env`: `OPEN_AI_KEY`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `GROQ_API_KEY`, `GOOGLE_API_KEY`, `NEO4J_URI/USER/PASSWORD`, `DJANGO_SECRET_KEY`.
