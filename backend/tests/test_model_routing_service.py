from app.core.config import settings
from app.services import model_routing_service


def test_generation_route_falls_back_to_mock_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "LLM_BACKEND", "api")
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

    snapshot = model_routing_service.build_model_routing_snapshot()
    generation = snapshot["generation"]

    assert generation["requested_backend"] == "api"
    assert generation["effective_backend"] == "mock"
    assert generation["fallback_reason"] == "missing_api_key"


def test_generation_route_uses_local_backend_when_local_base_provided(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "LLM_BACKEND", "local")
    monkeypatch.setattr(settings, "LLM_LOCAL_API_BASE", "http://127.0.0.1:8001/v1")

    snapshot = model_routing_service.build_model_routing_snapshot()
    generation = snapshot["generation"]

    assert generation["effective_backend"] == "local"
    assert generation["api_base"] == "http://127.0.0.1:8001/v1"
    assert generation["provider"] == "local-openai-compatible"


def test_reranker_route_falls_back_to_mock_when_api_base_missing(monkeypatch):
    monkeypatch.setattr(settings, "RERANKER_PROVIDER", "api")
    monkeypatch.setattr(settings, "RERANKER_API_BASE", "")

    snapshot = model_routing_service.build_model_routing_snapshot()
    reranker = snapshot["reranker"]

    assert reranker["requested_backend"] == "api"
    assert reranker["effective_backend"] == "mock"
    assert reranker["fallback_reason"] == "missing_api_base"


def test_routing_snapshot_accepts_override_map():
    snapshot = model_routing_service.build_model_routing_snapshot({
        "llm_provider": "mock",
        "llm_backend": "mock",
        "embedding_backend": "mock",
        "vlm_backend": "mock",
        "reranker_provider": "none",
    })

    flat = model_routing_service.flatten_routing_snapshot(snapshot)
    assert flat["llm_backend"] == "mock"
    assert flat["embedding_backend"] == "mock"
    assert flat["vlm_backend"] == "mock"
    assert flat["reranker_backend"] == "none"
