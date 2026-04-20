# API Contractï¼ˆåŽç«¯å…ˆè¡Œç‰ˆï¼?
æ›´æ–°æ—¶é—´ï¼?026-04-17

---

## 1. é€šç”¨çº¦å®š

### 1.1 Base URL

- å¼€å‘çŽ¯å¢ƒï¼š`/api/v1`

### 1.2 ç»Ÿä¸€å“åº”ç»“æž„

```json
{
  "code": 200,
  "message": "success",
  "data": {},
  "meta": {
    "request_id": "uuid",
    "version": "0.1.0"
  }
}
```

é”™è¯¯å“åº”ï¼?
```json
{
  "code": 400,
  "message": "Bad request",
  "data": null,
  "meta": {
    "request_id": "uuid",
    "version": "0.1.0"
  }
}
```

### 1.3 è®¤è¯

```http
Authorization: Bearer <access_token>
```

### 1.4 å­—æ®µå…¼å®¹ç­–ç•¥

- ç™»å½•ï¼šå…¼å®?`account` ä¸?`email`
- æ³¨å†Œï¼šå…¼å®?camelCase ä¸?snake_case
- èŠå¤©è¯·æ±‚ï¼šå…¼å®?`message` ä¸?`content`

---

## 2. å·²å®žçŽ°æ ¸å¿ƒæŽ¥å£ï¼ˆå½“å‰å¯ç”¨ï¼?
### 2.1 è®¤è¯

- `POST /auth/send-verify-code`
- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

### 2.2 è¯¾ç¨‹ä¸Žç­çº?
- `GET /courses`
- `GET /courses/{course_id}`
- `POST /courses`
- `GET /courses/{course_id}/analytics`
- `GET /classes`
- `GET /classes/{class_id}`
- `POST /classes`
- `PUT /classes/{class_id}`
- `POST /classes/join`
- `POST /classes/{class_id}/invite`
- `GET /classes/{class_id}/members`

### 2.3 æ–‡ä»¶ä¸ŽçŸ¥è¯†åº“

- `POST /courses/{course_id}/files/upload`
- `GET /courses/{course_id}/files`
- `GET /courses/{course_id}/files/{file_id}/preview`
- `GET /courses/{course_id}/files/{file_id}/download`
- `GET /courses/{course_id}/files/{file_id}/analysis`
- `GET /courses/{course_id}/kb/status`
- `POST /courses/{course_id}/kb/rebuild`
- `GET /courses/{course_id}/graph`
- `GET /courses/{course_id}/search`

### 2.4 èŠå¤©ä¸Žå®¡æ ?
- `GET /chat/sessions`
- `GET /chat/sessions/{session_id}/messages`
- `POST /chat/query`
- `POST /chat/query-with-image`
- `POST /chat/messages/{message_id}/feedback`
- `GET /reviews/pending`
- `POST /reviews/{review_id}/submit`
- `POST /reviews/escalate`

### 2.5 ä»»åŠ¡ã€é€šçŸ¥ã€é—ªå¡ã€å­¦ç”Ÿç”»åƒ?
- `GET /tasks`
- `GET /tasks/{task_id}`
- `POST /tasks`
- `POST /tasks/{task_id}/submit`
- `GET /tasks/{task_id}/submissions`
- `GET /notifications`
- `POST /notifications`
- `POST /notifications/mark-read`
- `GET /flashcards`
- `POST /flashcards/{flashcard_id}/review`
- `GET /students/me/profile`
- `GET /students/me/reports/weekly`
- `GET /students/me/reports/monthly`
- `GET /students/me/export`
- `GET /students/me/mistakes`
- `POST /students/me/mistakes`
- `PUT /students/me/mistakes/{mistake_id}/mastered`
- `POST /students/me/mistakes/{mistake_id}/practice`

### 2.6 ç®¡ç†ç«?
- `GET /admin/overview`
- `GET /admin/users`
- `GET /admin/classes`
- `GET /admin/courses`
- `GET /admin/reviews`
- `GET /admin/settings`
- `GET /admin/model-config`
- `PUT /admin/model-config`

---

## 3. è®¡åˆ’è¡¥é½æŽ¥å£ï¼ˆåŽç«¯ä¸‹ä¸€é˜¶æ®µï¼?
### 3.1 åé¦ˆåˆ†æž

- `GET /analytics/feedback/overview`
- `GET /analytics/feedback/reasons`
- `GET /analytics/feedback/keywords`
- `GET /analytics/feedback/knowledge-gaps`
- `GET /analytics/feedback/suggestions`
- `POST /analytics/feedback/export`

### 3.2 æ™ºèƒ½æŽ¨è

- `GET /recommendations/materials`
- `GET /recommendations/learning-path`
- `POST /recommendations/feedback`

### 3.3 å¤šæ¨¡æ€ç»“æžœæŸ¥è¯?
- `GET /files/{file_id}/preview`
- `GET /files/{file_id}/transcript`
- `GET /files/{file_id}/keyframes`
- `GET /files/{file_id}/ocr`

### 3.4 ç®¡ç†ç«¯æ€§èƒ½ä¸Žå®žéª?
- `GET /admin/rag-performance`
- `GET /admin/experiment-results`

---

## 4. èŠå¤©é—®ç­”ç¤ºä¾‹

### 4.1 è¯·æ±‚

`POST /chat/query`

```json
{
  "course_id": "course_uuid",
  "message": "What is TCP slow start?",
  "session_id": null,
  "attachments": []
}
```

### 4.2 å“åº”

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "session_id": "session_uuid",
    "message_id": "message_uuid",
    "content": "answer text",
    "sources": [
      {
        "name": "tcp_notes.txt",
        "page": 1,
        "type": "txt",
        "score": 0.91,
        "chunk_id": "tcp_notes-chunk-1"
      }
    ],
    "suggestions": [
      "Can you explain this with an example?"
    ],
    "confidence": 0.85,
    "needs_review": false
  }
}
```

---

## 5. é”™è¯¯ç å»ºè®®ï¼ˆä¸‹ä¸€é˜¶æ®µå†»ç»“ï¼?
| code | å«ä¹‰ |
|---|---|
| 400 | å‚æ•°é”™è¯¯ |
| 401 | æœªè®¤è¯æˆ– token æ— æ•ˆ |
| 403 | æ— æƒé™?|
| 404 | èµ„æºä¸å­˜åœ?|
| 409 | èµ„æºå†²çª |
| 422 | æ ¡éªŒå¤±è´¥ |
| 500 | æœåŠ¡å†…éƒ¨é”™è¯¯ |
| 503 | ä¾èµ–æœåŠ¡ä¸å¯ç”?|

---

## 6. ç‰ˆæœ¬ç­–ç•¥

1. å½“å‰ä¸»ç‰ˆæœ¬ï¼š`v1`ã€? 
2. ç ´åæ€§å˜æ›´ä»…å…è®¸é€šè¿‡æ–°ç‰ˆæœ¬è·¯å¾„å‘å¸ƒã€? 
3. ä¿æŒç™»å½•/æ³¨å†Œå­—æ®µåˆ«åå…¼å®¹ï¼Œå‡å°‘å‰ç«¯è”è°ƒè¿”å·¥ã€? 
## 7. 2026-04-17 åè®®å¢žé‡ï¼ˆS0å®žçŽ°ï¼?
### 7.1 Meta è§„èŒƒï¼ˆæ–°å¢?`trace_id`ï¼?
æ‰€æœ‰å“åº”ï¼ˆæˆåŠŸ/å¤±è´¥ï¼‰ç»Ÿä¸€è¿”å›žï¼?
```json
{
  "code": 200,
  "message": "success",
  "data": {},
  "meta": {
    "request_id": "uuid",
    "trace_id": "trace_id_or_request_id",
    "version": "0.1.0"
  }
}
```

è¯´æ˜Žï¼?- `X-Request-ID`ï¼šç”±åŽç«¯æ¯æ¬¡è¯·æ±‚ç”Ÿæˆã€?- `X-Trace-ID`ï¼šä¼˜å…ˆé€ä¼ è¯·æ±‚å¤´ï¼›è‹¥æœªä¼ åˆ™å›žé€€ä¸ºæœ¬æ¬?`request_id`ã€?
### 7.2 é”™è¯¯ç»“æž„ï¼ˆæ–°å¢žç¨³å®?`error.key`ï¼?
é”™è¯¯å“åº”ç¤ºä¾‹ï¼?
```json
{
  "code": 401,
  "message": "Authentication required",
  "data": null,
  "error": {
    "key": "auth_required"
  },
  "meta": {
    "request_id": "uuid",
    "trace_id": "trace_id_or_request_id",
    "version": "0.1.0"
  }
}
```

### 7.3 å†»ç»“é”™è¯¯ç›®å½•ï¼ˆç¬¬ä¸€ç‰ˆï¼‰

| HTTP/Code | error.key | å«ä¹‰ |
|---|---|---|
| 400 | `bad_request` | è¯·æ±‚å‚æ•°æˆ–ä¸šåŠ¡å‰ç½®æ¡ä»¶ä¸æ»¡è¶³ |
| 401 | `auth_required` | æœªè®¤è¯æˆ–è®¤è¯å¤±æ•ˆ |
| 403 | `forbidden` | é‰´æƒé€šè¿‡ä½†æ— æƒé™ |
| 404 | `resource_not_found` | èµ„æºä¸å­˜åœ?|
| 409 | `resource_conflict` | èµ„æºå†²çª |
| 422 | `validation_error` | è¯·æ±‚ä½“éªŒè¯å¤±è´?|
| 500 | `internal_error` | æœåŠ¡å†…éƒ¨å¼‚å¸¸ |
| 503 | `upstream_unavailable` | ä¾èµ–æœåŠ¡ä¸å¯ç”?|

### 7.4 OpenAPI ç¤ºä¾‹è¦†ç›–ï¼ˆå½“å‰ï¼‰

æœ¬è½®å·²è¡¥å……å“åº”ç¤ºä¾‹çš„æŽ¥å£ï¼?- `POST /auth/login`
- `GET /auth/me`
- `POST /chat/query`
- `POST /chat/messages/{message_id}/feedback`
- `POST /courses/{course_id}/files/upload`
- `GET /courses/{course_id}/kb/status`

å…¶ä½™æŽ¥å£å°†æŒ‰ S0 å‰©ä½™ä»»åŠ¡ç»§ç»­è¡¥é½ã€?
## 8. 2026-04-17 ¹ÜÀí¶ËRAGÐÔÄÜ½Ó¿Ú£¨ÒÑÊµÏÖ£©

- ÐÂÔö£ºGET /admin/rag-performance
- ²ÎÊý£º
  - days£¨1-90£¬Ä¬ÈÏ7£©
  - class_id£¨¿ÉÑ¡£©
- ·µ»ØºËÐÄ×Ö¶Î£º
  - 	otals.queries/success/fallback/main_chain_success
  - ates.success_rate/fallback_rate/main_chain_success_rate
  - latency_ms.avg/p50/p95/max
  - quality.avg_confidence/avg_source_count
  - distributions.query_mode/engine/fallback_reason

¸Ã½Ó¿ÚÓÃÓÚ¹ÜÀí¶Ë¹Û²â RAG Ö÷Á´ÉúÐ§³Ì¶ÈÓë»ØÍË½¡¿µ¶È£¬×÷ÎªºóÐøÊµÑéÆÀ²âºÍÄ£ÐÍµ÷ÓÅÒÀ¾Ý¡£

## 9. 2026-04-17 ¹ÜÀí¶ËÊµÑé½á¹û½Ó¿Ú£¨ÒÑÊµÏÖ£©

- ÐÂÔö£ºGET /admin/experiment-results
- ²ÎÊý£º
  - days£¨1-90£¬Ä¬ÈÏ7£©
  - class_id£¨¿ÉÑ¡£©
- ·µ»Ø£º
  - summary£¨query_total/main_chain_success_rate/fallback_rate/avg_confidence/p95_latency_ms£©
  - model_snapshot£¨llm_provider/llm_model/rag_engine£©
  - ag_performance£¨ÍêÕû¾ÛºÏÃ÷Ï¸£©

¸Ã½Ó¿ÚÓÃÓÚ¿ÆÑÐÊµÑé½×¶ÎµÄÖÜÆÚÐÔ½á¹û¶ÔÕÕÓë¹éµµ¡£

## 10. 2026-04-17 Ë÷ÒýÈÎÎñ¹ÜÀí½Ó¿Ú£¨S2 µÚÒ»½×¶Î£©

ÐÂÔö½Ó¿Ú£º
- `GET /courses/{course_id}/kb/tasks`
  - ²ÎÊý£º`class_id?`¡¢`status?`¡¢`page`¡¢`page_size`
  - ·µ»Ø£º¿Î³ÌÏÂÎÄ¼þ½âÎöÈÎÎñÁÐ±í£¨º¬ÖØÊÔÓë´íÎó·ÖÀà×Ö¶Î£©
- `POST /courses/{course_id}/files/{file_id}/kb/retry`
  - ²ÎÊý£º`force`£¨Ä¬ÈÏ `true`£©
  - ·µ»Ø£ºÖØÊÔ¶¯×÷½á¹ûÓë×îÐÂÈÎÎñ¿ìÕÕ
- `GET /admin/index-tasks`
  - ²ÎÊý£º`course_id?`¡¢`class_id?`¡¢`status?`¡¢`page`¡¢`page_size`
  - ·µ»Ø£ºÈ«¾ÖË÷ÒýÈÎÎñ¼à¿ØÁÐ±í

ÉÏ´«ÃÝµÈ²¹³ä£º
- `POST /courses/{course_id}/files/upload` ÔÚÏìÓ¦ÖÐÐÂÔö£º
  - `deduplicated`£¨ÊÇ·ñ¸´ÓÃÒÑÓÐ²ÄÁÏ£©
  - `action`£¨Èç `indexed/reindexed/reuse_existing/failed/already_processing`£©

½âÎöÈÎÎñ·µ»Ø²¹³ä£º
- `attempt_count`
- `max_attempts`
- `retry_available`
- `last_error_category`

## 11. 2026-04-17 Ë÷ÒýÒì²½Èë¶ÓÄÜÁ¦£¨S2 µÚ¶þ½×¶Î£©

ÐÂÔö/À©Õ¹£º
- `POST /courses/{course_id}/files/upload`
  - ÐÂÔö query ²ÎÊý£º`async_index`£¨Ä¬ÈÏ `false`£©
  - `true` Ê±£º½öÈë¶ÓË÷ÒýÈÎÎñ²¢Á¢¼´·µ»Ø£¬²»ÔÚÇëÇóÄÚÖ´ÐÐË÷Òý
  - ·µ»ØÐÂÔö£º`queue_task_id`
- `POST /courses/{course_id}/files/{file_id}/kb/retry`
  - ÐÂÔö query ²ÎÊý£º`async_retry`£¨Ä¬ÈÏ `false`£©
  - `true` Ê±£º½öÈë¶ÓÖØÊÔÈÎÎñ²¢Á¢¼´·µ»Ø
  - ·µ»ØÐÂÔö£º`queue_task_id`

ÈÎÎñÏêÇéÐÂÔö×Ö¶Î£º
- `queue_task_id`
- `queue_status`

ËµÃ÷£º
- µ±Ç°ÒÑÊµÏÖ¡°Èë¶ÓÓëÈÎÎñ¿É²é¡±£»Éú²ú½¨Òé½áºÏ Celery worker Óë broker ÔËÐÐ¡£
- ÔÚÎ´°²×° Celery µÄ¿ª·¢»·¾³ÏÂ£¬ÏµÍ³±£Áô¼æÈÝ·µ»Ø£¬²»×è¶ÏÖ÷Á÷³Ì¡£

## 12. 2026-04-17 Ë÷Òý¶ÓÁÐ×´Ì¬²éÑ¯£¨S2 µÚÈý½×¶Î-1£©

ÐÂÔö½Ó¿Ú£º
- `GET /admin/index-queue/{queue_task_id}`

·µ»Ø£º
- `queue_task_id`
- `queue_backend`£¨celery/dummy£©
- `queue_status`
- `queue_result`£¨Èôºó¶ËÖ§³Ö²¢ÒÑÍê³É£©
- `parse_task`£¨¹ØÁªµÄË÷ÒýÈÎÎñ¿ìÕÕ£©

ËµÃ÷£º
- ¸Ã½Ó¿ÚÓÃÓÚÅÅ²é¡°ÒÑÈë¶ÓÈÎÎñ¡±Ö´ÐÐ×´Ì¬Óë¹ØÁªË÷ÒýÈÎÎñÊÇ·ñÍê³É¡£

## 13. 2026-04-17 Index Batch Retry + Queue Metrics (S2 Stage 3-2)

New endpoints:
- `POST /admin/index-tasks/retry-failed`
  - query: `course_id`, `class_id`, `limit`, `force`, `ignore_cooldown`
  - returns: `candidate_total`, `processed_count`, `effective_limit`, `queued_count`, `skipped_count`, `queued[]`, `skipped[]`
- `GET /admin/index-queue-metrics`
  - query: `course_id`, `class_id`
  - returns: `totals`, `queue`, `retry`, `latency_ms`

Task fields added in parse-task payloads:
- `auto_retry_round`
- `next_retry_after`
- `cooldown_remaining_seconds`

## 14. 2026-04-17 Failure Limit Alerting (S2 Closure)

New capability:
- When a parse/index task reaches retry limit (`max_attempts`) or auto-retry rounds are exhausted, backend emits admin alerts through `Notification`.

Alert payload (`Notification.extra_data`):
- `alert_kind`: `kb_index_failure_limit`
- `reason`: `max_attempts_reached` or `auto_retry_exhausted`
- `task_id`, `course_id`, `class_id`, `material_id`, `material_name`
- `attempt_count`, `max_attempts`, `last_error_category`
- `queue_task_id`, `queue_status`, `triggered_at`

Dedup strategy:
- Same `reason + attempt_count` for one parse task is emitted once to avoid alert spam.

Parse-task fields expanded:
- `alert_count`
- `last_alert_reason`
- `last_alert_at`

## 15. 2026-04-17 Content Items Schema v1 (S3 Stage 1)

Enhancement:
- `GET /courses/{course_id}/files/{file_id}/analysis` now returns `content_items_schema`.
- Normalized schema is `v1`.

`content_items` v1 fields:
- `item_id`
- `modality`
- `text`
- `source_name`
- `source_type`
- `page`
- `score`
- `meta`

Notes:
- Backend normalizes parser outputs into this structure after successful ingest.
- This is the base contract for future multimodal retrieval, graph ingestion, and reranking.

## 16. 2026-04-17 Multimodal Field Mapping for content_items v1 (S3 Stage 2)

Enhancement:
- Backend now maps multimodal parser payloads into stable `content_items v1` keys with modality alias normalization.

New normalized keys (in addition to previous base keys):
- `raw_type`
- `bbox`
- `layout_type`
- `doc_id`
- `chunk_id`
- `table_html`
- `table_markdown`
- `formula_latex`
- `image_path`
- `ocr_text`
- `timestamp_start`
- `timestamp_end`

Modality aliases:
- `equation/math/latex` -> `formula`
- `figure/diagram/chart/photo/screenshot` -> `image`
- `dataframe/csv/spreadsheet` -> `table`

Notes:
- Unknown modality values are safely downgraded to `text`.
- Bounding box supports both list and dict formats (`x1/y1/x2/y2` or `left/top/width/height`).

## 17. 2026-04-17 RAG-Anything Processing Quality Metadata (S3 Stage 3)

Enhancement:
- `raganything_adapter.ingest_material` now computes and stores processing quality metadata.

Stored fields:
- `extra_data.raganything_quality`
  - `quality_level` (`complete/partial/text_only/multimodal_only/failed`)
  - `text_processed`
  - `multimodal_processed`
  - `fully_processed`
  - `warnings[]`
  - `raw_status_keys[]`

Analysis API enhancement:
- `GET /courses/{course_id}/files/{file_id}/analysis` now includes:
  - `raganything_status`
  - `raganything_quality`

Purpose:
- Enables quality-aware filtering and experiment slicing for multimodal ingestion quality.

## 18. 2026-04-17 Knowledge Graph Confidence & Provenance Fields (S3 Stage 4)

Enhancement:
- Knowledge graph nodes/edges now carry confidence and provenance metadata.

Node (`/courses/{course_id}/graph -> nodes[]`) new fields:
- `confidence`
- `source_material_id`
- `source_span`
- `provenance`

Edge (`/courses/{course_id}/graph -> edges[]`) new fields:
- `confidence`
- `source_span`
- `provenance`

Ingest behavior:
- Entity/relation confidence is updated incrementally on repeated ingestion.
- Provenance tracks source material ids and occurrence timestamps/counts.

Schema compatibility:
- Local SQLite bootstrap now performs additive runtime upgrades for required graph columns.

## 19. 2026-04-17 Multimodal Regression Fixture Suite (S3 Closure)

Fixture set:
- `backend/tests/fixtures/multimodal/fixture_manifest.json`
- `backend/tests/fixtures/multimodal/fixture_notes.txt`
- `backend/tests/fixtures/multimodal/fixture_table_formula.md`
- image sample stored as base64 in manifest (`fixture_diagram.png`)

Regression test:
- `backend/tests/test_multimodal_regression_e2e.py`

Coverage:
- upload -> analysis -> graph
- validates `content_items_schema=v1`
- validates multimodal modality coverage (`text/table/formula/image`)
- validates graph confidence/provenance/source-span visibility

Parser behavior update:
- simple parser now emits table/formula/image content items when detectable.

## 20. 2026-04-17 Retrieval Strategy Switch + Reranker Abstraction (S4 Stage 1)

New config options:
- `RAG_RETRIEVAL_STRATEGY` (`lexical|hybrid|graph`)
- `RAG_RETRIEVAL_CANDIDATE_K`
- `RAG_ANSWER_TOP_K`
- `RAG_QUERY_REWRITE_ENABLED`
- `RERANKER_PROVIDER` (`mock|none`)
- `RERANKER_MODEL`

Runtime behavior:
- Added retrieval-strategy-aware candidate scoring in RAG query fallback path.
- Added pluggable reranker abstraction (`app.integrations.reranker`).
- Current built-in providers:
  - `mock` reranker (deterministic heuristic rerank)
  - `none` reranker (no-op pass-through)

Observability fields added (rag query event `extra_data`):
- `retrieval_strategy`
- `reranker_provider`
- `reranker_model`
- `candidate_count`
- `selected_count`
- `graph_term_count`
- `query_rewrite_enabled`

Admin performance aggregations now include distributions:
- `retrieval_strategy`
- `reranker`
- `query_rewrite`

## 21. 2026-04-17 Query Rewrite + Multi-Query Retrieval Merge (S4 Stage 2)

New config options:
- RAG_QUERY_REWRITE_MODE (
one|simple|compact|keywords)
- RAG_QUERY_REWRITE_MAX_VARIANTS

Runtime behavior:
- Added shared query rewrite utility:
  - ackend/app/integrations/rag/query_rewrite.py
- RAGAnythingAdapter now performs multi-query local retrieval merge for fallback:
  - generate query variants from original question
  - retrieve per-variant candidates
  - merge duplicate chunks and track query-hit coverage
- SimpleRAGEngine now supports the same query-variant retrieval logic.

New retrieval scoring signals (candidate-level):
- matched_query_count
- query_coverage
- query_coverage_boost

Observability fields added (rag query event extra_data):
- query_rewrite_mode
- query_variant_count

Admin performance aggregations now include distributions:
- query_rewrite_mode
- query_variant_bucket (|1|2|3|4+|unknown)
## 22. 2026-04-17 S4 Stage 2 Contract Addendum (Encoding-safe copy)

Config additions:
- RAG_QUERY_REWRITE_MODE: none | simple | compact | keywords
- RAG_QUERY_REWRITE_MAX_VARIANTS

Event extra_data additions:
- query_rewrite_mode
- query_variant_count

Admin distribution additions:
- query_rewrite_mode
- query_variant_bucket
## 23. 2026-04-17 External Reranker Providers (S4 Stage 3)

New config options:
- RERANKER_PROVIDER: mock | none | api | local
- RERANKER_API_BASE
- RERANKER_API_KEY
- RERANKER_API_PATH
- RERANKER_API_TIMEOUT_SECONDS
- RERANKER_LOCAL_MODEL

Runtime behavior:
- Added API reranker provider with robust response parsing and fallback to base-score ranking on remote errors.
- Added local reranker provider:
  - optional CrossEncoder runtime loading when dependency and model are available
  - deterministic heuristic fallback when model runtime is unavailable
- Reranker factory now supports provider cache reset and explicit provider selection logic.

Stability behavior:
- api provider without RERANKER_API_BASE falls back to mock provider at selection stage.
- api runtime exceptions do not break query flow; candidates are returned with fallback metadata.
## 24. 2026-04-17 Query Rewrite Ablation Export (S4 Stage 4)

New admin endpoint:
- GET /api/v1/admin/rag-ablation

Query params:
- days: 1..90 (default 7)
- class_id: optional

Response outline:
- window metadata: window_days/window_start/window_end/filters
- totals: query count
- groups:
  - rewrite_enabled: enabled vs disabled
  - rewrite_mode: per mode segment metrics
  - query_variant_bucket: per bucket segment metrics

Segment metrics:
- queries
- success_rate
- fallback_rate
- avg_confidence
- avg_source_count
- latency_ms (avg/p50/p95/max)

Use case:
- Supports direct ablation comparison for rewrite on/off and rewrite mode variants.
## 25. 2026-04-18 Model Routing Layer (S5 Stage 1)

Purpose:
- Add a unified backend routing control plane for generation / embedding / vlm / reranker.
- Support api/local/mock style deployment switching with explicit fallback reasons.

Config additions:
- LLM_BACKEND: auto | api | local | mock
- LLM_LOCAL_API_BASE
- EMBEDDING_BACKEND: auto | api | local | mock
- EMBEDDING_LOCAL_API_BASE
- VLM_BACKEND: auto | api | local | mock
- VLM_LOCAL_API_BASE

Model-config persistence additions:
- llm_backend
- llm_local_api_base
- embedding_backend
- embedding_model
- embedding_local_api_base
- vlm_backend
- vlm_model
- vlm_local_api_base
- reranker_provider
- reranker_model
- reranker_local_model

New admin endpoint:
- GET /api/v1/admin/model-routing

Routing snapshot schema (per capability):
- requested_backend
- effective_backend
- provider
- model
- api_base
- api_key_configured
- fallback_reason

Experiment export enhancement:
- GET /api/v1/admin/experiment-results now includes model_routing snapshot.

Metrics event enrichment:
- llm_backend
- embedding_backend
- vlm_backend
- reranker_backend
## 26. 2026-04-18 Runtime Routing Parity (S5 Stage 2)

Enhancements:
- Runtime now reads persisted admin model-config values to build effective routing snapshot.
- Chat query path uses persisted `rag_engine` to select runtime RAG engine.
- RAGAnything adapter now uses routing snapshot during runtime model invocation.

RAGAnything runtime parity details:
- generation/embedding/vlm backend decisions are bound into:
  - llm function setup
  - embedding function setup
  - vision function setup
  - fallback answer generation path
- Adapter instance cache now includes routing signature; route changes can trigger instance refresh.

Observability parity details:
- RAG query event backend fields (`llm_backend/embedding_backend/vlm_backend/reranker_backend`) now reflect persisted routing config path.

New/updated tests:
- backend/tests/test_chat_engine_selection.py
- backend/tests/test_rag_engine_factory.py
- backend/tests/test_raganything_adapter_query.py (routing-aware fallback case)
## 27. 2026-04-18 Personalization Routing Slice Context (S5 Stage 3)

Student report enhancement:
- Weekly/monthly student reports now include routing slice context for experiment segmentation.

Added fields in report payload:
- highlights.recommendation_context:
  - routing_slice_key
  - llm_backend
  - embedding_backend
  - vlm_backend
  - reranker_backend
- experiment_context:
  - routing_slice_key
  - model_routing (full routing snapshot)

Purpose:
- Allows recommendation/personalization outcomes to be sliced by runtime model-routing strategy during experiments.

## 28. 2026-04-18 Personalization Routing Comparison View (S5 Stage 4)

New admin endpoint:
- GET /api/v1/admin/personalization-routing-metrics

Query params:
- days: 1..180 (default 30)
- class_id: optional
- top_n: 1..50 (default 12)

Response outline:
- window metadata: window_days/window_start/window_end/filters
- summary:
  - total_queries
  - total_slices
  - total_users
  - best_confidence_slice
  - lowest_fallback_slice
- slices[] (sorted by queries desc, top_n applied):
  - routing_slice_key
  - llm_backend / embedding_backend / vlm_backend / reranker_backend
  - queries / users
  - success_rate / fallback_rate
  - avg_confidence / avg_source_count / avg_latency_ms
  - avg_activity_score / avg_task_completion_rate / avg_dislike_count
  - learning_events_per_user

Purpose:
- Provide admin-side comparative analytics for personalization quality across model-routing slices.
- Support experiment decisions by connecting routing strategy and learner behavior outcomes.


