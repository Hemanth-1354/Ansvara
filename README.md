# Ansvara

Ansvara is a tool for automatically answering structured questionnaires using your own reference documents. You upload a questionnaire and a set of internal documents, and the system generates grounded answers with citations using a RAG pipeline backed by Groq's LLaMA 3.1.

Built for teams that regularly deal with security reviews, vendor assessments, or compliance audits — where the same internal knowledge base is used repeatedly to answer similar questions.

Live: https://ansvara.vercel.app

---

## How it works

1. Register and log in
2. Upload a questionnaire (PDF, DOCX, TXT, or XLSX)
3. Upload your reference documents — these become the source of truth
4. Click Generate — the system parses each question, retrieves relevant chunks via TF-IDF, and sends them to Groq LLaMA 3.1 to produce a grounded answer
5. Review and edit answers inline
6. Export as PDF or DOCX, with answers inserted below each question and citations included

If a question cannot be answered from the reference documents, the system returns "Not found in references." rather than hallucinating.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI |
| Database | PostgreSQL (Neon) |
| LLM | Groq API — LLaMA 3.1 8B Instant |
| Frontend | React 18, Vite, Tailwind CSS |
| Auth | JWT via python-jose + bcrypt |
| Retrieval | Custom TF-IDF chunking (no vector DB needed) |
| Export | python-docx, ReportLab |
| Infra | Docker, Render (backend), Vercel (frontend) |

---

## Features

- JWT authentication with per-user document isolation
- Parses questions from numbered lists, bullets, and natural language formats
- TF-IDF retrieval over chunked reference documents (500 words, 50-word overlap)
- Confidence score per answer based on retrieval quality
- Evidence snippets — expandable raw chunks that were used to generate each answer
- Selective regeneration — re-run individual answers without redoing the whole questionnaire
- Full run history — every generation is saved independently so you can compare versions
- Export preserves original question order with answers and citations inline

---

## Running locally

**Prerequisites:** Docker, Docker Compose, a Groq API key (free at console.groq.com)

```bash
git clone https://github.com/your-username/ansvara.git
cd ansvara
cp .env.example .env
# Add your GROQ_API_KEY to .env
docker-compose up --build
```

App runs at `http://localhost:3000`. API docs at `http://localhost:8000/docs`.

Sample questionnaire and reference documents are in `sample-data/` if you want to test without your own files.

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key for LLaMA 3.1 |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | JWT signing secret |
| `ALLOWED_ORIGINS` | Yes | Comma-separated frontend URLs for CORS |

---

## Project structure

```
ansvara/
├── backend/
│   ├── main.py                      # FastAPI app, CORS, router registration
│   ├── requirements.txt
│   ├── Dockerfile
│   └── app/
│       ├── api/
│       │   ├── auth.py              # Register, login, JWT
│       │   ├── questionnaires.py    # Upload and parse questionnaires
│       │   ├── documents.py         # Reference document management
│       │   └── answers.py           # Generation, editing, export
│       ├── models/
│       │   └── database.py          # SQLAlchemy models
│       └── services/
│           ├── parser.py            # Text extraction and question parsing
│           ├── llm.py               # RAG pipeline and Groq integration
│           └── exporter.py          # DOCX and PDF export
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── store/                   # Zustand auth store
│   │   └── utils/                   # Axios client
│   ├── vercel.json
│   └── vite.config.js
├── sample-data/
├── docker-compose.yml
└── .env.example
```

---

## Assumptions

- Reference documents are per-user and persist across runs, acting as a personal knowledge base
- Question parsing covers the most common formats (numbered, bulleted, Q: prefixed). Unusual layouts may need manual cleanup
- TF-IDF is sufficient for small to medium document sets. Semantic search would improve recall on larger corpora
- LLaMA 3.1 8B Instant was chosen for speed and cost. Swapping to a larger model in `llm.py` improves answer quality

---

## Trade-offs

**TF-IDF over vector embeddings** — avoids the overhead of a vector database and embedding API calls. Works well for focused document sets but misses semantically similar content that doesn't share keywords.

**LLaMA 3.1 8B over GPT-4** — the free Groq tier handles the load fine for this use case. Accuracy drops on ambiguous questions but is acceptable for structured compliance content.

**`create_all` over Alembic migrations** — fine for initial deployment, but schema changes in production would require a proper migration setup.

**In-memory file handling** — uploaded files are processed and stored as text in the database rather than on disk or object storage. Simpler to deploy but limits handling of very large files.

---

## What I'd improve with more time

- Replace TF-IDF with `sentence-transformers` + pgvector for semantic retrieval
- Stream LLM responses token by token instead of waiting for the full answer
- Add Celery + Redis for async generation so large questionnaires don't block the request
- Proper Alembic migration setup instead of `create_all`
- Rate limiting on auth endpoints
- Forgot password flow via Resend (transactional email)
- Team support with shared reference document libraries across users
