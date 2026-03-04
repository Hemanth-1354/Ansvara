# QuestionnAIre — AI-Powered Questionnaire Answering Tool

> **GTM Engineering Internship Assignment**

## What I Built

**QuestionnAIre** is a full-stack web application that automates the completion of structured questionnaires (security reviews, vendor assessments, compliance audits) using AI. Users upload a questionnaire and reference documents; the system uses RAG (Retrieval-Augmented Generation) with Groq's LLaMA 3.1 to answer each question with citations and confidence scores.

### Fictional Company

**Industry:** Healthcare SaaS / Health Tech

**Company:** NovaMed Health — a B2B SaaS platform that helps healthcare organizations automate clinical workflows, manage patient records, and maintain regulatory compliance. NovaMed serves hospitals, outpatient clinics, and telehealth providers across the US, operating under HIPAA and HITRUST frameworks.

Sample questionnaire and reference documents are provided in `sample-data/`.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI |
| Database | PostgreSQL 15 |
| LLM | Groq API (LLaMA 3.1 8B Instant) — free tier |
| Frontend | React 18, Vite, Tailwind CSS |
| Auth | JWT (python-jose + bcrypt) |
| RAG | Custom TF-IDF chunk retrieval |
| Export | python-docx, ReportLab (PDF) |
| Container | Docker + Docker Compose |

---

## Features Implemented

### Phase 1 — Core Workflow ✅
- User signup & login with JWT authentication
- Upload questionnaire (PDF, DOCX, TXT, XLSX)
- Upload multiple reference documents
- AI parses questions automatically
- RAG pipeline: chunk → retrieve → answer via Groq LLaMA 3.1
- Each answer includes at least one citation
- "Not found in references." returned when answer cannot be grounded

### Phase 2 — Review & Export ✅
- Review all Q&A pairs in a structured web view
- Edit individual answers inline before export
- Export to DOCX or PDF — preserves question order, inserts answers below each question, includes citations

### Nice-to-Have Features ✅ (Implemented 4/5)
1. **Confidence Score** — TF-IDF retrieval quality score shown as a progress bar (0–100%)
2. **Evidence Snippets** — Raw text chunks from reference docs shown in expandable cards
3. **Partial Regeneration** — Select individual answers and regenerate with one click
4. **Version History** — Dashboard shows all previous runs; each run is stored independently

---

## Architecture

```
┌──────────────────┐     HTTP/REST      ┌──────────────────────────────┐
│  React Frontend  │◄──────────────────►│   FastAPI Backend            │
│  (Nginx :3000)   │                    │   (:8000)                    │
└──────────────────┘                    │                              │
                                        │  /api/auth     JWT auth      │
                                        │  /api/questionnaires upload  │
                                        │  /api/documents  ref docs    │
                                        │  /api/answers  RAG + export  │
                                        └──────────┬───────────────────┘
                                                   │
                              ┌────────────────────┼──────────────────┐
                              │                    │                  │
                        ┌─────▼─────┐      ┌──────▼─────┐   ┌───────▼──────┐
                        │ PostgreSQL│      │ Groq API   │   │ File Storage │
                        │ (DB :5432)│      │ LLaMA 3.1  │   │ /app/uploads │
                        └───────────┘      └────────────┘   └──────────────┘

RAG Pipeline:
  Upload doc → Extract text → Chunk (500 words, 50 overlap)
  Question → TF-IDF similarity → Top-3 chunks → Groq LLM → Answer + Citations
```

---

## Quickstart

### Prerequisites
- Docker & Docker Compose installed
- Groq API key (free at https://console.groq.com)

### 1. Clone / Unzip

```bash
unzip questionnaire-tool.zip
cd questionnaire-tool
```

### 2. Set Your Groq API Key

```bash
cp .env.example .env
# Edit .env and set your GROQ_API_KEY
```

Or export inline:
```bash
export GROQ_API_KEY=gsk_your_key_here
```

### 3. Build & Run

```bash
docker-compose up --build
```

Wait ~60 seconds for all services to start.

### 4. Open the App

- **App:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs

### 5. Try It

1. Register an account
2. Go to "New Questionnaire"
3. Upload `sample-data/questionnaire.txt`
4. Upload all 3 files from `sample-data/` as reference documents
5. Click "Generate Answers with AI"
6. Review, edit, and export as PDF or DOCX

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | *(required)* | Groq API key for LLaMA 3.1 |
| `DATABASE_URL` | postgresql://... | PostgreSQL connection string |
| `SECRET_KEY` | change-me | JWT signing secret |

> **Without a Groq API key**, the app still works — answers will be generated from raw retrieved text snippets as a fallback.

---

## Assumptions

1. **Single-user reference library** — Reference documents are per-user and reused across runs. This simulates an internal knowledge base.
2. **Question parsing** — The parser handles numbered lists (1. / 1) / Q1:), bullets, and question-sentence heuristics. Edge cases with unusual formatting may require adjustment.
3. **File size** — Designed for documents up to ~50 pages. Very large PDFs may be slow due to chunking.
4. **Groq free tier** — LLaMA 3.1 8B Instant is used (fast, free tier). Switch to `llama-3.1-70b-versatile` in `llm.py` for better accuracy.
5. **TF-IDF RAG** — A lightweight custom retriever is used instead of a vector DB (no external vector DB required). This is sufficient for small-to-medium document sets.

---

## Trade-offs

| Decision | Trade-off |
|----------|-----------|
| TF-IDF retrieval vs. vector embeddings | Simpler, no extra infra; less semantic understanding |
| Groq LLaMA 3.1 vs. OpenAI GPT-4 | Free tier; slightly less accurate but fast |
| File-based storage vs. S3 | Simpler for demo; Docker volume persists data |
| Single-file React build | Easier to containerize; less code splitting |
| postgresql over sqlite | Production-ready; requires Docker but real persistence |

---

## What I'd Improve With More Time

1. **Vector embeddings** — Replace TF-IDF with `sentence-transformers` + pgvector for semantic search
2. **Streaming answers** — Stream LLM responses token-by-token for better UX
3. **Async job queue** — Use Celery + Redis for async generation on large questionnaires
4. **Document preview** — Show parsed question preview before generation
5. **Team/org support** — Multi-tenant support with shared reference document libraries
6. **Coverage gap analysis** — Automatically identify reference doc gaps based on "not found" patterns
7. **Cloud deployment** — Terraform for AWS ECS/Fargate deployment with RDS

---

## Project Structure

```
questionnaire-tool/
├── backend/
│   ├── main.py                    # FastAPI app
│   ├── requirements.txt
│   ├── Dockerfile
│   └── app/
│       ├── api/
│       │   ├── auth.py            # JWT auth endpoints
│       │   ├── questionnaires.py  # Upload & parse questionnaires
│       │   ├── documents.py       # Reference doc management
│       │   └── answers.py         # Generate, edit, export
│       ├── models/
│       │   └── database.py        # SQLAlchemy models
│       └── services/
│           ├── parser.py          # Document text extraction & question parsing
│           ├── llm.py             # RAG pipeline + Groq LLM
│           └── exporter.py        # DOCX/PDF export
├── frontend/
│   ├── src/
│   │   ├── pages/                 # LoginPage, RegisterPage, DashboardPage, WorkspacePage, RunDetailPage
│   │   ├── components/            # Layout, FileDropzone, ConfidenceBar
│   │   ├── store/                 # Zustand auth store
│   │   └── utils/                 # Axios API client
│   ├── Dockerfile
│   └── nginx.conf
├── sample-data/
│   ├── questionnaire.txt          # 12-question compliance questionnaire
│   ├── security_policy.txt        # NovaMed security reference doc
│   ├── data_management_policy.txt # NovaMed data management doc
│   └── certifications_and_audits.txt
├── docker-compose.yml
├── .env.example
└── README.md
```
