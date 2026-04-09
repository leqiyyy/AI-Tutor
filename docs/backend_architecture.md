# Backend Architecture

## Overview

The backend is implemented as a **modular monolith**. It keeps business capabilities in one deployable FastAPI service while separating responsibilities by layer so the MVP can run now and evolve later.

Core business line:

1. teacher uploads course material
2. system ingests material into a class/course knowledge base
3. student or teacher asks AI assistant
4. system answers with grounded citations
5. low-confidence or disliked answers enter review queue
6. teacher correction is synced back to the fallback knowledge store
7. analytics and flashcards improve the learning loop

## Layers

### Access Layer

Main files:

- [main.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/main.py)
- [api.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/api/v1/api.py)
- [exceptions.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/core/exceptions.py)
- [responses.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/core/responses.py)

Responsibilities:

- FastAPI application bootstrap
- router aggregation
- CORS
- request logging
- health endpoints
- unified exception and response structure

### Core Infrastructure Layer

Main files:

- [config.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/core/config.py)
- [database.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/core/database.py)
- [redis.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/core/redis.py)
- [celery_app.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/core/celery_app.py)
- [logging.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/core/logging.py)

Responsibilities:

- configuration loading
- database engine/session setup
- Redis adapter
- Celery adapter
- structured logging

### Domain Model Layer

Main folders:

- [models](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/models)
- [schemas](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/schemas)

Responsibilities:

- persistence models
- API request/response schemas
- enum/status definitions embedded in ORM models

Key entity groups:

- users / auth
- courses / classes / class members
- materials / KB spaces / file parse tasks
- chat sessions / chat messages / citations
- review items / review sync records
- flashcards / flashcard records
- learning records / question analytics / student profiles

### Service Layer

Main files:

- [auth_service.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/services/auth_service.py)
- [course_service.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/services/course_service.py)
- [task_service.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/services/task_service.py)
- [chat_service.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/services/chat_service.py)
- [kb_service.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/services/kb_service.py)
- [analytics_service.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/services/analytics_service.py)
- [flashcard_service.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/services/flashcard_service.py)

Responsibilities:

- business rules
- permission-sensitive orchestration
- aggregation for API responses
- learning event recording

### AI / Knowledge Layer

Main files:

- [base.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/ai/base.py)
- [simple_engine.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/integrations/rag/simple_engine.py)
- [simple.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/integrations/parser/simple.py)

Responsibilities:

- parser abstraction
- simplified knowledge ingestion
- fallback retrieval
- citation generation
- confidence estimation
- teacher answer feedback loop

### Worker Layer

Main files:

- [system.py](e:/all_files/project2/AI_tutor/AI-Tutor-end5/backend/app/workers/tasks/system.py)

Responsibilities:

- placeholder Celery task registration
- future async ingestion / analytics jobs

## API Group Mapping

### Teacher-facing

- `/api/v1/courses`
- `/api/v1/classes`
- `/api/v1/tasks`
- `/api/v1/chat`
- `/api/v1/reviews`
- `/api/v1/notifications`

### Student-facing

- `/api/v1/courses`
- `/api/v1/classes`
- `/api/v1/tasks`
- `/api/v1/chat`
- `/api/v1/flashcards`
- `/api/v1/students/me/profile`

### Admin-facing

- `/api/v1/admin`

## Storage Strategy

Current MVP mode:

- business data: SQLite or PostgreSQL
- file storage: local filesystem
- task queue: Celery adapter with optional Redis
- RAG: simplified in-process retrieval with parsed chunks stored in `file_parse_tasks`

Future replacement points:

- local storage -> MinIO
- simple parser -> specialized PDF/Docx/OCR/multimodal parsers
- simple RAG -> vector / graph / hybrid retrieval stack
- inline ingestion -> Celery async jobs

Current adapter status:

- the backend now includes a real `RAGAnythingAdapter`
- when `RAG_ENGINE=raganything`, document processing and query orchestration can run through the official RAG-Anything package
- business metadata, citations, review queue, and analytics remain in the local service/database layer

## Health and Operability

Health endpoints:

- `/health`
- `/health/live`
- `/health/ready`

What they check:

- database connectivity
- Redis availability when enabled
- storage backend health
- Celery adapter configuration state

## Current Design Tradeoffs

- The service is optimized for local MVP execution first.
- Retrieval is intentionally simple so the system stays runnable without external AI infra.
- The same public API shape is designed to survive a later swap to stronger model and retrieval backends.
