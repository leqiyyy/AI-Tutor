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
from app.integrations.rag import raganything_adapter as raganything_adapter_module
from app.integrations.rag.query_rewrite import build_query_rewrite_bundle
from app.integrations.rag.raganything_adapter import RAGAnythingAdapter
from app.integrations.rag.storage_config import build_runtime_rag_storage_config_snapshot
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


def test_raganything_llm_func_records_query_trace(monkeypatch):
    adapter = _build_adapter_with_db_free_mocks(monkeypatch)
    trace = {}
    token = raganything_adapter_module._QUERY_TRACE_CONTEXT.set(trace)

    async def fake_call_llm_api(**kwargs):
        return "ok"

    monkeypatch.setattr(adapter, "_call_llm_api", fake_call_llm_api)
    llm_func = adapter._build_llm_func({
        "generation": {
            "model": "generation-model",
            "api_base": "https://generation.example/v1",
        }
    })

    try:
        result = asyncio.run(
            llm_func(
                "Provided context:\nTCP slow start.\n\nUser query: explain it",
                system_prompt="Answer using the provided context.",
                history_messages=[{"role": "user", "content": "之前的问题"}],
            )
        )
    finally:
        raganything_adapter_module._QUERY_TRACE_CONTEXT.reset(token)

    assert result == "ok"
    assert trace["llm_call_count"] == 1
    assert trace["llm_calls"][0]["purpose"] == "answer_generation"
    assert trace["final_generation_input"]["model"] == "generation-model"
    assert trace["final_generation_input"]["prompt_chars"] > 0


def test_raganything_effective_query_submits_compact_terms_only():
    adapter = RAGAnythingAdapter()
    bundle = build_query_rewrite_bundle(
        question="TCP 和 UDP 的区别是什么？",
        enabled=True,
        mode="hybrid",
        max_variants=4,
    )

    query_text = adapter._build_effective_query_text(
        question="TCP 和 UDP 的区别是什么？",
        rewrite_bundle=bundle,
    )

    assert "检索辅助信息" not in query_text
    assert "问题意图" not in query_text
    assert "回答时必须以原始问题为准" not in query_text
    assert query_text.startswith("TCP 和 UDP 的区别是什么？")
    assert len(query_text.splitlines()) <= 2
    assert any(term in query_text for term in ("TCP/IP", "传输层", "可靠传输", "适用场景"))


def test_raganything_compact_retrieval_terms_filters_meta_noise():
    adapter = RAGAnythingAdapter()
    terms = adapter._compact_retrieval_terms(
        question="链路层的功能是什么？",
        rewrite_bundle={
            "queries": [
                "链路层的功能是什么？",
                "检索辅助信息 问题意图 查找 资料 回答 数据链路层 成帧 CRC",
            ],
            "retrieval_focus_terms": ["检索焦点", "核心特征", "资料"],
        },
        max_terms=8,
    )

    assert "数据链路层" in terms
    assert "成帧" in terms
    assert "CRC" in terms
    assert "检索辅助信息" not in terms
    assert "问题意图" not in terms
    assert "资料" not in terms


def test_raganything_aquery_history_keeps_only_related_context(monkeypatch):
    adapter = RAGAnythingAdapter()
    monkeypatch.setattr(settings, "RAG_AQUERY_HISTORY_POLICY", "compact")
    monkeypatch.setattr(settings, "RAG_AQUERY_HISTORY_MAX_MESSAGES", 4)
    monkeypatch.setattr(settings, "RAG_AQUERY_HISTORY_MESSAGE_MAX_CHARS", 80)

    history, meta = adapter._build_aquery_history(
        history=[
            {"role": "user", "content": "DNS 的递归查询是什么？"},
            {"role": "assistant", "content": "DNS 递归查询会由递归解析器继续代查。"},
            {"role": "user", "content": "TCP 拥塞控制有哪些阶段？"},
            {"role": "assistant", "content": "TCP 拥塞控制包括慢启动、拥塞避免、快重传和快恢复。"},
        ],
        query_text="TCP 拥塞控制。追问：继续解释第二点",
    )

    assert meta["policy"] == "compact"
    assert meta["submitted_count"] == 2
    assert all("DNS" not in item["content"] for item in history)
    assert any("TCP" in item["content"] for item in history)
    assert any("慢启动" in item["content"] for item in history)


def test_raganything_aquery_history_drops_unrelated_new_topic(monkeypatch):
    adapter = RAGAnythingAdapter()
    monkeypatch.setattr(settings, "RAG_AQUERY_HISTORY_POLICY", "compact")
    monkeypatch.setattr(settings, "RAG_AQUERY_HISTORY_MAX_MESSAGES", 4)

    history, meta = adapter._build_aquery_history(
        history=[
            {"role": "user", "content": "TCP 拥塞控制有哪些阶段？"},
            {"role": "assistant", "content": "慢启动、拥塞避免、快重传和快恢复是常见阶段。"},
        ],
        query_text="请解释 DNS 的递归查询过程",
    )

    assert history == []
    assert meta["submitted_count"] == 0
    assert meta["dropped_count"] == 2


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


def test_lightrag_reference_query_modes_include_global_for_mix():
    adapter = RAGAnythingAdapter()

    assert adapter._lightrag_reference_query_modes("mix") == [
        "hybrid",
        "global",
        "local",
        "naive",
    ]


def test_llm_history_messages_normalize_ai_role_for_model_apis():
    adapter = RAGAnythingAdapter()

    normalized = adapter._normalize_llm_history_messages([
        {"role": "user", "content": "链路层是什么？"},
        {"role": "ai", "content": "链路层负责相邻节点间的数据传输。"},
        {"role": "system", "content": ""},
    ])

    assert normalized == [
        {"role": "user", "content": "链路层是什么？"},
        {"role": "assistant", "content": "链路层负责相邻节点间的数据传输。"},
    ]


def test_llm_history_messages_skip_garbled_assistant_answers():
    adapter = RAGAnythingAdapter()

    normalized = adapter._normalize_llm_history_messages([
        {"role": "user", "content": "链路层和协议层的关系是什么？"},
        {
            "role": "ai",
            "content": (
                "关键词 词汇表 内容提由文字 协议里关键词二 关键词查看代码 "
                "\\修 \\修 \\修 \\修 \\修 \\修 \\修 \\修 \\修 \\修"
            ),
        },
        {"role": "user", "content": "传输层呢？"},
    ])

    assert normalized == [
        {"role": "user", "content": "链路层和协议层的关系是什么？"},
        {"role": "user", "content": "传输层呢？"},
    ]


def test_answer_repair_detects_lightrag_keyword_gibberish():
    adapter = RAGAnythingAdapter()

    assert adapter._answer_needs_repair(
        "关键词 词汇表 内容提由文字 协议里关键词二 关键词查看代码 "
        "\\修 \\修 \\修 \\修 \\修 \\修 \\修 \\修 \\修 \\修"
    )


def test_answer_repair_detects_code_like_gibberish():
    adapter = RAGAnythingAdapter()

    assert adapter._answer_needs_repair(
        "订单抽象\\6 \\; parseInt stdClass IP IP TCP UDP ACK SYN FIN "
        "\\IP \\TCP \\UDP \\ACK \\SYN \\FIN \\PIP \\CPI \\ping"
    )


def test_answer_repair_does_not_repair_normal_markdown_tables():
    adapter = RAGAnythingAdapter()

    answer = """
### TCP 拥塞控制机制详解

| 丢包检测方式 | 拥塞窗口变化 | 进入阶段 |
|------------|------------|---------|
| 超时 | CongWin 降为 1 MSS | 慢启动 |
| 3 个重复 ACK | CongWin 降为 CongWin/2 | 拥塞避免 |

TCP 拥塞控制会结合确认应答、超时重传等机制，共同服务于可靠传输。
"""

    assert not adapter._answer_needs_repair(answer)


def test_compact_retrieval_terms_rejects_broad_terms_not_in_question():
    adapter = RAGAnythingAdapter()

    terms = adapter._compact_retrieval_terms(
        question="解释 TCP 拥塞控制中慢启动和拥塞避免的关系",
        rewrite_bundle={
            "queries": [
                "解释 TCP 拥塞控制中慢启动和拥塞避免的关系",
                "传输层；TCP；UDP；可靠传输；流量控制；拥塞控制；慢启动；拥塞避免",
            ],
            "retrieval_focus_terms": [],
        },
    )

    assert "UDP" not in terms
    assert "慢启动" in terms
    assert "拥塞避免" in terms


def test_answer_generation_prompt_recognizes_lightrag_rag_prompt():
    adapter = RAGAnythingAdapter()

    assert adapter._is_answer_generation_prompt(
        "User Query: 链路层的功能是什么\nReference Document List: [1] note.md",
        "You answer by only using the information within the provided Context.",
        False,
    )


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
    assert result.meta["query_trace"]["rerank"]["applied"] is True
    assert result.meta["query_trace"]["rerank"]["before"]["count"] == 2
    assert result.meta["query_trace"]["rerank"]["after"]["items"][0]["chunk_id"] == "tcp"
    assert result.meta["query_trace"]["sources_final"]["items"][0]["chunk_id"] == "tcp"
    reset_reranker_cache()


def test_raganything_main_chain_sources_are_limited_to_answer_top_k(monkeypatch):
    reset_reranker_cache()
    monkeypatch.setattr(settings, "RERANKER_PROVIDER", "mock")
    monkeypatch.setattr(settings, "RAG_ANSWER_TOP_K", 1)
    adapter = _build_adapter_with_db_free_mocks(monkeypatch)

    class FakeRag:
        async def aquery(self, query, mode=None):
            return {
                "answer": "Use slow start to grow cwnd until ssthresh.",
                "sources": [
                    {
                        "name": "queueing.md",
                        "score": 0.5,
                        "chunk_id": "queue",
                        "content": "Queue management and packet scheduling.",
                    },
                    {
                        "name": "tcp.md",
                        "score": 0.55,
                        "chunk_id": "tcp",
                        "content": "TCP slow start grows the congestion window each RTT.",
                    },
                    {
                        "name": "routing.md",
                        "score": 0.4,
                        "chunk_id": "routing",
                        "content": "Routing protocols exchange reachability information.",
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

    assert [source["chunk_id"] for source in result.sources] == ["tcp"]
    assert result.meta["candidate_count"] == 3
    assert result.meta["selected_count"] == 1
    assert result.meta["source_top_k"] == 1
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

    assert "我暂时没有从当前课程资料中检索到足够依据" in result.answer
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


def test_raganything_content_items_get_stable_atomic_ids():
    adapter = RAGAnythingAdapter()
    items = adapter._annotate_content_items(
        [
            {
                "type": "table",
                "text": "第 1 行，指标：throughput；数值：125。",
                "table_markdown": "| metric | value |\n| --- | --- |\n| throughput | 125 |",
                "page_idx": 0,
                "metadata": {"source_type": "table"},
            }
        ],
        material_id="mat-1",
        file_name="lesson.md",
    )

    assert len(items) == 1
    assert items[0]["atomic_id"].startswith("mat-1-au-1-")
    assert items[0]["item_id"] == items[0]["atomic_id"]
    assert items[0]["modality"] == "table"
    assert items[0]["metadata"]["material_id"] == "mat-1"
    assert items[0]["metadata"]["source_name"] == "lesson.md"


def test_raganything_projection_rejects_table_artifact_entities():
    adapter = RAGAnythingAdapter()

    assert adapter._is_projection_course_entity("拥塞控制", entity_type="course_concept")
    assert not adapter._is_projection_course_entity("表的结构", entity_type="concept")
    assert not adapter._is_projection_course_entity("Table Structure", entity_type="concept")
    assert not adapter._is_projection_course_entity("lesson.md", entity_type="concept")


def test_raganything_query_rewrite_trace_records_submitted_query_policy():
    adapter = RAGAnythingAdapter()
    bundle = build_query_rewrite_bundle(
        question="TCP 和 UDP 的区别是什么？",
        enabled=True,
        mode="hybrid",
        max_variants=4,
    )
    effective_question = adapter._build_effective_query_text(
        question="TCP 和 UDP 的区别是什么？",
        rewrite_bundle=bundle,
    )

    trace = adapter._build_query_rewrite_trace(
        question="TCP 和 UDP 的区别是什么？",
        effective_question=effective_question,
        rewrite_bundle=bundle,
    )

    assert trace["submitted_query_policy"] == "original_question_plus_compact_terms"
    assert trace["submitted_compact_terms"]
    assert "检索辅助信息" not in " ".join(trace["submitted_compact_terms"])
    assert trace["effective_question_preview"].startswith("TCP 和 UDP 的区别是什么？")


def test_structured_table_query_terms_extract_target_term():
    adapter = RAGAnythingAdapter()

    terms = adapter._structured_table_query_terms("在中英对照表格中，协议是什么意思")

    assert "协议" in terms
    assert "中英对照" not in terms
    assert adapter._is_structured_table_lookup_question("在中英对照表格中，协议是什么意思")


def test_structured_table_matches_are_merged_before_rerank(monkeypatch):
    adapter = RAGAnythingAdapter()

    monkeypatch.setattr(
        adapter,
        "_lookup_structured_table_sources",
        lambda **kwargs: [{
            "chunk_id": "table-protocol",
            "source_name": "notes.md",
            "raw_text": "第 7 行，中英对照：协议（protocol）；概念：网络协议的简称，是通信计算机双方必须共同遵守的约定。",
            "retrieval_score": 1.0,
        }],
    )

    sources, meta = adapter._augment_sources_with_structured_table_matches(
        question="在中英对照表格中，协议是什么意思",
        sources=[{
            "chunk_id": "generic-table",
            "source_name": "notes.md",
            "raw_text": "Table Analysis: table structure and organization",
            "retrieval_score": 0.0,
        }],
        class_id="class-demo",
    )

    assert meta["enabled"] is True
    assert meta["matched_count"] == 1
    assert sources[0]["chunk_id"] == "table-protocol"


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
    assert raw["metadata"]["adapter_include_references_requested"] is True


def test_lightrag_query_param_enables_rerank_when_supported(monkeypatch):
    adapter = RAGAnythingAdapter()
    monkeypatch.setattr(settings, "RERANKER_PROVIDER", "api")

    class FakeQueryParam:
        def __init__(self, mode, include_references, conversation_history, enable_rerank=False):
            self.mode = mode
            self.include_references = include_references
            self.conversation_history = conversation_history
            self.enable_rerank = enable_rerank

    param = adapter._build_lightrag_query_param(
        QueryParam=FakeQueryParam,
        mode="hybrid",
        history=[],
        role="student",
    )

    assert param.enable_rerank is True


def test_raganything_query_trace_counts_raw_payload(monkeypatch):
    adapter = RAGAnythingAdapter()
    monkeypatch.setattr(settings, "RERANKER_PROVIDER", "local")

    trace = adapter._build_query_trace(
        raw={
            "llm_response": {"content": "answer"},
            "metadata": {
                "adapter_effective_mode": "hybrid",
                "adapter_attempted_modes": ["hybrid"],
                "adapter_include_references_requested": True,
                "adapter_lightrag_rerank_requested": True,
            },
            "data": {
                "chunks": [{"content": "chunk"}],
                "entities": [{"name": "TCP"}],
                "relationships": [{"source": "TCP", "target": "拥塞控制"}],
            },
        },
        query_method="lightrag_aquery_llm:hybrid",
        requested_mode="mix",
        has_image=False,
    )

    assert trace["effective_mode"] == "hybrid"
    assert trace["raw_source_counts"]["data_chunks"] == 1
    assert trace["raw_source_counts"]["data_entities"] == 1
    assert trace["raw_context"]["data_chunks"]["text_chars"] == len("chunk")
    assert trace["lightrag_internal_rerank_requested"] is True


def test_raganything_source_atomic_metadata_matches_chunk():
    adapter = RAGAnythingAdapter()
    task = SimpleNamespace(
        chunks=[
            {
                "chunk_id": "chunk-1",
                "text": "TCP slow start doubles the congestion window.",
                "metadata": {
                    "atomic_id": "atomic-1",
                    "item_id": "item-1",
                    "modality": "text",
                    "content_index": 1,
                },
            }
        ],
        extra_data={"content_items": []},
    )

    payload = adapter._source_atomic_metadata(
        {"chunk_id": "chunk-1", "snippet": "TCP slow start doubles the congestion window."},
        task,
    )

    assert payload["atomic_id"] == "atomic-1"
    assert payload["item_id"] == "item-1"
    assert payload["modality"] == "text"


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
    node_label = f"拥塞控制{marker[:4]}"
    related_label = f"慢启动{marker[:4]}"

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

        storage_snapshot = build_runtime_rag_storage_config_snapshot()
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
                "raganything_storage": {
                    **storage_snapshot,
                    "active_lightrag_storage": {
                        "requested_backend": storage_snapshot.get("requested_backend"),
                        "effective_backend": storage_snapshot.get("effective_backend"),
                    },
                },
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
        material_id="material-output",
        file_path=str(Path("fixture_notes.txt")),
        mime_type="text/plain",
        file_name="fixture_notes.txt",
    )

    assert payload["metadata_source"] == "raganything_output_files"
    assert payload["content_items"]
    assert payload["content_items"][0]["text"].startswith("Adaptive congestion control")
    assert payload["chunks"]
    assert payload["summary"].startswith("Adaptive congestion control")
