# AI Tutor Backend

FastAPI backend for the AI Tutor system. The current codebase is a modular-monolith MVP with:

- authentication and role-based access
- courses and classes
- course file upload and simplified knowledge base ingestion
- AI chat with citations and review queue fallback
- flashcards, analytics, and student profile snapshots

## Stack

- Python 3.11+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- Pydantic v2
- Redis / Celery / MinIO adapters
- SQLite fallback for local development

## Quick Start

### 1. Install dependencies

```powershell
Set-Location backend
python -m pip install -r requirements.txt
```

### 2. Configure environment

```powershell
Copy-Item .env.example .env
```

The default local setup uses:

- SQLite
- local filesystem storage
- mock RAG / mock AI
- Redis disabled

### 3. Seed demo data

```powershell
python -m app.db.seed
```

Demo accounts:

- admin: `admin@aitutor.local` / `Admin123!`
- teacher: `teacher@aitutor.local` / `Teacher123!`
- student: `student@aitutor.local` / `Student123!`
- teacher login alias: `T2024001`
- student login alias: `2024301001`
- class invite code: `CS301A1`

### 4. Run the API

```powershell
uvicorn app.main:app --reload
```

Open:

- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## Database Migrations

Inspect migration heads:

```powershell
alembic heads
alembic history
```

Run migrations:

```powershell
alembic upgrade head
```

## Celery Worker

If Redis is enabled:

```powershell
celery -A app.core.celery_app:celery_app worker --loglevel=info
```

## Docker

From the repository root:

```powershell
docker compose up --build
```

## Tests

Run smoke tests from the repository root:

```powershell
python -m pytest backend/tests -q
```

## Implemented MVP Flows

1. Login -> current user -> courses/classes access
2. Teacher upload file -> parse task -> KB status/graph
3. Student/teacher chat -> citation -> low-confidence review
4. Student dislike -> teacher review submit -> sync record
5. Flashcard fetch -> review record persistence
6. Course analytics -> student profile snapshot

## Key API Groups

- `/api/v1/auth`
- `/api/v1/courses`
- `/api/v1/classes`
- `/api/v1/tasks`
- `/api/v1/chat`
- `/api/v1/reviews`
- `/api/v1/flashcards`
- `/api/v1/notifications`
- `/api/v1/students`

## Important Notes

- The current RAG pipeline is intentionally simplified and replaceable.
- SQLite is fine for local development, but PostgreSQL is the intended production database.
- Uploaded files are stored under `backend/uploads/` in local mode.

## RAG-Anything Integration

The backend now includes a real `RAGAnythingAdapter` path. To use it, run the backend in the same Python environment where `raganything`, `mineru`, and LibreOffice are available, then set:

```powershell
$env:RAG_ENGINE='raganything'
$env:LLM_API_KEY='your_llm_key'
$env:LLM_API_BASE='your_llm_base_url'
$env:LLM_MODEL='your_chat_model'

$env:EMBEDDING_API_KEY='your_embedding_key'
$env:EMBEDDING_API_BASE='your_embedding_base_url'
$env:EMBEDDING_MODEL='your_embedding_model'
$env:EMBEDDING_DIM='1536'

$env:VLM_API_KEY='your_vlm_key'
$env:VLM_API_BASE='your_vlm_base_url'
$env:VLM_MODEL='your_vlm_model'

$env:LIBREOFFICE_PATH='E:\A_software\LibreOffice\program\soffice.exe'
```

Notes:

- `RAGAnything` requires a real LLM function and embedding function.
- The backend uses LightRAG's official OpenAI / OpenAI-compatible wrappers under the hood.
- If `RAG_ENGINE` is not set to `raganything`, the backend continues using the simplified fallback engine.

Example split-provider setup:

```env
RAG_ENGINE=raganything

LLM_MODEL=gpt-5.4
LLM_API_BASE=https://beecode.cc
LLM_API_KEY=your_llm_key
LLM_WIRE_API=responses

EXTRACT_MODEL=Qwen3-235B-A22B-Instruct
EXTRACT_API_BASE=https://apis.iflow.cn/v1
EXTRACT_API_KEY=your_extract_key
EXTRACT_WIRE_API=chat_completions

EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_API_BASE=https://api.siliconflow.cn/v1/
EMBEDDING_API_KEY=your_embedding_key
EMBEDDING_DIM=1024

VLM_MODEL=qwen3-vl-plus
VLM_API_BASE=https://apis.iflow.cn/v1
VLM_API_KEY=your_vlm_key
VLM_WIRE_API=chat_completions

LIBREOFFICE_PATH=E:\A_software\LibreOffice\program\soffice.exe
```

For providers like `beecode.cc`, the backend now calls:

- `POST https://beecode.cc/responses`
- auth header: `x-api-key: <key>`

So do not manually append `/v1` for that LLM base.

Recommended split for the current system:

- final answer generation: `gpt-5.4 @ beecode.cc`
- entity / relation extraction during indexing: `Qwen3-235B-A22B-Instruct @ iflow`
- embedding: `BAAI/bge-m3 @ SiliconFlow`

Why `Qwen3-235B-A22B-Instruct` for extraction:

- stronger structured instruction following than a reasoning-heavy model
- large enough context window for extraction prompts
- avoids unnecessary reasoning overhead compared with thinking models
