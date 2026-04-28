# AI Tutor Backend

FastAPI backend for the AI Tutor system. The current codebase is a modular-monolith MVP with:

- authentication and role-based access
- courses and classes
- course file upload and strict RAG-Anything knowledge base ingestion
- AI chat with citations, RAG confidence signals, and teacher review sync
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
- strict RAG-Anything main-chain configuration
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

For the full thesis/demo server stack with:

- API container
- Celery worker
- PostgreSQL
- Redis
- Qdrant
- Neo4j
- MinIO

use the dedicated server deployment files:

- root compose: [`../docker-compose.server.yml`](../docker-compose.server.yml)
- env template: [`.env.server.example`](./.env.server.example)
- guide: [`deploy/SERVER_DEPLOYMENT.md`](./deploy/SERVER_DEPLOYMENT.md)

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

- SQLite is fine for local development, but PostgreSQL is the intended production database.
- Uploaded files are stored under `backend/uploads/` in local mode.
- This backend now treats `RAG-Anything` as the only formal RAG engine. If its dependencies are missing, startup/query paths should fail loudly instead of falling back to Simple RAG.

## RAG-Anything Runtime

This project now uses `RAG-Anything` as the only formal RAG main chain. Before running strict upload / retrieval / QA flows, check the runtime:

```powershell
Set-Location backend
python scripts/check_raganything_runtime.py
```

If the script exits with code `1`, read the printed `blockers` and fix them first.

After the runtime becomes `ready`, you can run one strict end-to-end smoke check against a real local material:

```powershell
Set-Location backend
python scripts/smoke_raganything_pipeline.py --file .\tests\fixtures\multimodal\fixture_notes.txt
```

The smoke report validates these stages in order:

- runtime readiness
- temporary material registration
- `RAG-Anything` ingestion
- main-chain query
- optional teacher-reviewed QA write-back via `add_qa_pair`
- optional follow-up query that verifies the teacher-reviewed content can be retrieved again through the formal `RAG-Anything` main chain

If any stage fails, the script exits with code `1` and prints the failing step in JSON.

Useful options:

- `--class-id <id>`: run the smoke check against a specific class
- `--output-dir <path>`: persist JSON/Markdown smoke reports for experiment records
- `--skip-review-sync`: only validate ingest + query, skip teacher QA write-back
- `--skip-review-query`: write back teacher QA but skip the follow-up retrieval verification
- `--isolated-class`: clone a fresh temporary class so smoke data does not pollute an existing class knowledge base

By default, the smoke script writes:

- `runtime_tmp/rag_smoke_reports/raganything_smoke_<run_id>.json`
- `runtime_tmp/rag_smoke_reports/raganything_smoke_<run_id>.md`

For audio/video preprocessing validation, run the multimodal suite:

```powershell
Set-Location backend
python scripts/smoke_multimodal_raganything_suite.py --isolated-class --skip-review-sync
```

The suite creates deterministic local fixtures and verifies both routes through the formal RAG-Anything chain:

- audio: sidecar transcript -> `content_list` text -> `insert_content_list` -> LightRAG graph/vector index -> query
- video: sidecar transcript + keyframe PNG -> `content_list` text/image -> VLM-enhanced RAG-Anything processing -> reranked query

If you enable real automatic audio/video preprocessing, configure `MULTIMODAL_AUTO_PREPROCESS_ENABLED=true`. The backend now supports two ASR routes:

- local ASR: `ASR_PROVIDER=faster_whisper` plus the `faster-whisper` package
- API ASR: `ASR_PROVIDER=api` plus `ASR_API_BASE`, `ASR_API_KEY`, `ASR_MODEL`, and optional auth/path overrides

Video auto preprocessing still requires `FFMPEG_PATH` so the backend can extract audio and keyframes before sending the transcript and visual frames into `RAG-Anything`.

Without ASR, production audio/video files should provide a transcript sidecar (`.txt`, `.md`, `.vtt`, or `.srt`) so they can still enter RAG-Anything cleanly.

## Knowledge Graph API

The course graph exposed by `/api/v1/courses/{course_id}/graph` is a visualization and analytics projection built from `RAG-Anything` extraction results. Retrieval still uses the formal `RAG-Anything + LightRAG` chain; the graph API is used for teacher-side inspection, paper screenshots, and business-side graph queries.

Default response fields:

- `nodes` / `edges`: graph elements projected from `KnowledgeEntity` and `KnowledgeRelation`
- `stats`: basic counts for nodes, edges, and classes
- `summary`: entity-type distribution, relation-type distribution, source-material count, material-type distribution, and average confidence
- `legend`: normalized entity/relation type buckets for frontend visualization
- `materials`: material-level provenance summaries referenced by the graph
- `filters`: the applied filter parameters plus available class/entity-type options

Useful query parameters:

- `class_id`: only return the graph for one class inside the course
- `entity_type`: only keep a specific node type such as `concept`, `material`, or `image`
- `min_confidence`: confidence threshold applied to both nodes and edges
- `limit`: max number of highest-confidence nodes returned

## External Storage Topology

The current adapter still writes the formal `RAG-Anything + LightRAG` index to the local working directory by default. The backend now also exposes structured readiness/configuration status for external storage so the thesis/demo deployment can document the intended production topology explicitly.

Recommended topology for the full thesis system:

- vector database: `Qdrant`
- graph database: `Neo4j`
- local LightRAG working directory: kept as the adapter's current effective storage path unless the lower-level storage adapter is replaced later

Relevant environment variables:

```env
RAG_STORAGE_BACKEND=lightrag-default

VECTOR_DB_PROVIDER=qdrant
VECTOR_DB_URL=http://localhost:6333
VECTOR_DB_API_KEY=
VECTOR_DB_COLLECTION=raganything_chunks

GRAPH_DB_PROVIDER=neo4j
GRAPH_DB_URL=bolt://localhost:7687
GRAPH_DB_DATABASE=neo4j
GRAPH_DB_USERNAME=neo4j
GRAPH_DB_PASSWORD=your_password
```

Supported storage backend labels in the backend status model:

- `lightrag-default`: current local LightRAG/RAG-Anything working directory storage
- `qdrant`: intended external vector store topology
- `neo4j`: intended external graph store topology
- `qdrant-neo4j`: intended split topology with Qdrant for vectors and Neo4j for graph projection

When `RAG_STORAGE_BACKEND` is switched to `qdrant`, `neo4j`, or `qdrant-neo4j` and the target service is reachable, the backend now injects the corresponding official LightRAG storage adapters into the formal `RAG-Anything` chain. Runtime/admin reports will show both configuration readiness and live connectivity diagnostics.

For a local thesis/demo bootstrap, you can start both services with:

```powershell
docker compose -f backend/deploy/docker-compose.rag-storage.yml up -d
```

To generate a backend-specific env patch for the current machine, run:

```powershell
python backend/scripts/prepare_external_rag_storage.py --backend qdrant-neo4j
```

You can also start from the committed template [`.env.rag-storage.example`](./.env.rag-storage.example).

Before switching an existing project to external storage, you can audit which courses/materials need reindexing:

```powershell
python backend/scripts/list_reindex_targets.py
```

To execute only the storage-mismatch rebuilds, use:

```powershell
python backend/scripts/rebuild_storage_targets.py --apply
```

To use the backend with a real `RAGAnythingAdapter`, run it in the same Python environment where `raganything`, `mineru`, and LibreOffice are available, then set:

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
- If RAG-Anything is unavailable, the backend should report a hard failure instead of silently using a simplified fallback engine.

Example split-provider setup:

```env
RAG_ENGINE=raganything

LLM_MODEL=gpt-5.4
LLM_API_BASE=https://beecode.cc
LLM_API_KEY=your_llm_key
LLM_WIRE_API=responses

EXTRACT_MODEL=Qwen/Qwen2.5-7B-Instruct
EXTRACT_API_BASE=https://api.siliconflow.cn/v1
EXTRACT_API_KEY=your_extract_key
EXTRACT_WIRE_API=chat_completions
RAGANYTHING_DEFAULT_LLM_TIMEOUT_SECONDS=180

EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_API_BASE=https://api.siliconflow.cn/v1/
EMBEDDING_API_KEY=your_embedding_key
EMBEDDING_DIM=1024

VLM_MODEL=qwen3-vl-plus
VLM_API_BASE=https://apis.iflow.cn/v1
VLM_API_KEY=your_vlm_key
VLM_WIRE_API=chat_completions

RERANKER_PROVIDER=api
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_API_BASE=https://api.siliconflow.cn/v1
# Optional when EMBEDDING_API_KEY or EXTRACT_API_KEY already points to SiliconFlow.
RERANKER_API_KEY=your_siliconflow_key
RERANKER_API_PATH=/rerank

LIBREOFFICE_PATH=E:\A_software\LibreOffice\program\soffice.exe
```

For providers like `beecode.cc`, the backend now calls:

- `POST https://beecode.cc/responses`
- auth header: `x-api-key: <key>`

So do not manually append `/v1` for that LLM base.

Recommended split for the current system:

- final answer generation: `gpt-5.4 @ beecode.cc`
- entity / relation extraction during indexing: `Qwen/Qwen2.5-7B-Instruct @ SiliconFlow`
- embedding: `BAAI/bge-m3 @ SiliconFlow`
- reranking: `BAAI/bge-reranker-v2-m3 @ SiliconFlow`
- visual understanding: `Qwen/Qwen3-VL-8B-Instruct @ SiliconFlow`

Why `Qwen/Qwen2.5-7B-Instruct` for extraction in the current smoke-tested setup:

- stronger structured instruction following than a reasoning-heavy model
- stable OpenAI-compatible chat-completions behavior for LightRAG extraction prompts
- avoids unnecessary reasoning overhead compared with thinking models
