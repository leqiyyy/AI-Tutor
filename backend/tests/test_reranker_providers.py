import asyncio

from app.core.config import settings
from app.integrations.reranker import get_reranker, reset_reranker_cache
from app.integrations.reranker.api_reranker import APIReranker
from app.integrations.reranker.local_reranker import LocalReranker


def test_api_reranker_uses_remote_scores(monkeypatch):
    reranker = APIReranker()
    candidates = [
        {"chunk_id": "a", "raw_text": "TCP congestion control introduction", "retrieval_score": 0.5},
        {"chunk_id": "b", "raw_text": "Detailed slow start and cwnd threshold notes", "retrieval_score": 0.5},
    ]

    async def fake_fetch_scores(*, query, candidates):
        _ = (query, candidates)
        return [0.1, 0.9]

    monkeypatch.setattr(reranker, "_fetch_scores", fake_fetch_scores)
    result = asyncio.run(reranker.rerank(query="Explain slow start", candidates=candidates))

    assert len(result) == 2
    assert result[0]["chunk_id"] == "b"
    assert result[0]["reranker_provider"] == "api"


def test_api_reranker_falls_back_on_remote_failure(monkeypatch):
    reranker = APIReranker()
    candidates = [
        {"chunk_id": "low", "raw_text": "low", "retrieval_score": 0.1},
        {"chunk_id": "high", "raw_text": "high", "retrieval_score": 0.7},
    ]

    async def broken_fetch(*, query, candidates):
        _ = (query, candidates)
        raise RuntimeError("network down")

    monkeypatch.setattr(reranker, "_fetch_scores", broken_fetch)
    result = asyncio.run(reranker.rerank(query="any", candidates=candidates))

    assert result[0]["chunk_id"] == "high"
    assert result[0]["rerank_components"]["api_fallback"] is True
    assert result[0]["rerank_fallback_reason"] == "RuntimeError"


def test_local_reranker_heuristic_sorts_by_semantic_overlap():
    reranker = LocalReranker()
    candidates = [
        {
            "chunk_id": "a",
            "raw_text": "Slow start doubles congestion window before reaching threshold.",
            "retrieval_score": 0.4,
        },
        {
            "chunk_id": "b",
            "raw_text": "This section is about course schedule and grading policy.",
            "retrieval_score": 0.4,
        },
    ]
    result = asyncio.run(reranker.rerank(query="Explain slow start congestion window", candidates=candidates))

    assert len(result) == 2
    assert result[0]["chunk_id"] == "a"
    assert result[0]["reranker_provider"] == "local"


def test_reranker_factory_selects_api_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "RERANKER_PROVIDER", "api")
    monkeypatch.setattr(settings, "RERANKER_API_BASE", "http://localhost:18080")
    reset_reranker_cache()

    reranker = get_reranker()
    assert reranker.provider_name == "api"


def test_reranker_factory_falls_back_to_mock_for_unconfigured_api(monkeypatch):
    monkeypatch.setattr(settings, "RERANKER_PROVIDER", "api")
    monkeypatch.setattr(settings, "RERANKER_API_BASE", "")
    reset_reranker_cache()

    reranker = get_reranker()
    assert reranker.provider_name == "mock"
