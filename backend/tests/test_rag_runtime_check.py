from importlib.machinery import ModuleSpec

from app.integrations.rag.runtime_check import build_raganything_runtime_report
from app.integrations.rag.storage_config import build_rag_storage_config_snapshot


def test_runtime_report_blocks_when_dependencies_missing(monkeypatch):
    import app.integrations.rag.runtime_check as runtime_check

    monkeypatch.setattr(runtime_check.settings, "RAG_ENGINE", "raganything")
    monkeypatch.setattr(runtime_check.settings, "LIBREOFFICE_PATH", "")
    monkeypatch.setattr(runtime_check.settings, "LLM_MODEL", "")
    monkeypatch.setattr(runtime_check.settings, "LLM_API_BASE", "")
    monkeypatch.setattr(runtime_check.settings, "OPENAI_API_BASE", "")
    monkeypatch.setattr(runtime_check.settings, "LLM_API_KEY", "")
    monkeypatch.setattr(runtime_check.settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(runtime_check.settings, "EXTRACT_MODEL", "")
    monkeypatch.setattr(runtime_check.settings, "EXTRACT_API_BASE", "")
    monkeypatch.setattr(runtime_check.settings, "EXTRACT_API_KEY", "")
    monkeypatch.setattr(runtime_check.settings, "EMBEDDING_MODEL", "")
    monkeypatch.setattr(runtime_check.settings, "EMBEDDING_API_BASE", "")
    monkeypatch.setattr(runtime_check.settings, "EMBEDDING_API_KEY", "")
    monkeypatch.setattr(
        runtime_check.model_routing_service,
        "build_runtime_model_routing_snapshot",
        lambda: {
            "generation": {"effective_backend": "mock"},
            "embedding": {"effective_backend": "mock"},
            "vlm": {"effective_backend": "mock"},
            "reranker": {"effective_backend": "mock"},
        },
    )
    monkeypatch.setattr(
        runtime_check.importlib.util,
        "find_spec",
        lambda name: None,
    )
    monkeypatch.setattr(runtime_check.shutil, "which", lambda name: None)

    report = build_raganything_runtime_report()

    assert report["status"] == "blocked"
    keys = {item["key"] for item in report["blockers"]}
    assert "raganything_package" in keys
    assert "mineru_package" in keys
    assert "libreoffice" in keys
    assert "llm_backend" in keys
    assert "embedding_backend" in keys
    assert "llm_env" in keys
    assert "extract_env" in keys
    assert "embedding_env" in keys
    assert report["env_requirements"]["llm"]["missing"]
    assert report["env_requirements"]["extract"]["missing"]
    assert report["quick_start"]


def test_runtime_report_ready_when_core_dependencies_exist(monkeypatch):
    import app.integrations.rag.runtime_check as runtime_check

    monkeypatch.setattr(runtime_check.settings, "RAG_ENGINE", "raganything")
    monkeypatch.setattr(runtime_check.settings, "LIBREOFFICE_PATH", "soffice")
    monkeypatch.setattr(runtime_check.settings, "LLM_MODEL", "gpt-test")
    monkeypatch.setattr(runtime_check.settings, "LLM_API_BASE", "http://localhost:9000/v1")
    monkeypatch.setattr(runtime_check.settings, "OPENAI_API_BASE", "")
    monkeypatch.setattr(runtime_check.settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(runtime_check.settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(runtime_check.settings, "EXTRACT_MODEL", "extract-test")
    monkeypatch.setattr(runtime_check.settings, "EXTRACT_API_BASE", "http://localhost:9001/v1")
    monkeypatch.setattr(runtime_check.settings, "EXTRACT_API_KEY", "extract-key")
    monkeypatch.setattr(runtime_check.settings, "EXTRACT_WIRE_API", "chat_completions")
    monkeypatch.setattr(runtime_check.settings, "EMBEDDING_MODEL", "embed-test")
    monkeypatch.setattr(runtime_check.settings, "EMBEDDING_API_BASE", "http://localhost:9000/v1")
    monkeypatch.setattr(runtime_check.settings, "EMBEDDING_API_KEY", "embed-key")
    monkeypatch.setattr(
        runtime_check.model_routing_service,
        "build_runtime_model_routing_snapshot",
        lambda: {
            "generation": {"effective_backend": "api"},
            "embedding": {"effective_backend": "api"},
            "vlm": {"effective_backend": "api"},
            "reranker": {"effective_backend": "local"},
        },
    )
    monkeypatch.setattr(
        runtime_check.importlib.util,
        "find_spec",
        lambda name: ModuleSpec(name, loader=None),
    )
    monkeypatch.setattr(runtime_check.shutil, "which", lambda name: f"C:/fake/{name}.exe")

    report = build_raganything_runtime_report()

    assert report["status"] == "ready"
    assert report["blocker_count"] == 0
    assert report["recommendations"] == []
    assert report["env_requirements"]["llm"]["ready"] is True
    assert report["env_requirements"]["extract"]["ready"] is True
    assert report["env_requirements"]["embedding"]["ready"] is True
    assert report["routing"]["extraction"]["model"] == "extract-test"
    assert report["routing"]["extraction"]["api_base"] == "http://localhost:9001/v1"
    assert report["routing"]["extraction"]["uses_dedicated_extract_model"] is True


def test_runtime_report_marks_api_asr_ready_when_configured(monkeypatch):
    import app.integrations.rag.runtime_check as runtime_check

    monkeypatch.setattr(runtime_check.settings, "RAG_ENGINE", "raganything")
    monkeypatch.setattr(runtime_check.settings, "LIBREOFFICE_PATH", "soffice")
    monkeypatch.setattr(runtime_check.settings, "LLM_MODEL", "gpt-test")
    monkeypatch.setattr(runtime_check.settings, "LLM_API_BASE", "http://localhost:9000/v1")
    monkeypatch.setattr(runtime_check.settings, "OPENAI_API_BASE", "")
    monkeypatch.setattr(runtime_check.settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(runtime_check.settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(runtime_check.settings, "EMBEDDING_MODEL", "embed-test")
    monkeypatch.setattr(runtime_check.settings, "EMBEDDING_API_BASE", "http://localhost:9000/v1")
    monkeypatch.setattr(runtime_check.settings, "EMBEDDING_API_KEY", "embed-key")
    monkeypatch.setattr(runtime_check.settings, "MULTIMODAL_AUTO_PREPROCESS_ENABLED", True)
    monkeypatch.setattr(runtime_check.settings, "ASR_PROVIDER", "api")
    monkeypatch.setattr(runtime_check.settings, "ASR_MODEL", "whisper-test")
    monkeypatch.setattr(runtime_check.settings, "ASR_API_BASE", "https://asr.example/v1")
    monkeypatch.setattr(runtime_check.settings, "ASR_API_KEY", "asr-key")
    monkeypatch.setattr(runtime_check.settings, "VLM_API_BASE", "")
    monkeypatch.setattr(runtime_check.settings, "VLM_API_KEY", "")
    monkeypatch.setattr(
        runtime_check.model_routing_service,
        "build_runtime_model_routing_snapshot",
        lambda: {
            "generation": {"effective_backend": "api"},
            "embedding": {"effective_backend": "api"},
            "vlm": {"effective_backend": "mock"},
            "reranker": {"effective_backend": "api"},
        },
    )
    monkeypatch.setattr(
        runtime_check.importlib.util,
        "find_spec",
        lambda name: ModuleSpec(name, loader=None),
    )
    monkeypatch.setattr(runtime_check.shutil, "which", lambda name: f"C:/fake/{name}.exe")

    report = build_raganything_runtime_report()

    assert report["routing"]["asr"]["effective_backend"] == "api"
    assert report["routing"]["asr"]["api_base"] == "https://asr.example/v1"
    assert report["env_requirements"]["asr"]["ready"] is True
    assert report["status"] == "ready"


def test_runtime_report_blocks_when_external_storage_backend_is_incomplete(monkeypatch):
    import app.integrations.rag.runtime_check as runtime_check

    monkeypatch.setattr(runtime_check.settings, "RAG_ENGINE", "raganything")
    monkeypatch.setattr(runtime_check.settings, "LIBREOFFICE_PATH", "soffice")
    monkeypatch.setattr(runtime_check.settings, "LLM_MODEL", "gpt-test")
    monkeypatch.setattr(runtime_check.settings, "LLM_API_BASE", "http://localhost:9000/v1")
    monkeypatch.setattr(runtime_check.settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(runtime_check.settings, "EMBEDDING_MODEL", "embed-test")
    monkeypatch.setattr(runtime_check.settings, "EMBEDDING_API_BASE", "http://localhost:9000/v1")
    monkeypatch.setattr(runtime_check.settings, "EMBEDDING_API_KEY", "embed-key")
    monkeypatch.setattr(runtime_check.settings, "RAG_STORAGE_BACKEND", "qdrant-neo4j")
    monkeypatch.setattr(runtime_check.settings, "VECTOR_DB_PROVIDER", "qdrant")
    monkeypatch.setattr(runtime_check.settings, "VECTOR_DB_URL", "")
    monkeypatch.setattr(runtime_check.settings, "GRAPH_DB_PROVIDER", "neo4j")
    monkeypatch.setattr(runtime_check.settings, "GRAPH_DB_URL", "")
    monkeypatch.setattr(
        runtime_check.model_routing_service,
        "build_runtime_model_routing_snapshot",
        lambda: {
            "generation": {"effective_backend": "api"},
            "embedding": {"effective_backend": "api"},
            "vlm": {"effective_backend": "api"},
            "reranker": {"effective_backend": "api"},
        },
    )
    monkeypatch.setattr(
        runtime_check.importlib.util,
        "find_spec",
        lambda name: ModuleSpec(name, loader=None),
    )
    monkeypatch.setattr(runtime_check.shutil, "which", lambda name: f"C:/fake/{name}.exe")
    monkeypatch.setattr(
        runtime_check,
        "build_runtime_rag_storage_config_snapshot",
        lambda: build_rag_storage_config_snapshot(
            {
                "rag_storage_backend": "qdrant-neo4j",
                "vector_db_provider": "qdrant",
                "vector_db_url": "",
                "graph_db_provider": "neo4j",
                "graph_db_url": "",
            }
        ),
    )

    report = build_raganything_runtime_report()

    assert report["status"] == "blocked"
    keys = {item["key"] for item in report["blockers"]}
    assert "vector_db" in keys
    assert "graph_db" in keys
    assert report["storage"]["requested_backend"] == "qdrant-neo4j"


def test_runtime_report_blocks_when_external_storage_is_unreachable(monkeypatch):
    import app.integrations.rag.runtime_check as runtime_check

    monkeypatch.setattr(runtime_check.settings, "RAG_ENGINE", "raganything")
    monkeypatch.setattr(runtime_check.settings, "LIBREOFFICE_PATH", "soffice")
    monkeypatch.setattr(runtime_check.settings, "LLM_MODEL", "gpt-test")
    monkeypatch.setattr(runtime_check.settings, "LLM_API_BASE", "http://localhost:9000/v1")
    monkeypatch.setattr(runtime_check.settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(runtime_check.settings, "EMBEDDING_MODEL", "embed-test")
    monkeypatch.setattr(runtime_check.settings, "EMBEDDING_API_BASE", "http://localhost:9000/v1")
    monkeypatch.setattr(runtime_check.settings, "EMBEDDING_API_KEY", "embed-key")
    monkeypatch.setattr(
        runtime_check.model_routing_service,
        "build_runtime_model_routing_snapshot",
        lambda: {
            "generation": {"effective_backend": "api"},
            "embedding": {"effective_backend": "api"},
            "vlm": {"effective_backend": "api"},
            "reranker": {"effective_backend": "api"},
        },
    )
    monkeypatch.setattr(
        runtime_check.importlib.util,
        "find_spec",
        lambda name: ModuleSpec(name, loader=None),
    )
    monkeypatch.setattr(runtime_check.shutil, "which", lambda name: f"C:/fake/{name}.exe")
    monkeypatch.setattr(
        runtime_check,
        "build_runtime_rag_storage_config_snapshot",
        lambda: {
            "requested_backend": "qdrant-neo4j",
            "effective_backend": "unavailable",
            "activation_state": "external_config_ready",
            "external_configured": True,
            "external_ready": False,
            "supports_external_vector": True,
            "supports_external_graph": True,
            "vector_db": {
                "configured": True,
                "provider": "qdrant",
                "config_ready": True,
                "ready": False,
                "connectivity": {
                    "attempted": True,
                    "reachable": False,
                    "protocol": "http",
                    "latency_ms": None,
                    "detail": "connection refused",
                },
            },
            "graph_db": {
                "configured": True,
                "provider": "neo4j",
                "config_ready": True,
                "ready": False,
                "connectivity": {
                    "attempted": True,
                    "reachable": False,
                    "protocol": "bolt",
                    "latency_ms": None,
                    "detail": "auth failed",
                },
            },
            "working_dir": {"path": "E:/tmp/rag_storage", "exists": True},
            "output_dir": {"path": "E:/tmp/rag_output", "exists": True},
            "note": "External storage configured but unreachable.",
        },
    )

    report = build_raganything_runtime_report()

    assert report["status"] == "blocked"
    keys = {item["key"] for item in report["blockers"]}
    assert "vector_db_connectivity" in keys
    assert "graph_db_connectivity" in keys
    assert any("docker-compose.rag-storage.yml" in item for item in report["recommendations"])
