import pytest

from app.integrations.rag.storage_config import (
    build_external_storage_bootstrap_plan,
    build_lightrag_storage_plan,
    build_rag_storage_config_snapshot,
)


def test_storage_config_defaults_to_local_only(monkeypatch):
    import app.integrations.rag.storage_config as storage_config

    monkeypatch.setattr(storage_config.settings, "RAG_STORAGE_BACKEND", "lightrag-default")
    monkeypatch.setattr(storage_config.settings, "VECTOR_DB_PROVIDER", "auto")
    monkeypatch.setattr(storage_config.settings, "VECTOR_DB_URL", "")
    monkeypatch.setattr(storage_config.settings, "VECTOR_DB_API_KEY", "")
    monkeypatch.setattr(storage_config.settings, "GRAPH_DB_PROVIDER", "auto")
    monkeypatch.setattr(storage_config.settings, "GRAPH_DB_URL", "")
    monkeypatch.setattr(storage_config.settings, "GRAPH_DB_USERNAME", "")
    monkeypatch.setattr(storage_config.settings, "GRAPH_DB_PASSWORD", "")

    snapshot = build_rag_storage_config_snapshot()

    assert snapshot["requested_backend"] == "lightrag-default"
    assert snapshot["effective_backend"] == "lightrag-default"
    assert snapshot["activation_state"] == "local_only"
    assert snapshot["supports_external_vector"] is False
    assert snapshot["supports_external_graph"] is False


def test_storage_config_marks_qdrant_neo4j_ready(monkeypatch):
    import app.integrations.rag.storage_config as storage_config

    monkeypatch.setattr(storage_config.settings, "RAG_STORAGE_BACKEND", "qdrant-neo4j")
    monkeypatch.setattr(storage_config.settings, "VECTOR_DB_PROVIDER", "qdrant")
    monkeypatch.setattr(storage_config.settings, "VECTOR_DB_URL", "http://localhost:6333")
    monkeypatch.setattr(storage_config.settings, "VECTOR_DB_API_KEY", "vector-key")
    monkeypatch.setattr(storage_config.settings, "VECTOR_DB_COLLECTION", "course_chunks")
    monkeypatch.setattr(storage_config.settings, "GRAPH_DB_PROVIDER", "neo4j")
    monkeypatch.setattr(storage_config.settings, "GRAPH_DB_URL", "bolt://localhost:7687")
    monkeypatch.setattr(storage_config.settings, "GRAPH_DB_DATABASE", "neo4j")
    monkeypatch.setattr(storage_config.settings, "GRAPH_DB_USERNAME", "neo4j")
    monkeypatch.setattr(storage_config.settings, "GRAPH_DB_PASSWORD", "graph-pass")
    monkeypatch.setattr(storage_config, "_package_available", lambda name: True)

    snapshot = build_rag_storage_config_snapshot()

    assert snapshot["requested_backend"] == "qdrant-neo4j"
    assert snapshot["effective_backend"] == "qdrant-neo4j"
    assert snapshot["activation_state"] == "external_config_ready"
    assert snapshot["external_ready"] is True
    assert snapshot["vector_db"]["provider"] == "qdrant"
    assert snapshot["vector_db"]["collection"] == "course_chunks"
    assert snapshot["graph_db"]["provider"] == "neo4j"
    assert snapshot["graph_db"]["database"] == "neo4j"

    plan = build_lightrag_storage_plan("class-demo")

    assert plan["effective_backend"] == "qdrant-neo4j"
    assert plan["workspace"] == "course_chunks__class-demo"
    assert plan["lightrag_kwargs"]["vector_storage"] == "QdrantVectorDBStorage"
    assert plan["lightrag_kwargs"]["graph_storage"] == "Neo4JStorage"
    assert plan["env_overrides"]["QDRANT_URL"] == "http://localhost:6333"
    assert plan["env_overrides"]["NEO4J_URI"] == "bolt://localhost:7687"


def test_storage_plan_raises_when_external_backend_is_incomplete(monkeypatch):
    import app.integrations.rag.storage_config as storage_config

    monkeypatch.setattr(storage_config.settings, "RAG_STORAGE_BACKEND", "qdrant")
    monkeypatch.setattr(storage_config.settings, "VECTOR_DB_PROVIDER", "qdrant")
    monkeypatch.setattr(storage_config.settings, "VECTOR_DB_URL", "")
    monkeypatch.setattr(storage_config.settings, "VECTOR_DB_API_KEY", "")

    snapshot = build_rag_storage_config_snapshot()

    assert snapshot["requested_backend"] == "qdrant"
    assert snapshot["effective_backend"] == "unavailable"
    assert snapshot["activation_state"] == "external_config_incomplete"

    with pytest.raises(RuntimeError, match="Requested external RAG storage is not ready"):
        build_lightrag_storage_plan("class-demo")


def test_storage_config_includes_connectivity_when_requested(monkeypatch):
    import app.integrations.rag.storage_config as storage_config

    monkeypatch.setattr(storage_config.settings, "RAG_STORAGE_BACKEND", "qdrant-neo4j")
    monkeypatch.setattr(storage_config.settings, "VECTOR_DB_PROVIDER", "qdrant")
    monkeypatch.setattr(storage_config.settings, "VECTOR_DB_URL", "http://localhost:6333")
    monkeypatch.setattr(storage_config.settings, "VECTOR_DB_API_KEY", "vector-key")
    monkeypatch.setattr(storage_config.settings, "GRAPH_DB_PROVIDER", "neo4j")
    monkeypatch.setattr(storage_config.settings, "GRAPH_DB_URL", "bolt://localhost:7687")
    monkeypatch.setattr(storage_config.settings, "GRAPH_DB_USERNAME", "neo4j")
    monkeypatch.setattr(storage_config.settings, "GRAPH_DB_PASSWORD", "graph-pass")
    monkeypatch.setattr(storage_config, "_package_available", lambda name: True)
    monkeypatch.setattr(
        storage_config,
        "_probe_vector_connectivity",
        lambda **kwargs: {
            "attempted": True,
            "reachable": True,
            "protocol": "http",
            "latency_ms": 12.5,
            "detail": "ok",
        },
    )
    monkeypatch.setattr(
        storage_config,
        "_probe_graph_connectivity",
        lambda **kwargs: {
            "attempted": True,
            "reachable": True,
            "protocol": "bolt",
            "latency_ms": 8.0,
            "detail": "Neo4j/5.x",
        },
    )

    snapshot = build_rag_storage_config_snapshot(include_connectivity=True)

    assert snapshot["external_ready"] is True
    assert snapshot["vector_db"]["connectivity"]["reachable"] is True
    assert snapshot["graph_db"]["connectivity"]["reachable"] is True
    assert snapshot["vector_db"]["ready"] is True
    assert snapshot["graph_db"]["ready"] is True


def test_external_storage_bootstrap_plan_prefers_qdrant_neo4j(monkeypatch):
    import app.integrations.rag.storage_config as storage_config

    monkeypatch.setattr(storage_config, "_package_available", lambda name: False)
    monkeypatch.setattr(storage_config.settings, "VECTOR_DB_URL", "")
    monkeypatch.setattr(storage_config.settings, "GRAPH_DB_URL", "")
    monkeypatch.setattr(storage_config.settings, "GRAPH_DB_PASSWORD", "")

    plan = build_external_storage_bootstrap_plan("qdrant-neo4j")

    assert plan["target_backend"] == "qdrant-neo4j"
    assert "qdrant-client>=1.10.0" in plan["install_packages"]
    assert "neo4j>=5.20.0" in plan["install_packages"]
    assert plan["env_patch"]["VECTOR_DB_URL"] == "http://localhost:6333"
    assert plan["env_patch"]["GRAPH_DB_URL"] == "bolt://localhost:7687"
    assert "RAG_STORAGE_BACKEND=qdrant-neo4j" in plan["env_block"]
