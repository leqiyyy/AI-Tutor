import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace

from app.core.config import settings
from app.core.database import SessionLocal
from app.integrations.rag.raganything_adapter import RAGAnythingAdapter
from app.integrations.reranker import reset_reranker_cache
from app.models.course import Class, Course, Material
from app.models.knowledge import FileParseTask, KBSpace, KnowledgeEntity, KnowledgeRelation


def _build_adapter_with_db_free_mocks(monkeypatch):
    _ = monkeypatch
    return RAGAnythingAdapter()


def _make_workspace_tmp_dir(name: str) -> Path:
    path = Path("backend/runtime_tmp/test_artifacts") / f"{name}_{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def test_raganything_llm_func_prefers_dedicated_extract_route(monkeypatch):
    adapter = _build_adapter_with_db_free_mocks(monkeypatch)
    captured = {}

    monkeypatch.setattr(settings, "EXTRACT_MODEL", "extract-model")
    monkeypatch.setattr(settings, "EXTRACT_API_BASE", "https://extract.example/v1")
    monkeypatch.setattr(settings, "EXTRACT_API_KEY", "extract-key")
    monkeypatch.setattr(settings, "EXTRACT_WIRE_API", "chat_completions")

    async def fake_call_llm_api(**kwargs):
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr(adapter, "_call_llm_api", fake_call_llm_api)
    llm_func = adapter._build_llm_func({
        "generation": {
            "model": "generation-model",
            "api_base": "https://generation.example/v1",
        }
    })

    result = asyncio.run(llm_func("extract entities"))

    assert result == "ok"
    assert captured["model"] == "extract-model"
    assert captured["base_url"] == "https://extract.example/v1"
    assert captured["api_key"] == "extract-key"


def test_raganything_processing_error_is_extracted_from_raw_status():
    adapter = RAGAnythingAdapter()

    error = adapter._extract_processing_error({
        "status": "failed",
        "raw_status": {
            "error_msg": "C[1/1]: chunk-x: AuthenticationError: Error code: 401 - Api key is invalid",
        },
    })

    assert error["category"] == "llm_authentication"
    assert "Api key is invalid" in error["message"]

    timeout_error = adapter._extract_processing_error({
        "raw_status": {
            "error_msg": "C[1/1]: chunk-x: LLM func: Worker execution timeout after 360s",
        },
    })

    assert timeout_error["category"] == "llm_timeout"


def test_raganything_query_passes_query_mode(monkeypatch):
    adapter = _build_adapter_with_db_free_mocks(monkeypatch)

    class FakeRag:
        def __init__(self):
            self.mode = None
            self.query_text = None

        async def aquery(self, query, mode=None):
            self.mode = mode
            self.query_text = query
            return {
                "answer": "RAG main-chain answer",
                "sources": [
                    {
                        "name": "network_notes.pdf",
                        "page": 5,
                        "type": "pdf",
                        "score": 0.88,
                        "chunk_id": "chunk-1",
                    }
                ],
                "confidence": 0.82,
            }

    fake = FakeRag()
    monkeypatch.setattr(adapter, "_get_instance", lambda class_id: fake)

    result = asyncio.run(
        adapter.query(
            question="What is TCP slow start?",
            class_id="class-demo",
            history=[],
            attachments=[],
        )
    )

    assert fake.mode == settings.RAGANYTHING_QUERY_MODE
    assert "TCP slow start" in fake.query_text
    assert result.answer == "RAG main-chain answer"
    assert result.sources[0]["chunk_id"] == "chunk-1"
    assert result.confidence == 0.82
    assert result.meta["retrieval_strategy"] == "main_chain"
    assert result.meta["reranker_provider"] == "main_chain_native"
    assert result.meta["query_rewrite_mode"] in {"disabled", "hybrid", "compact", "keywords"}
    assert result.meta["query_variant_count"] >= 1


def test_raganything_query_uses_mode_for_kwargs_methods(monkeypatch):
    adapter = _build_adapter_with_db_free_mocks(monkeypatch)

    class FakeRag:
        def __init__(self):
            self.kwargs = None

        async def aquery(self, query, mode="mix", **kwargs):
            self.kwargs = {"query": query, "mode": mode, **kwargs}
            return "Strict main-chain answer"

    fake = FakeRag()
    monkeypatch.setattr(adapter, "_get_instance", lambda class_id: fake)

    result = asyncio.run(
        adapter.query(
            question="What is queue delay?",
            class_id="class-demo",
            history=[],
            attachments=[],
        )
    )

    assert result.answer == "Strict main-chain answer"
    assert fake.kwargs["mode"] == settings.RAGANYTHING_QUERY_MODE
    assert "query_mode" not in fake.kwargs


def test_raganything_main_chain_sources_can_be_reranked(monkeypatch):
    reset_reranker_cache()
    monkeypatch.setattr(settings, "RERANKER_PROVIDER", "mock")
    adapter = _build_adapter_with_db_free_mocks(monkeypatch)

    class FakeRag:
        async def aquery(self, query, mode=None):
            return {
                "answer": "Use slow start to grow cwnd until ssthresh.",
                "sources": [
                    {
                        "name": "queueing.md",
                        "page": 1,
                        "score": 0.5,
                        "chunk_id": "queue",
                        "content": "Queue management and packet scheduling.",
                    },
                    {
                        "name": "tcp.md",
                        "page": 2,
                        "score": 0.55,
                        "chunk_id": "tcp",
                        "content": "TCP slow start grows the congestion window each RTT.",
                    },
                ],
                "confidence": 0.7,
            }

    monkeypatch.setattr(adapter, "_get_instance", lambda class_id: FakeRag())

    result = asyncio.run(
        adapter.query(
            question="Explain TCP slow start",
            class_id="class-demo",
            history=[],
            attachments=[],
        )
    )

    assert result.meta["reranker_provider"] == "mock"
    assert result.meta["reranked_main_chain_sources"] is True
    assert result.sources[0]["chunk_id"] == "tcp"
    reset_reranker_cache()


def test_raganything_builds_lightrag_internal_rerank_func(monkeypatch):
    adapter = _build_adapter_with_db_free_mocks(monkeypatch)

    class FakeReranker:
        provider_name = "api"
        model_name = "BAAI/bge-reranker-v2-m3"

        async def rerank(self, *, query, candidates, context=None):
            _ = (query, context)
            return [
                {**candidates[1], "rerank_score": 0.93, "rerank_components": {"remote_score": 0.93}},
                {**candidates[0], "rerank_score": 0.15, "rerank_components": {"remote_score": 0.15}},
            ]

    monkeypatch.setattr(
        "app.integrations.rag.raganything_adapter.get_reranker",
        lambda: FakeReranker(),
    )
    rerank_func = adapter._build_rerank_func({"reranker": {"effective_backend": "api"}})

    result = asyncio.run(
        rerank_func(
            query="Explain slow start",
            documents=["grading policy", "slow start congestion window"],
            top_n=2,
        )
    )

    assert result == [
        {"index": 1, "relevance_score": 0.93},
        {"index": 0, "relevance_score": 0.15},
    ]


def test_raganything_query_includes_attachment_context(monkeypatch):
    adapter = _build_adapter_with_db_free_mocks(monkeypatch)

    class FakeRag:
        def __init__(self):
            self.query_text = None

        async def aquery(self, query, mode=None):
            self.query_text = query
            return {"answer": "ok", "sources": [], "confidence": 0.7}

    fake = FakeRag()
    monkeypatch.setattr(adapter, "_get_instance", lambda class_id: fake)

    result = asyncio.run(
        adapter.query(
            question="Explain this attachment",
            class_id="class-demo",
            history=[],
            attachments=[{"file_type": "txt", "attachment_context": "Attachment: notes.txt\nPreview:\nTCP slow start"}],
        )
    )

    assert "Attachment-derived context" in fake.query_text
    assert "TCP slow start" in fake.query_text
    assert result.answer == "ok"


def test_raganything_query_prefers_multimodal_entry_when_image_present(monkeypatch):
    adapter = _build_adapter_with_db_free_mocks(monkeypatch)

    class FakeRag:
        def __init__(self):
            self.called_method = None

        async def aquery_with_multimodal(self, query, mode=None):
            self.called_method = "aquery_with_multimodal"
            return "Multimodal chain answer"

        async def aquery(self, query, mode=None):  # pragma: no cover - should not be preferred
            self.called_method = "aquery"
            return "Text chain answer"

    fake = FakeRag()
    monkeypatch.setattr(adapter, "_get_instance", lambda class_id: fake)
    monkeypatch.setattr(
        adapter,
        "_describe_image_attachment",
        lambda attachment, question: asyncio.sleep(0, result="A network topology diagram with packet loss"),
    )

    result = asyncio.run(
        adapter.query(
            question="Explain congestion control in this image.",
            class_id="class-demo",
            history=[],
            attachments=[{"file_type": "image", "image_base64": "abcd"}],
        )
    )

    assert fake.called_method == "aquery_with_multimodal"
    assert result.answer == "Multimodal chain answer"


def test_raganything_query_does_not_fallback_when_main_chain_fails(monkeypatch):
    adapter = RAGAnythingAdapter()

    class BrokenRag:
        async def aquery(self, query, mode=None):
            raise RuntimeError("raganything query failed")

    monkeypatch.setattr(adapter, "_get_instance", lambda class_id: BrokenRag())
    monkeypatch.setattr(
        adapter,
        "_load_runtime_routing_snapshot",
        lambda: {
            "generation": {
                "effective_backend": "api",
                "model": "test-model",
                "api_base": "http://localhost:9999/v1",
            },
            "embedding": {"effective_backend": "api", "model": "embed-test", "api_base": "http://localhost:9999/v1"},
            "vlm": {"effective_backend": "mock", "model": "mock-vlm-v1", "api_base": None},
            "reranker": {"effective_backend": "mock", "model": "mock-reranker-v1", "api_base": None},
        },
    )

    result = asyncio.run(
        adapter.query(
            question="How does slow start work?",
            class_id="class-demo",
            history=[],
            attachments=[],
        )
    )

    assert "RAG-Anything main-chain retrieval is currently unavailable" in result.answer
    assert result.sources == []
    assert result.confidence == 0.0
    assert result.meta["used_fallback"] is False
    assert result.meta["fallback_disabled"] is True
    assert result.meta["fallback_reason"] == "query_exception"
    assert result.meta["query_error_detail"] == "raganything query failed"
    assert result.meta["retrieval_strategy"] == "raganything_main_chain"
    assert result.meta["query_rewrite_mode"] in {"disabled", "hybrid", "compact", "keywords"}
    assert result.meta["query_variant_count"] >= 1


def test_raganything_query_initializes_lightrag_before_text_query(monkeypatch):
    adapter = RAGAnythingAdapter()
    calls = {"ensure": 0}

    class FakeRag:
        def __init__(self):
            self.lightrag = None

        async def _ensure_lightrag_initialized(self):
            calls["ensure"] += 1
            self.lightrag = object()
            return {"success": True}

        async def aquery(self, query, mode=None):
            assert self.lightrag is not None
            return {
                "answer": "Initialized main-chain answer",
                "sources": [{"name": "tcp.md", "score": 0.82, "chunk_id": "chunk-1", "content": "slow start"}],
                "confidence": 0.84,
            }

    monkeypatch.setattr(adapter, "_get_instance", lambda class_id: FakeRag())

    result = asyncio.run(
        adapter.query(
            question="Explain TCP slow start",
            class_id="class-demo",
            history=[],
            attachments=[],
        )
    )

    assert calls["ensure"] == 1
    assert result.answer == "Initialized main-chain answer"
    assert result.sources
    assert result.confidence == 0.84


def test_raganything_text_query_disables_vlm_enhancement(monkeypatch):
    adapter = RAGAnythingAdapter()
    captured = {}

    class FakeRag:
        async def aquery(self, query, mode=None, **kwargs):
            captured["query"] = query
            captured["mode"] = mode
            captured["kwargs"] = kwargs
            return {"answer": "ok", "sources": [], "confidence": 0.7}

    raw, method = asyncio.run(
        adapter._invoke_rag_query(
            rag=FakeRag(),
            query_text="Explain TCP slow start",
            query_mode="mix",
            history=[],
            attachments=[],
            prefer_multimodal=False,
            class_id="class-demo",
        )
    )

    assert method == "aquery"
    assert raw["answer"] == "ok"
    assert captured["kwargs"]["vlm_enhanced"] is False


def test_lightrag_reference_query_uses_stable_hybrid_for_mix(monkeypatch):
    adapter = RAGAnythingAdapter()
    calls = []

    lightrag_module = ModuleType("lightrag")

    class FakeQueryParam:
        def __init__(self, **kwargs):
            self.mode = kwargs["mode"]
            self.include_references = kwargs["include_references"]

    class FakeLightRAG:
        async def aquery_llm(self, query, param=None):
            calls.append(param.mode)
            return {
                "llm_response": {"content": f"answer for {query}"},
                "data": {"chunks": [{"content": "stable hybrid source"}]},
            }

    lightrag_module.QueryParam = FakeQueryParam
    monkeypatch.setattr(
        "app.integrations.rag.raganything_adapter.importlib.import_module",
        lambda name: lightrag_module if name == "lightrag" else __import__(name),
    )

    raw, method = asyncio.run(
        adapter._invoke_lightrag_query_with_references(
            rag=SimpleNamespace(lightrag=FakeLightRAG()),
            query_text="Explain teacher reviewed answer",
            query_mode="mix",
            history=[],
            class_id="class-demo",
        )
    )

    assert calls == ["hybrid"]
    assert method == "lightrag_aquery_llm:hybrid"
    assert raw["metadata"]["adapter_requested_mode"] == "mix"
    assert raw["metadata"]["adapter_effective_mode"] == "hybrid"


def test_raganything_processing_quality_labels():
    adapter = RAGAnythingAdapter()

    complete = adapter._build_processing_quality({
        "text_processed": True,
        "multimodal_processed": True,
        "fully_processed": True,
    })
    assert complete["quality_level"] == "complete"
    assert complete["warnings"] == []

    text_only = adapter._build_processing_quality({
        "text_processed": True,
        "multimodal_processed": False,
        "fully_processed": False,
    })
    assert text_only["quality_level"] == "text_only"
    assert "multimodal_not_ready" in text_only["warnings"]

    failed = adapter._build_processing_quality({
        "text_processed": False,
        "multimodal_processed": False,
        "fully_processed": False,
    })
    assert failed["quality_level"] == "failed"
    assert "text_not_ready" in failed["warnings"]


def test_raganything_extracts_official_graph_payload():
    adapter = RAGAnythingAdapter()
    payload = {
        "raganything_status": {
            "knowledge_entities": [
                {"name": "TCP slow start", "entity_type": "concept", "confidence": 0.88},
            ],
            "knowledge_relations": [
                {
                    "source": "TCP slow start",
                    "target": "Congestion window",
                    "relation_type": "uses",
                    "confidence": 0.8,
                }
            ],
        }
    }

    entities = adapter._extract_graph_entities(payload)
    relations = adapter._extract_graph_relations(payload)

    assert entities[0]["name"] == "TCP slow start"
    assert entities[0]["entity_type"] == "concept"
    assert relations[0]["relation_type"] == "uses"


def test_raganything_add_qa_pair_uses_insert_content_list(monkeypatch):
    adapter = RAGAnythingAdapter()
    captured = {}

    class FakeRag:
        async def insert_content_list(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(adapter, "_get_instance", lambda class_id: FakeRag())

    ok = asyncio.run(
        adapter.add_qa_pair(
            "missing-class-for-unit-test",
            "What is TCP slow start?",
            "A teacher verified explanation.",
        )
    )

    assert ok is True
    assert captured["doc_id"].startswith("teacher-review-")
    assert captured["file_path"].startswith("teacher_review_")
    assert captured["content_list"][0]["metadata"]["source"] == "teacher_review"
    assert "Teacher-verified answer" in captured["content_list"][0]["text"]


def test_raganything_get_instance_passes_official_storage_plan(monkeypatch):
    adapter = RAGAnythingAdapter()
    captured = {}
    tmp_path = _make_workspace_tmp_dir("storage_plan")

    monkeypatch.setattr(adapter, "_prepare_environment", lambda: None)
    monkeypatch.setattr(adapter, "_require_model_config", lambda snapshot: None)
    monkeypatch.setattr(
        adapter,
        "_load_runtime_routing_snapshot",
        lambda: {
            "generation": {"effective_backend": "api", "model": "gen-model", "api_base": "https://llm.example/v1"},
            "embedding": {"effective_backend": "api", "model": "embed-model", "api_base": "https://embed.example/v1"},
            "vlm": {"effective_backend": "api", "model": "vlm-model", "api_base": "https://vlm.example/v1"},
            "reranker": {"effective_backend": "none", "model": "", "api_base": ""},
        },
    )
    monkeypatch.setattr(adapter, "_build_embedding_func", lambda snapshot: "embedding-func")
    monkeypatch.setattr(adapter, "_build_rerank_func", lambda snapshot: None)
    monkeypatch.setattr(adapter, "_build_llm_func", lambda snapshot: "llm-func")
    monkeypatch.setattr(adapter, "_build_vision_func", lambda snapshot: "vision-func")
    monkeypatch.setattr(
        "app.integrations.rag.raganything_adapter.build_lightrag_storage_plan",
        lambda class_id: {
            "requested_backend": "qdrant-neo4j",
            "effective_backend": "qdrant-neo4j",
            "workspace": "course_chunks__class-demo",
            "vector_db": {"provider": "qdrant"},
            "graph_db": {"provider": "neo4j"},
            "lightrag_kwargs": {
                "kv_storage": "JsonKVStorage",
                "vector_storage": "QdrantVectorDBStorage",
                "graph_storage": "Neo4JStorage",
                "doc_status_storage": "JsonDocStatusStorage",
                "workspace": "course_chunks__class-demo",
            },
            "env_overrides": {
                "QDRANT_URL": "http://localhost:6333",
                "NEO4J_URI": "bolt://localhost:7687",
            },
        },
    )
    monkeypatch.setattr(settings, "RAGANYTHING_WORKING_DIR", str(tmp_path / "rag_storage"))
    monkeypatch.setattr(settings, "RAGANYTHING_OUTPUT_DIR", str(tmp_path / "rag_output"))
    monkeypatch.setattr(settings, "RAGANYTHING_DEFAULT_LLM_TIMEOUT_SECONDS", 180)
    monkeypatch.setattr(settings, "RAGANYTHING_PARSER", "mineru")
    monkeypatch.setattr(settings, "RAGANYTHING_PARSE_METHOD", "auto")
    monkeypatch.setattr(settings, "RAGANYTHING_MAX_CONCURRENT_FILES", 1)
    monkeypatch.setattr(settings, "EXTRACT_MODEL", "extract-model")
    monkeypatch.setattr(settings, "LLM_MODEL", "fallback-model")

    raganything_module = ModuleType("raganything")
    config_module = ModuleType("raganything.config")

    class FakeConfig:
        def __init__(self, **kwargs):
            captured["config_kwargs"] = kwargs

    class FakeRAGAnything:
        def __init__(self, **kwargs):
            captured["rag_kwargs"] = kwargs

        def check_parser_installation(self):
            return True

    raganything_module.RAGAnything = FakeRAGAnything
    config_module.RAGAnythingConfig = FakeConfig

    real_import_module = __import__("importlib").import_module

    def fake_import_module(name, package=None):
        if name == "raganything":
            return raganything_module
        if name == "raganything.config":
            return config_module
        return real_import_module(name, package)

    monkeypatch.setattr("app.integrations.rag.raganything_adapter.importlib.import_module", fake_import_module)

    instance = adapter._get_instance("class-demo")

    assert isinstance(instance, FakeRAGAnything)
    assert captured["rag_kwargs"]["lightrag_kwargs"]["vector_storage"] == "QdrantVectorDBStorage"
    assert captured["rag_kwargs"]["lightrag_kwargs"]["graph_storage"] == "Neo4JStorage"
    assert captured["rag_kwargs"]["lightrag_kwargs"]["workspace"] == "course_chunks__class-demo"
    assert os.environ["QDRANT_URL"] == "http://localhost:6333"
    assert os.environ["NEO4J_URI"] == "bolt://localhost:7687"


def test_raganything_adapter_restores_kb_compatibility_methods():
    adapter = RAGAnythingAdapter()
    marker = uuid.uuid4().hex[:8]
    node_label = f"rag-node-{marker}"
    related_label = f"rag-related-{marker}"

    with SessionLocal() as db:
        base_class = db.query(Class).first()
        assert base_class is not None

        course = Course(
            name=f"Storage Migration {marker}",
            code=f"STO-{marker}",
            description="isolated rebuild fixture",
            created_by=base_class.teacher_id,
        )
        db.add(course)
        db.flush()

        cls = Class(
            course_id=course.id,
            teacher_id=base_class.teacher_id,
            name=f"Storage Migration Class {marker}",
            semester="2026-Spring",
            invite_code=f"INV{marker[:8]}",
        )
        db.add(cls)
        db.flush()

        kb_space = KBSpace(
            course_id=cls.course_id,
            class_id=cls.id,
            status="ready",
            document_count=1,
            chunk_count=1,
            last_built_at=datetime.now(timezone.utc),
            extra_data={
                "raganything_teacher_review_sync": [{"doc_id": f"teacher-review-{marker}"}],
            },
        )
        db.add(kb_space)
        db.flush()

        material = Material(
            class_id=cls.id,
            uploaded_by=cls.teacher_id,
            title=f"Strict RAG Material {marker}",
            file_name=f"strict_rag_{marker}.txt",
            file_path=f"E:/fake/strict_rag_{marker}.txt",
            file_size=128,
            mime_type="text/plain",
            file_type="txt",
            kb_status="indexed",
            description="adapter compatibility regression fixture",
        )
        db.add(material)
        db.flush()

        task = FileParseTask(
            kb_space_id=kb_space.id,
            course_id=cls.course_id,
            class_id=cls.id,
            material_id=material.id,
            status="completed",
            parser_name="raganything",
            summary="Strict RAG summary",
            extracted_text="Strict RAG extracted text",
            chunks=[{"chunk_id": f"chunk-{marker}", "text": "strict rag chunk text"}],
            extra_data={
                "content_items": [{"item_id": f"ci-{marker}", "modality": "text", "text": "chunk body"}],
                "content_items_schema": "v1",
                "preprocess": {"mode": "direct_document"},
                "raganything_status": {"entrypoint": "insert_file"},
                "raganything_quality": {"quality_level": "complete"},
                "graph_projection": {"entity_count": 2, "relation_count": 1},
                "ingest": {
                    "attempt_count": 2,
                    "max_attempts": 5,
                    "retry_available": True,
                    "queue_task_id": f"queue-{marker}",
                    "queue_status": "completed",
                },
            },
        )
        db.add(task)
        db.flush()

        source = KnowledgeEntity(
            class_id=cls.id,
            name=node_label,
            entity_type="concept",
            description="strict rag node",
            source_material_id=material.id,
            confidence=0.91,
            source_span={"kind": "test_node"},
            provenance={"source_material_ids": [material.id]},
            status="approved",
        )
        target = KnowledgeEntity(
            class_id=cls.id,
            name=related_label,
            entity_type="concept",
            description="strict rag related node",
            source_material_id=material.id,
            confidence=0.87,
            source_span={"kind": "test_node"},
            provenance={"source_material_ids": [material.id]},
            status="approved",
        )
        db.add_all([source, target])
        db.flush()

        relation = KnowledgeRelation(
            class_id=cls.id,
            source_id=source.id,
            target_id=target.id,
            relation_type="related_to",
            weight=1.4,
            confidence=0.79,
            source_span={"kind": "test_edge"},
            provenance={"source_material_ids": [material.id]},
        )
        db.add(relation)
        db.commit()

        course_id = cls.course_id
        task_id = task.id
        material_id = material.id

    task_payload = adapter.get_parse_task(task_id)
    kb_status = adapter.get_kb_status(course_id)
    graph = adapter.get_graph(course_id)
    filtered_graph = adapter.get_graph(course_id, entity_type="concept", min_confidence=0.9, limit=1)

    assert task_payload is not None
    assert task_payload["kind"] == "file_parse"
    assert task_payload["id"] == task_id
    assert task_payload["material_id"] == material_id
    assert task_payload["attempt_count"] == 2
    assert task_payload["queue_task_id"].startswith("queue-")
    assert task_payload["content_items_schema"] == "v1"
    assert task_payload["raganything_quality"]["quality_level"] == "complete"

    assert kb_status["backend"] == "raganything"
    assert kb_status["strict_mode"] is True
    assert kb_status["materials_total"] >= 1
    assert kb_status["materials_indexed"] >= 1
    assert kb_status["parse_tasks"]["completed"] >= 1
    assert kb_status["teacher_review_sync_count"] >= 1
    assert kb_status["storage"]["current_requested_backend"]
    assert kb_status["storage"]["reindex_required"] is False
    assert isinstance(kb_status["storage"]["indexed_backend_distribution"], dict)

    matched_nodes = [node for node in graph["nodes"] if node["label"] == node_label]
    assert matched_nodes
    assert matched_nodes[0]["provenance"]["source_material_ids"] == [material_id]
    matched_edges = [edge for edge in graph["edges"] if edge["source_label"] == node_label]
    assert matched_edges
    assert matched_edges[0]["label"] == "related_to"
    assert matched_edges[0]["provenance"]["source_material_ids"] == [material_id]
    assert graph["summary"]["entity_type_distribution"]["concept"] >= 2
    assert graph["summary"]["relation_type_distribution"]["related_to"] >= 1
    assert graph["summary"]["source_material_count"] >= 1
    assert any(item["material_id"] == material_id for item in graph["materials"])
    assert graph["filters"]["available_class_ids"]
    assert "concept" in graph["filters"]["available_entity_types"]
    assert graph["legend"]["entity_types"]
    assert graph["legend"]["relation_types"]

    assert filtered_graph["stats"]["node_count"] == 1
    assert filtered_graph["stats"]["edge_count"] == 0
    assert filtered_graph["filters"]["entity_type"] == "concept"
    assert filtered_graph["filters"]["min_confidence"] == 0.9
    assert filtered_graph["filters"]["limit"] == 1
    assert filtered_graph["nodes"][0]["label"] == node_label


def test_raganything_rebuild_course_can_target_storage_mismatch_only(monkeypatch):
    import app.integrations.rag.raganything_adapter as adapter_module

    adapter = RAGAnythingAdapter()
    marker = uuid.uuid4().hex[:8]
    recorded = []

    with SessionLocal() as db:
        base_class = db.query(Class).first()
        assert base_class is not None

        course = Course(
            name=f"Storage Migration {marker}",
            code=f"STO-{marker}",
            description="isolated rebuild fixture",
            created_by=base_class.teacher_id,
        )
        db.add(course)
        db.flush()

        cls = Class(
            course_id=course.id,
            teacher_id=base_class.teacher_id,
            name=f"Storage Migration Class {marker}",
            semester="2026-Spring",
            invite_code=f"INV{marker[:8]}",
        )
        db.add(cls)
        db.flush()

        kb_space = KBSpace(
            course_id=cls.course_id,
            class_id=cls.id,
            status="ready",
            document_count=2,
            chunk_count=2,
            last_built_at=datetime.now(timezone.utc),
            extra_data={},
        )
        db.add(kb_space)
        db.flush()

        material_old = Material(
            class_id=cls.id,
            uploaded_by=cls.teacher_id,
            title=f"Old Storage {marker}",
            file_name=f"old_storage_{marker}.txt",
            file_path=f"E:/fake/old_storage_{marker}.txt",
            file_size=128,
            mime_type="text/plain",
            file_type="txt",
            kb_status="indexed",
            description="old storage fixture",
        )
        material_new = Material(
            class_id=cls.id,
            uploaded_by=cls.teacher_id,
            title=f"New Storage {marker}",
            file_name=f"new_storage_{marker}.txt",
            file_path=f"E:/fake/new_storage_{marker}.txt",
            file_size=128,
            mime_type="text/plain",
            file_type="txt",
            kb_status="indexed",
            description="new storage fixture",
        )
        db.add_all([material_old, material_new])
        db.flush()

        old_task = FileParseTask(
            kb_space_id=kb_space.id,
            course_id=cls.course_id,
            class_id=cls.id,
            material_id=material_old.id,
            status="completed",
            parser_name="raganything",
            extra_data={
                "raganything_storage": {
                    "requested_backend": "lightrag-default",
                    "effective_backend": "lightrag-default",
                    "active_lightrag_storage": {
                        "requested_backend": "lightrag-default",
                        "effective_backend": "lightrag-default",
                    },
                },
            },
        )
        new_task = FileParseTask(
            kb_space_id=kb_space.id,
            course_id=cls.course_id,
            class_id=cls.id,
            material_id=material_new.id,
            status="completed",
            parser_name="raganything",
            extra_data={
                "raganything_storage": {
                    "requested_backend": "qdrant-neo4j",
                    "effective_backend": "qdrant-neo4j",
                    "active_lightrag_storage": {
                        "requested_backend": "qdrant-neo4j",
                        "effective_backend": "qdrant-neo4j",
                    },
                },
            },
        )
        db.add_all([old_task, new_task])
        db.commit()

        course_id = cls.course_id
        old_material_id = material_old.id
        new_material_id = material_new.id

    monkeypatch.setattr(
        adapter_module,
        "build_runtime_rag_storage_config_snapshot",
        lambda: {
            "requested_backend": "qdrant-neo4j",
            "effective_backend": "qdrant-neo4j",
            "activation_state": "external_config_ready",
            "external_configured": True,
            "external_ready": True,
            "supports_external_vector": True,
            "supports_external_graph": True,
            "vector_db": {"provider": "qdrant"},
            "graph_db": {"provider": "neo4j"},
            "working_dir": {"path": "E:/tmp/rag_storage", "exists": True},
            "output_dir": {"path": "E:/tmp/rag_output", "exists": True},
            "note": "test snapshot",
        },
    )

    async def _fake_ingest(class_id, material_id, file_path, mime_type):
        _ = (class_id, file_path, mime_type)
        recorded.append(material_id)
        return True

    monkeypatch.setattr(adapter, "ingest_material", _fake_ingest)
    monkeypatch.setattr(adapter, "get_kb_status", lambda cid: {"course_id": cid, "storage": {"reindex_required": True}})

    result = asyncio.run(adapter.rebuild_course(course_id, storage_migration_only=True))

    assert recorded == [old_material_id]
    assert new_material_id not in recorded
    assert result["rebuild_scope"] == "storage_migration_only"
    assert result["requested_reindex_count"] == 1
    assert result["reprocessed_count"] == 1
    assert result["storage_migration_target_backend"] == "qdrant-neo4j"

    with SessionLocal() as db:
        db.query(FileParseTask).filter(FileParseTask.material_id.in_([old_material_id, new_material_id])).delete(synchronize_session=False)
        db.query(Material).filter(Material.id.in_([old_material_id, new_material_id])).delete(synchronize_session=False)
        db.query(KBSpace).filter(KBSpace.class_id == cls.id).delete(synchronize_session=False)
        db.query(Class).filter(Class.id == cls.id).delete(synchronize_session=False)
        db.query(Course).filter(Course.id == course_id).delete(synchronize_session=False)
        db.commit()


def test_raganything_metadata_payload_can_read_official_output_files(monkeypatch):
    adapter = RAGAnythingAdapter()
    tmp_path = _make_workspace_tmp_dir("metadata_payload")
    class_id = "class-output"
    output_dir = tmp_path / class_id / "fixture_notes" / "hybrid_auto"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "fixture_notes_content_list.json").write_text(
        json.dumps([
            {
                "type": "text",
                "text": "Adaptive congestion control improves queue stability.",
                "bbox": [1, 2, 3, 4],
                "page_idx": 0,
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "fixture_notes.md").write_text(
        "Adaptive congestion control improves queue stability.\n\nQueue delay matters.",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "RAGANYTHING_OUTPUT_DIR", str(tmp_path))

    preprocess = SimpleNamespace(
        mode="direct_document",
        content_list=[],
    )

    payload = adapter._build_metadata_payload(
        class_id=class_id,
        status={"entrypoint": "process_document_complete"},
        preprocess_result=preprocess,
        file_path=str(Path("fixture_notes.txt")),
        mime_type="text/plain",
        file_name="fixture_notes.txt",
    )

    assert payload["metadata_source"] == "raganything_output_files"
    assert payload["content_items"]
    assert payload["content_items"][0]["text"].startswith("Adaptive congestion control")
    assert payload["chunks"]
    assert payload["summary"].startswith("Adaptive congestion control")
