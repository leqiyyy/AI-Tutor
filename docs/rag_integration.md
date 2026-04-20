# RAG-Anything 集成说明（后端先行实施版�?
更新时间�?026-04-17

---

## 1. 目标

将当前“可运行的简�?RAG”升级为“可科研评估�?RAG-Anything 主链”，并保留稳�?fallback�?
---

## 2. 当前状�?
已具备：

- `RAG_ENGINE=raganything` 切换入口
- `RAGAnythingAdapter` 索引能力
- `SimpleRAGEngine` fallback
- 基础 citation、置信度、审核回流机�?
不足�?
- 查询主链仍有较多本地词匹配逻辑
- `RAGANYTHING_QUERY_MODE` 尚未真正参与查询
- 多模态结构化解析链路不完�?
---

## 3. 集成架构

### 3.1 组件分层

1. Parser Provider：文档解析（PDF/PPT/图片/音视频）  
2. Embedding Provider：向量化  
3. Retrieval Layer：召回与过滤  
4. Reranker Provider：重排序  
5. LLM/VLM Provider：回答生成与多模态理�? 
6. Citation Builder：证据溯源输�? 

### 3.2 引擎选择策略

- 主路径：`RAGAnythingAdapter`
- 兜底：`SimpleRAGEngine`
- 触发兜底条件：依赖不可用、主链异常、超�?
---

## 4. 实施步骤

### Step 1：查询主链替�?
- `RAGAnythingAdapter.query` 优先调用�?  - `aquery`
  - `aquery_with_multimodal`
- �?query mode 参数接入配置并生效：
  - `local/global/hybrid/mix`

效果�?
- 检索链路与 RAG-Anything 原生能力对齐

### Step 2：证据输出统一

- 标准�?citation 字段�?  - `name/page/type/score/chunk_id/doc_id`
- 回答、citation、confidence 一并落�?
效果�?
- 回答可追溯，可用于后续评�?
### Step 3：审核回流到主检�?
- 审核补答除写 DB 外，同步写入 RAG 可检索索�?- 记录回流状态：`pending/synced/failed`

效果�?
- 用户反馈真正影响后续问答质量

### Step 4：多模态链路增�?
- PDF：文�?+ OCR + 表格 + 版面�?- 图片：OCR + 描述
- 音视频：转录 + 关键�?+ 时间�?- PPT：幻灯片结构�?
效果�?
- 图文/音视频课程材料均可检索溯�?
---

## 5. 关键配置�?
```env
RAG_ENGINE=raganything
RAGANYTHING_QUERY_MODE=mix
RAGANYTHING_PARSER=mineru
RAGANYTHING_PARSE_METHOD=auto
RAGANYTHING_MAX_CONCURRENT_FILES=1

LLM_MODEL=...
LLM_API_BASE=...
LLM_API_KEY=...

EMBEDDING_MODEL=...
EMBEDDING_API_BASE=...
EMBEDDING_API_KEY=...
EMBEDDING_DIM=...

VLM_MODEL=...
VLM_API_BASE=...
VLM_API_KEY=...
```

---

## 6. 评测指标建议

检索层�?
- Recall@5
- nDCG@10
- MRR

生成层：

- 引用可追溯率
- 幻觉�?- 平均响应时间

反馈层：

- 点踩�?- 转人工率
- 审核后命中提升率

---

## 7. 验证清单

- 上传文本/PDF/图像后可完成索引
- 问答可返�?citation 且字段完�?- query mode 切换后日志有差异
- 主链异常�?fallback 可用
- 审核补答后同类问题回答质量有提升
## 2026-04-17 增量实现（S1 第一阶段�?
### 已实�?
1. 查询主链优先
- `RAGAnythingAdapter.query` 现在优先调用 RAG-Anything 实例查询方法，调用顺序：
  - 有图附件：`aquery_with_multimodal`
  - 通用：`aquery`
  - 兼容：`query`

2. Query mode 贯�?- `RAGANYTHING_QUERY_MODE` 已传递到主链调用，自动兼�?`mode` / `query_mode` 参数名�?
3. 输出标准�?- 主链返回值支�?`str` / `dict` / `list` / object 多种格式，统一归一为：
  - `answer`
  - `sources[{name,page,type,score,chunk_id}]`
  - `confidence`

4. 异常回退
- 当出现以下情况，自动切回本地检索回退链路�?  - RAG-Anything 实例初始化失�?  - 主链查询报错
  - 主链返回空答�?
5. 测试覆盖
- 新增 `backend/tests/test_raganything_adapter_query.py`，覆盖：
  - query_mode 传�?  - 图像附件优先走多模态入�?  - 主链异常回退

### 下一�?
1. 增加可观测指标：
- 主链命中率、回退率、回退原因分布、query_mode 分布�?
2. 证据增强�?- 在主链成功时补充更完�?citation 字段映射（doc_id/source_span/provenance）�?
3. 审核回流增强�?- `add_qa_pair` 回灌后增加可追踪字段，确保人工修正可在主链中被定位与复用�?

### 2026-04-17 ����ʵ�֣�S1 �ڶ��׶Σ��ɹ۲⣩

1. �¼��ɼ�
- ���� ag_query_events��ÿ���ʴ��¼��
  - engine/query_mode/query_method
  - used_fallback/fallback_reason
  - latency_ms/confidence/source_count

2. ���������·���ϱ�
- RAGAnythingAdapter.query �����ṹ�� meta����ȷ�������������ԭ��
- chat_service ͳһ���� meta ����⣬�쳣·��Ҳ��֤�м�¼��

3. �����˾ۺ�
- ���� GET /api/v1/admin/rag-performance��
  - �����ɹ��ʡ�fallback��
  - query_mode/engine/fallback_reason �ֲ�
  - ʱ�ӷ�λ��������ֵ

˵������ǰָ���ѿ�֧�ֽ׶��Կ���ʵ��Աȣ����������� experiment-results �����ӿ����ϸ���� citation �����ֶΡ�

### 2026-04-17 ����ʵ�֣�S2 �ڶ��׶Σ��������񻯣�

1. ��������ִ��
- ���� `kb.index_parse_task` worker ���񣬿ɰ� `parse_task_id` ��ִ̨��������
- `kb_service` �������׼����ִ�к������γɡ�����ִ�С��߽硣

2. �첽��ӽӿ�
- �ϴ�֧�� `async_index=true`������֧�� `async_retry=true`��
- ǰ��/���÷������õ� `parse_task_id + queue_task_id`������ѯ����״̬��

3. �ɹ۲��ֶ���ǿ
- ���񷵻����� `queue_task_id/queue_status`���� `attempt_count/retry_available` ������

˵������һ����ɺ�������·�Ѿ߱���ͬ������ + �첽��ӡ�˫ģʽ�����ں�������ѹ�������ʵ�顣

### 2026-04-17 ����ʵ�֣�S2 �����׶�-1�����пɹ۲⣩

1. ����̬��ѯ
- ���� `GET /api/v1/admin/index-queue/{queue_task_id}`�����ڲ�ѯ�������ִ��̬��

2. �����������
- ��ѯ����ɻ��ݵ� `parse_task` ���գ����ڶ�λ���������ύ������δ��ɡ������⡣

˵����������·��ǰ�Ѿ߱�����ӡ������б����������顢����̬��ѯ����������������

### 2026-04-17 Increment (S2 Stage 3-2: Retry/Cooldown/Metrics)

1. Admin batch retry for failed index tasks
- Added `POST /api/v1/admin/index-tasks/retry-failed`.
- Supports filtering by `course_id/class_id`, limit control, cooldown-aware retry, and optional force override.

2. Cooldown and auto-retry strategy
- Added cooldown gate based on latest failed attempt timestamp.
- Added auto-retry scheduling path in `process_parse_task_by_id` when task remains failed.
- Auto-retry metadata persisted in parse-task ingest meta (`auto_retry_round`, `next_retry_after`).

3. Queue metrics API
- Added `GET /api/v1/admin/index-queue-metrics` for queue depth, retry success rate, and latency summaries.
- Latency is derived from parse-task ingest history events (`queue_submitted`, `attempt_start`, `attempt_done`).

4. Validation
- Added/expanded tests in `backend/tests/test_kb_index_task_management.py`.
- Full backend test suite passed (`22 passed`).

### 2026-04-17 Increment (S2 Closure: Failure Limit Alerting)

1. Alerting output finalized
- Added failure limit alert output via `Notification` for admin users.
- Trigger conditions:
  - max attempts reached in parse/index retry loop
  - auto-retry round exhausted

2. Dedup guard
- Added per-task dedup on `(reason, attempt_count)` to avoid repeated alerts for the same failure state.

3. Query visibility
- Parse-task summary/analysis now includes:
  - `alert_count`
  - `last_alert_reason`
  - `last_alert_at`

4. Validation
- Added end-to-end test to verify:
  - alert is emitted to admin
  - repeated batch retry does not duplicate the same alert

### 2026-04-17 Increment (S3 Stage 1: content_items schema normalization)

1. Unified content item schema
- Added `content_items_schema=v1` and normalized `content_items` fields after ingest success.
- Target fields: `item_id/modality/text/source_name/source_type/page/score/meta`.

2. API-level visibility
- `file analysis` payload now includes `content_items_schema` for downstream consumers.

3. Validation
- Added test to verify schema is `v1` and normalized fields are present.

### 2026-04-17 Increment (S3 Stage 2: multimodal field mapping)

1. Extended v1 normalization
- `content_items v1` now includes multimodal-specific fields for table/formula/image/layout/timestamp contexts.

2. Alias & bbox normalization
- Added modality alias mapping and fallback strategy.
- Added bbox normalization from list or dict formats.

3. Validation
- Added unit-style mapping test for table/formula/image payloads to ensure schema stability.

### 2026-04-17 Increment (S3 Stage 3: ingestion quality labels)

1. Quality labels at ingest time
- Added RAG-Anything ingestion quality classification and warnings.
- Quality levels: `complete/partial/text_only/multimodal_only/failed`.

2. Surface to analysis API
- `file analysis` payload now carries `raganything_status` and `raganything_quality` for downstream diagnostics.

3. Validation
- Added tests for quality label classification behavior.

### 2026-04-17 Increment (S3 Stage 4: graph confidence/provenance)

1. Graph model enhancement
- Extended entity/relation model with confidence and provenance/source-span metadata.

2. Incremental update strategy
- Ingest now merges provenance and source anchors instead of overwrite.
- Repeated ingestion updates confidence and occurrence statistics.

3. Graph API expansion
- `/courses/{course_id}/graph` now exposes confidence/provenance fields for nodes and edges.

4. Validation
- Added regression test for incremental ingest to verify provenance includes multiple source material ids.

### 2026-04-17 Increment (S3 Closure: multimodal regression fixtures)

1. Deterministic fixture suite
- Added fixed multimodal fixtures (text + markdown table/formula + image base64 sample).

2. End-to-end regression test
- Added `test_multimodal_regression_e2e.py` covering `upload -> analysis -> graph`.
- Checks modality coverage and graph provenance traceability against uploaded fixture materials.

3. Parser support for fixture coverage
- Simple parser now emits table/formula/image content-items when input signal is present.

4. Outcome
- This creates a reusable baseline for future model/parser/reranker changes.

### 2026-04-17 Increment (S4 Stage 1: retrieval strategy + reranker abstraction)

1. Strategy switches
- Added retrieval strategy switch: lexical / hybrid / graph.
- Candidate and answer top-k are now configurable.

2. Reranker abstraction
- Added modular reranker layer with `mock` and `none` providers.
- Fallback answer path now runs retrieval candidates through reranker before final context selection.

3. Metrics enrichment
- Added retrieval/reranker selection metadata into per-query observability events.
- Admin RAG performance endpoint now aggregates retrieval strategy and reranker distributions.

4. Test coverage
- Added reranker unit test and updated adapter/metrics tests for new metadata.

### 2026-04-17 Increment (S4 Stage 2: query rewrite + multi-query merge)

1. Query rewrite utility
- Added ackend/app/integrations/rag/query_rewrite.py.
- Supports rewrite modes: 
one/simple/compact/keywords with configurable variant cap.

2. Multi-query retrieval merge
- RAGAnythingAdapter fallback path now merges retrieval results from query variants.
- Dedup by chunk identity and track matched_queries/query_hits.

3. Strategy scoring enrichment
- Retrieval candidates now include:
  - matched_query_count
  - query_coverage
  - query_coverage_boost

4. Observability enrichment
- Query event extra_data now includes:
  - query_rewrite_mode
  - query_variant_count
- Admin rag-performance now aggregates:
  - query_rewrite_mode
  - query_variant_bucket

5. Validation
- Added tests:
  - ackend/tests/test_query_rewrite.py
  - updated ackend/tests/test_raganything_adapter_query.py
  - updated ackend/tests/test_rag_metrics_admin.py
- Full backend suite passed (33 passed).
### 2026-04-17 Increment (S4 Stage 2 Addendum)

- Added shared query rewrite utility and enabled multi-query candidate merge in retrieval paths.
- Added query-level metadata: query_rewrite_mode and query_variant_count.
- Added admin metric buckets: query_rewrite_mode and query_variant_bucket.
- Validation status: backend tests passed (33 passed).
### 2026-04-17 Increment (S4 Stage 3: external reranker providers)

1. Provider extension
- Added reranker providers: api and local.
- Provider matrix is now: mock / none / api / local.

2. API reranker
- New module: backend/app/integrations/reranker/api_reranker.py
- Supports multiple response formats (scores/results/data) and index-aware parsing.
- On remote errors, falls back to base-score sorting without interrupting answer generation.

3. Local reranker
- New module: backend/app/integrations/reranker/local_reranker.py
- Tries local CrossEncoder model when available.
- Falls back to deterministic heuristic scoring when dependency/model is unavailable.

4. Factory and cache
- Reranker factory now supports explicit provider routing and cache reset helper.

5. Validation
- Added tests:
  - backend/tests/test_reranker_providers.py
- Full backend tests passed: 38 passed.
### 2026-04-17 Increment (S4 Stage 4: rewrite ablation export)

1. Ablation API
- Added GET /api/v1/admin/rag-ablation.
- Provides grouped comparison for:
  - rewrite enabled vs disabled
  - rewrite modes
  - query variant buckets

2. Metrics schema
- Each segment includes success/fallback rates, confidence, source count, and latency summary.
- Works on the same event stream used by rag-performance.

3. Validation
- Updated tests:
  - backend/tests/test_admin_smoke.py
  - backend/tests/test_rag_metrics_admin.py
- Full backend tests passed: 38 passed.
### 2026-04-18 Increment (S5 Stage 1: model routing layer)

1. Routing service
- Added backend/app/services/model_routing_service.py.
- Produces routing snapshot for generation/embedding/vlm/reranker with fallback reasons.

2. Admin control plane
- model-config now persists routing-related fields (backend/model/local base/provider).
- Added GET /api/v1/admin/model-routing for real-time route inspection.

3. Runtime observability
- chat query events now include:
  - llm_backend
  - embedding_backend
  - vlm_backend
  - reranker_backend
- rag-performance distributions now aggregate these routing backends.

4. Experiment snapshot
- /admin/experiment-results includes model_routing output for reproducible experiment context.

5. Validation
- Added tests:
  - backend/tests/test_model_routing_service.py
- Updated:
  - backend/tests/test_admin_smoke.py
  - backend/tests/test_rag_metrics_admin.py
- Full backend tests passed: 42 passed.
### 2026-04-18 Increment (S5 Stage 2: runtime routing parity)

1. Persisted config to runtime path
- Runtime routing now reads persisted admin model-config values.
- chat_service selects RAG engine by persisted rag_engine value.

2. RAGAnything route binding
- Adapter binds generation/embedding/vlm route snapshot into model function constructors.
- Fallback answer generation respects generation backend route.
- Adapter instance cache now tracks route signature for consistency.

3. Reliability and fallback
- When generation backend is mock in fallback path, adapter returns rule-based grounded summary instead of attempting unavailable API call.

4. Validation
- Added tests:
  - backend/tests/test_chat_engine_selection.py
  - backend/tests/test_rag_engine_factory.py
- Updated routing-aware fallback test in:
  - backend/tests/test_raganything_adapter_query.py
- Full backend tests passed: 45 passed.
### 2026-04-18 Increment (S5 Stage 3: personalization linkage with routing slices)

1. Student report linkage
- build_student_report now embeds routing slice metadata.
- recommended focus output is now accompanied by recommendation_context and experiment_context.

2. Experiment slicing support
- Reports now carry routing_slice_key + full model_routing snapshot for downstream analysis.

3. Validation
- Updated test:
  - backend/tests/test_notifications_and_reports.py
- Full backend tests passed: 45 passed.

### 2026-04-18 Increment (S5 Stage 4: admin personalization routing comparison)

1. Admin comparative view
- Added GET /api/v1/admin/personalization-routing-metrics.
- Supports filters: days/class_id/top_n.

2. Routing-slice analytics
- Added analytics aggregation by routing slice key:
  - llm_backend|embedding_backend|vlm_backend|reranker_backend
- Per-slice metrics now include:
  - query quality: success/fallback/confidence/source_count/latency
  - personalization context: activity_score/task_completion_rate/dislike_count
  - learning engagement: learning_events_per_user

3. Experiment interpretation support
- Response summary includes best_confidence_slice and lowest_fallback_slice.
- Enables direct side-by-side routing strategy comparison for personalization studies.

4. Validation
- Updated tests:
  - backend/tests/test_admin_smoke.py
  - backend/tests/test_rag_metrics_admin.py
- Full backend tests passed: 45 passed.



### 2026-04-18 Increment (S6 Stage 1: offline benchmark/export runner)

1. Benchmark/export script
- Added `backend/scripts/run_research_benchmark.py`.
- Runs deterministic backend-only experiment flow and exports:
  - JSON report
  - Markdown report

2. Metrics snapshot integration
- Script aggregates data from:
  - `/admin/rag-performance`
  - `/admin/rag-ablation`
  - `/admin/personalization-routing-metrics`
  - `/admin/experiment-results`

3. Optional multimodal fixture validation
- Added script option `--include-fixtures` using existing multimodal fixtures.
- Enables combined evaluation of retrieval/answer metrics + multimodal parsing consistency.

4. Regression coverage
- Added `backend/tests/test_research_benchmark_script.py`.
- Verifies report files are generated and include core metric sections.

5. Validation
- Full backend tests passed: 46 passed.

### 2026-04-19 Increment (S6 Stage 2: retrieval scoring + baseline comparison export)

1. Retrieval metric scoring
- Offline benchmark runner now supports qrels-style benchmark spec input.
- Added retrieval metrics:
  - Recall@k
  - nDCG@k
  - MRR
- Added per-question detail export for scored queries.

2. Baseline-vs-current weekly comparison
- Added baseline report comparison mode via `--baseline-report`.
- Added trend output (`improved/regressed/unchanged`) per metric.
- Added comparison artifact export:
  - `benchmark_compare_<run_id>.json`
  - `benchmark_compare_<run_id>.md`

3. Runner interface updates
- Added args:
  - `--benchmark-spec`
  - `--retrieval-k`
  - `--baseline-report`

4. Fixtures and templates
- Added benchmark spec template:
  - `backend/tests/fixtures/benchmark/benchmark_spec_template.json`

5. Validation
- Updated tests:
  - `backend/tests/test_research_benchmark_script.py`
- Full backend tests passed: 47 passed.
