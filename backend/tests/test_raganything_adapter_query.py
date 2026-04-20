import asyncio

from app.core.config import settings
from app.integrations.rag.raganything_adapter import RAGAnythingAdapter


def _build_adapter_with_db_free_mocks(monkeypatch):
    adapter = RAGAnythingAdapter()
    monkeypatch.setattr(adapter, "_review_answer_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(adapter, "_search_chunks_for_queries", lambda *args, **kwargs: [])
    return adapter


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
    assert result.meta["query_rewrite_mode"] in {"disabled", "simple", "compact", "keywords"}
    assert result.meta["query_variant_count"] >= 1


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


def test_raganything_query_falls_back_when_main_chain_fails(monkeypatch):
    adapter = RAGAnythingAdapter()

    class BrokenRag:
        async def aquery(self, query, mode=None):
            raise RuntimeError("raganything query failed")

    monkeypatch.setattr(adapter, "_get_instance", lambda class_id: BrokenRag())
    monkeypatch.setattr(adapter, "_review_answer_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        adapter,
        "_search_chunks_for_queries",
        lambda *args, **kwargs: [
            {
                "source_name": "network_notes.pdf",
                "source_type": "pdf",
                "page": 3,
                "chunk_id": "chunk-fallback-1",
                "score": 0.8,
                "snippet": "Slow start doubles cwnd every RTT before threshold.",
                "raw_text": "Slow start doubles congestion window each RTT before reaching ssthresh.",
            }
        ],
    )
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

    async def fake_llm(*args, **kwargs):
        return "Fallback answer from local retrieval chain"

    monkeypatch.setattr(adapter, "_call_llm_api", fake_llm)

    result = asyncio.run(
        adapter.query(
            question="How does slow start work?",
            class_id="class-demo",
            history=[],
            attachments=[],
        )
    )

    assert result.answer == "Fallback answer from local retrieval chain"
    assert result.sources[0]["name"] == "network_notes.pdf"
    assert result.confidence >= 0.55
    assert result.meta["used_fallback"] is True
    assert result.meta["retrieval_strategy"] in {"lexical", "hybrid", "graph"}
    assert "reranker_provider" in result.meta
    assert result.meta["query_rewrite_mode"] in {"disabled", "simple", "compact", "keywords"}
    assert result.meta["query_variant_count"] >= 1


def test_raganything_merges_multi_query_search_results(monkeypatch):
    adapter = RAGAnythingAdapter()

    def fake_search(_db, _class_id, query):
        if query == "query-a":
            return [{
                "source_name": "network_notes.pdf",
                "source_type": "pdf",
                "page": 2,
                "chunk_id": "chunk-1",
                "score": 0.6,
                "snippet": "chunk one",
                "raw_text": "chunk one text",
            }]
        if query == "query-b":
            return [{
                "source_name": "network_notes.pdf",
                "source_type": "pdf",
                "page": 2,
                "chunk_id": "chunk-1",
                "score": 0.8,
                "snippet": "chunk one better",
                "raw_text": "chunk one text improved",
            }]
        return []

    monkeypatch.setattr(adapter, "_search_class_chunks", fake_search)
    merged = adapter._search_chunks_for_queries(
        db=None,
        class_id="class-demo",
        queries=["query-a", "query-b"],
    )

    assert len(merged) == 1
    assert merged[0]["chunk_id"] == "chunk-1"
    assert merged[0]["score"] == 0.8
    assert merged[0]["query_hits"] == 2
    assert set(merged[0]["matched_queries"]) == {"query-a", "query-b"}


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
