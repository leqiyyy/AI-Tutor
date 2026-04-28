from __future__ import annotations

import importlib.util
import re
import socket
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.admin import AdminSetting


ALLOWED_RAG_STORAGE_BACKENDS = {
    "lightrag-default",
    "qdrant",
    "neo4j",
    "qdrant-neo4j",
}

DEFAULT_KV_STORAGE = "JsonKVStorage"
DEFAULT_VECTOR_STORAGE = "NanoVectorDBStorage"
DEFAULT_GRAPH_STORAGE = "NetworkXStorage"
DEFAULT_DOC_STATUS_STORAGE = "JsonDocStatusStorage"
DEFAULT_DOCKER_COMPOSE_FILE = "backend/deploy/docker-compose.rag-storage.yml"


def load_persisted_rag_storage_config() -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.query(AdminSetting).filter(AdminSetting.section == "rag_storage_config").all()
    return {row.key: row.value for row in rows}


def build_runtime_rag_storage_config_snapshot() -> dict[str, Any]:
    try:
        persisted = load_persisted_rag_storage_config()
    except Exception:
        persisted = {}
    return build_rag_storage_config_snapshot(persisted, include_connectivity=True)


def build_rag_storage_config_snapshot(
    overrides: dict[str, Any] | None = None,
    *,
    include_connectivity: bool = False,
) -> dict[str, Any]:
    config = dict(overrides or {})
    requested_backend = _normalize_storage_backend(_cfg(config, "rag_storage_backend", settings.RAG_STORAGE_BACKEND))
    vector_db = _build_vector_db_snapshot(config, include_connectivity=include_connectivity)
    graph_db = _build_graph_db_snapshot(config, include_connectivity=include_connectivity)

    supports_external_vector = requested_backend in {"qdrant", "qdrant-neo4j"}
    supports_external_graph = requested_backend in {"neo4j", "qdrant-neo4j"}
    external_vector_ready = (not supports_external_vector) or vector_db["ready"]
    external_graph_ready = (not supports_external_graph) or graph_db["ready"]
    external_configured = bool(vector_db["configured"] or graph_db["configured"])

    effective_backend = _resolve_effective_backend(
        requested_backend=requested_backend,
        external_vector_ready=external_vector_ready,
        external_graph_ready=external_graph_ready,
    )

    if requested_backend == "lightrag-default":
        activation_state = "local_only"
    elif effective_backend != "unavailable":
        activation_state = "external_config_ready"
    else:
        activation_state = "external_config_incomplete"

    working_dir = Path(settings.RAGANYTHING_WORKING_DIR)
    output_dir = Path(settings.RAGANYTHING_OUTPUT_DIR)
    if not working_dir.is_absolute():
        working_dir = (Path(settings.LOCAL_STORAGE_ROOT).parents[0] / working_dir).resolve()
    if not output_dir.is_absolute():
        output_dir = (Path(settings.LOCAL_STORAGE_ROOT).parents[0] / output_dir).resolve()

    return {
        "requested_backend": requested_backend,
        "effective_backend": effective_backend,
        "activation_state": activation_state,
        "external_configured": external_configured,
        "external_ready": external_vector_ready and external_graph_ready,
        "supports_external_vector": supports_external_vector,
        "supports_external_graph": supports_external_graph,
        "vector_db": vector_db,
        "graph_db": graph_db,
        "working_dir": {"path": str(working_dir), "exists": working_dir.exists()},
        "output_dir": {"path": str(output_dir), "exists": output_dir.exists()},
        "note": _build_storage_note(
            requested_backend=requested_backend,
            effective_backend=effective_backend,
        ),
    }


def build_lightrag_storage_plan(
    class_id: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = dict(overrides or {})
    snapshot = build_rag_storage_config_snapshot(config)
    requested_backend = snapshot["requested_backend"]
    effective_backend = snapshot["effective_backend"]
    vector_url = str(_cfg(config, "vector_db_url", settings.VECTOR_DB_URL) or "").strip()
    vector_api_key = str(_cfg(config, "vector_db_api_key", getattr(settings, "VECTOR_DB_API_KEY", "")) or "").strip()
    vector_collection = str(
        _cfg(
            config,
            "vector_db_collection",
            getattr(settings, "VECTOR_DB_COLLECTION", "raganything_chunks"),
        )
        or "raganything_chunks"
    ).strip()
    graph_url = str(_cfg(config, "graph_db_url", settings.GRAPH_DB_URL) or "").strip()
    graph_database = str(
        _cfg(
            config,
            "graph_db_database",
            getattr(settings, "GRAPH_DB_DATABASE", ""),
        )
        or ""
    ).strip()
    graph_username = str(
        _cfg(
            config,
            "graph_db_username",
            getattr(settings, "GRAPH_DB_USERNAME", ""),
        )
        or ""
    ).strip()
    graph_password = str(
        _cfg(
            config,
            "graph_db_password",
            getattr(settings, "GRAPH_DB_PASSWORD", ""),
        )
        or ""
    ).strip()
    workspace = _build_lightrag_workspace(class_id, requested_backend, vector_collection)
    lightrag_kwargs = {
        "kv_storage": DEFAULT_KV_STORAGE,
        "vector_storage": DEFAULT_VECTOR_STORAGE,
        "graph_storage": DEFAULT_GRAPH_STORAGE,
        "doc_status_storage": DEFAULT_DOC_STATUS_STORAGE,
        "workspace": workspace,
    }
    env_overrides: dict[str, str] = {}

    if requested_backend != "lightrag-default" and effective_backend == "unavailable":
        raise RuntimeError(
            "Requested external RAG storage is not ready. Complete Qdrant/Neo4j configuration before indexing."
        )

    if effective_backend in {"qdrant", "qdrant-neo4j"}:
        lightrag_kwargs["vector_storage"] = "QdrantVectorDBStorage"
        env_overrides["QDRANT_URL"] = vector_url
        if vector_api_key:
            env_overrides["QDRANT_API_KEY"] = vector_api_key

    if effective_backend in {"neo4j", "qdrant-neo4j"}:
        lightrag_kwargs["graph_storage"] = "Neo4JStorage"
        env_overrides["NEO4J_URI"] = graph_url
        if graph_database:
            env_overrides["NEO4J_DATABASE"] = graph_database
        if graph_username:
            env_overrides["NEO4J_USERNAME"] = graph_username
        if graph_password:
            env_overrides["NEO4J_PASSWORD"] = graph_password

    return {
        "requested_backend": requested_backend,
        "effective_backend": effective_backend,
        "workspace": workspace,
        "vector_db": snapshot["vector_db"],
        "graph_db": snapshot["graph_db"],
        "lightrag_kwargs": lightrag_kwargs,
        "env_overrides": env_overrides,
        "note": (
            "Uses official LightRAG storage adapters. Qdrant physical collections remain "
            "upstream-managed; VECTOR_DB_COLLECTION is applied as a logical workspace prefix."
        ),
    }


def build_external_storage_bootstrap_plan(target_backend: str = "qdrant-neo4j") -> dict[str, Any]:
    requested_backend = _normalize_storage_backend(target_backend)
    if requested_backend == "lightrag-default":
        requested_backend = "qdrant-neo4j"

    vector_enabled = requested_backend in {"qdrant", "qdrant-neo4j"}
    graph_enabled = requested_backend in {"neo4j", "qdrant-neo4j"}
    vector_provider = "qdrant" if vector_enabled else "auto"
    graph_provider = "neo4j" if graph_enabled else "auto"
    vector_url = str(getattr(settings, "VECTOR_DB_URL", "") or "http://localhost:6333").strip()
    graph_url = str(getattr(settings, "GRAPH_DB_URL", "") or "bolt://localhost:7687").strip()
    graph_database = str(getattr(settings, "GRAPH_DB_DATABASE", "") or "").strip()
    graph_username = str(getattr(settings, "GRAPH_DB_USERNAME", "neo4j") or "neo4j").strip()
    vector_collection = str(getattr(settings, "VECTOR_DB_COLLECTION", "raganything_chunks") or "raganything_chunks").strip()

    install_packages: list[str] = []
    if vector_enabled and not _package_available("qdrant_client"):
        install_packages.append("qdrant-client>=1.10.0")
    if graph_enabled and not _package_available("neo4j"):
        install_packages.append("neo4j>=5.20.0")

    env_patch = {
        "RAG_STORAGE_BACKEND": requested_backend,
        "VECTOR_DB_PROVIDER": vector_provider,
        "VECTOR_DB_URL": vector_url if vector_enabled else "",
        "VECTOR_DB_API_KEY": str(getattr(settings, "VECTOR_DB_API_KEY", "") or "").strip(),
        "VECTOR_DB_COLLECTION": vector_collection if vector_enabled else "",
        "GRAPH_DB_PROVIDER": graph_provider,
        "GRAPH_DB_URL": graph_url if graph_enabled else "",
        "GRAPH_DB_DATABASE": graph_database if graph_enabled else "",
        "GRAPH_DB_USERNAME": graph_username if graph_enabled else "",
        "GRAPH_DB_PASSWORD": str(getattr(settings, "GRAPH_DB_PASSWORD", "") or "").strip(),
    }
    env_lines = [f"{key}={value}" for key, value in env_patch.items()]

    next_steps = [
        f"Start external services: `docker compose -f {DEFAULT_DOCKER_COMPOSE_FILE} up -d`",
        "Install optional backend dependencies if missing: `python -m pip install -r backend/requirements-raganything.txt`",
        "Apply the generated env block to `backend/.env` or the admin rag-storage config API.",
        "Run `python backend/scripts/check_raganything_runtime.py` and confirm storage blockers are gone.",
    ]
    if requested_backend == "qdrant-neo4j":
        next_steps.append("Switch one course/class to re-index under the new backend and validate `/api/v1/admin/rag-system-status`.")

    return {
        "target_backend": requested_backend,
        "docker_compose_file": DEFAULT_DOCKER_COMPOSE_FILE,
        "install_packages": install_packages,
        "env_patch": env_patch,
        "env_block": "\n".join(env_lines),
        "next_steps": next_steps,
    }


def _build_vector_db_snapshot(config: dict[str, Any], *, include_connectivity: bool = False) -> dict[str, Any]:
    vector_url = str(_cfg(config, "vector_db_url", settings.VECTOR_DB_URL) or "")
    provider = _normalize_provider(_cfg(config, "vector_db_provider", getattr(settings, "VECTOR_DB_PROVIDER", "auto")), _infer_vector_provider(vector_url))
    package_name = _vector_provider_package(provider)
    package_available = _package_available(package_name) if package_name else True
    parsed = _parse_url(vector_url)
    collection = str(_cfg(config, "vector_db_collection", getattr(settings, "VECTOR_DB_COLLECTION", "raganything_chunks")) or "raganything_chunks").strip()
    api_key = str(_cfg(config, "vector_db_api_key", getattr(settings, "VECTOR_DB_API_KEY", "")) or "").strip()
    api_key_configured = bool(api_key)
    configured = bool(vector_url)
    config_ready = configured and provider != "unknown" and package_available
    connectivity = (
        _probe_vector_connectivity(
            url=vector_url,
            provider=provider,
            api_key=api_key,
        )
        if include_connectivity and configured and provider != "unknown"
        else _connectivity_not_checked()
    )
    return {
        "configured": configured,
        "provider": provider,
        "url_present": configured,
        "url_preview": _mask_url(vector_url),
        "scheme": parsed.get("scheme"),
        "host": parsed.get("host"),
        "port": parsed.get("port"),
        "collection": collection,
        "api_key_configured": api_key_configured,
        "package_name": package_name,
        "package_available": package_available,
        "config_ready": config_ready,
        "connectivity": connectivity,
        "ready": config_ready and (not include_connectivity or connectivity.get("reachable", False)),
    }


def _build_graph_db_snapshot(config: dict[str, Any], *, include_connectivity: bool = False) -> dict[str, Any]:
    graph_url = str(_cfg(config, "graph_db_url", settings.GRAPH_DB_URL) or "")
    provider = _normalize_provider(_cfg(config, "graph_db_provider", getattr(settings, "GRAPH_DB_PROVIDER", "auto")), _infer_graph_provider(graph_url))
    package_name = _graph_provider_package(provider)
    package_available = _package_available(package_name) if package_name else True
    parsed = _parse_url(graph_url)
    database = str(_cfg(config, "graph_db_database", getattr(settings, "GRAPH_DB_DATABASE", "")) or "").strip()
    username = str(_cfg(config, "graph_db_username", getattr(settings, "GRAPH_DB_USERNAME", "")) or "").strip()
    password = str(_cfg(config, "graph_db_password", getattr(settings, "GRAPH_DB_PASSWORD", "")) or "").strip()
    password_configured = bool(password)
    configured = bool(graph_url)
    config_ready = configured and provider != "unknown" and package_available
    connectivity = (
        _probe_graph_connectivity(
            url=graph_url,
            provider=provider,
            username=username,
            password=password,
            package_available=package_available,
        )
        if include_connectivity and configured and provider != "unknown"
        else _connectivity_not_checked()
    )
    return {
        "configured": configured,
        "provider": provider,
        "url_present": configured,
        "url_preview": _mask_url(graph_url),
        "scheme": parsed.get("scheme"),
        "host": parsed.get("host"),
        "port": parsed.get("port"),
        "database": database,
        "username_present": bool(username),
        "password_configured": password_configured,
        "package_name": package_name,
        "package_available": package_available,
        "config_ready": config_ready,
        "connectivity": connectivity,
        "ready": config_ready and (not include_connectivity or connectivity.get("reachable", False)),
    }


def _resolve_effective_backend(
    *,
    requested_backend: str,
    external_vector_ready: bool,
    external_graph_ready: bool,
) -> str:
    if requested_backend == "lightrag-default":
        return "lightrag-default"
    if external_vector_ready and external_graph_ready:
        return requested_backend
    return "unavailable"


def _build_storage_note(*, requested_backend: str, effective_backend: str) -> str:
    if requested_backend == "lightrag-default":
        return (
            "RAG-Anything uses local LightRAG storage under working_dir "
            "(NanoVectorDBStorage + NetworkXStorage)."
        )
    if effective_backend == "unavailable":
        return (
            "External storage was requested, but Qdrant/Neo4j is not ready. "
            "The adapter will raise instead of silently falling back to local storage."
        )
    return (
        "RAG-Anything will activate the official LightRAG external storage adapters "
        "for the configured Qdrant / Neo4j topology."
    )


def _build_lightrag_workspace(class_id: str, requested_backend: str, vector_collection: str) -> str:
    class_token = _workspace_token(class_id)
    if requested_backend in {"qdrant", "qdrant-neo4j"}:
        collection_token = _workspace_token(vector_collection)
        if collection_token and collection_token != "raganything_chunks":
            return f"{collection_token}__{class_token}"
    return class_token


def _workspace_token(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
    return normalized or "default"


def _normalize_storage_backend(value: Any) -> str:
    normalized = str(value or "lightrag-default").strip().lower()
    if normalized not in ALLOWED_RAG_STORAGE_BACKENDS:
        return "lightrag-default"
    return normalized


def _normalize_provider(value: Any, inferred: str) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized in {"", "auto"}:
        return inferred
    return normalized


def _infer_vector_provider(url: str) -> str:
    if not url:
        return "unknown"
    parsed = urlparse(str(url))
    if parsed.scheme in {"http", "https", "grpc"}:
        return "qdrant"
    return "unknown"


def _infer_graph_provider(url: str) -> str:
    if not url:
        return "unknown"
    parsed = urlparse(str(url))
    if parsed.scheme in {"neo4j", "neo4j+s", "neo4j+ssc", "bolt", "bolt+s", "bolt+ssc"}:
        return "neo4j"
    return "unknown"


def _vector_provider_package(provider: str) -> str | None:
    if provider == "qdrant":
        return "qdrant_client"
    return None


def _graph_provider_package(provider: str) -> str | None:
    if provider == "neo4j":
        return "neo4j"
    return None


def _package_available(name: str | None) -> bool:
    if not name:
        return True
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _connectivity_not_checked() -> dict[str, Any]:
    return {
        "attempted": False,
        "reachable": False,
        "protocol": None,
        "latency_ms": None,
        "detail": "not_checked",
    }


def _probe_vector_connectivity(*, url: str, provider: str, api_key: str) -> dict[str, Any]:
    parsed = urlparse(str(url))
    scheme = (parsed.scheme or "").lower()
    if provider == "qdrant" and scheme in {"http", "https"}:
        endpoint = str(url).rstrip("/") + "/collections"
        headers = {"api-key": api_key} if api_key else {}
        started = time.perf_counter()
        try:
            response = httpx.get(endpoint, headers=headers, timeout=2.5, follow_redirects=True)
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            reachable = response.status_code == 200
            return {
                "attempted": True,
                "reachable": reachable,
                "protocol": scheme,
                "latency_ms": latency_ms,
                "detail": "ok" if reachable else f"http_{response.status_code}",
            }
        except Exception as exc:
            return {
                "attempted": True,
                "reachable": False,
                "protocol": scheme,
                "latency_ms": None,
                "detail": str(exc),
            }
    return _probe_tcp_connectivity(
        host=parsed.hostname,
        port=parsed.port or 6333,
        protocol=scheme or "tcp",
    )


def _probe_graph_connectivity(
    *,
    url: str,
    provider: str,
    username: str,
    password: str,
    package_available: bool,
) -> dict[str, Any]:
    parsed = urlparse(str(url))
    scheme = (parsed.scheme or "").lower()
    if provider == "neo4j" and package_available:
        driver = None
        started = time.perf_counter()
        try:
            from neo4j import GraphDatabase

            auth = (username, password) if username or password else None
            driver = GraphDatabase.driver(url, auth=auth)
            driver.verify_connectivity()
            server_info = driver.get_server_info()
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            detail = getattr(server_info, "agent", None) or "ok"
            return {
                "attempted": True,
                "reachable": True,
                "protocol": scheme or "bolt",
                "latency_ms": latency_ms,
                "detail": str(detail),
            }
        except Exception as exc:
            return {
                "attempted": True,
                "reachable": False,
                "protocol": scheme or "bolt",
                "latency_ms": None,
                "detail": str(exc),
            }
        finally:
            if driver is not None:
                try:
                    driver.close()
                except Exception:
                    pass
    return _probe_tcp_connectivity(
        host=parsed.hostname,
        port=parsed.port or 7687,
        protocol=scheme or "bolt",
    )


def _probe_tcp_connectivity(*, host: str | None, port: int | None, protocol: str) -> dict[str, Any]:
    if not host or not port:
        return {
            "attempted": False,
            "reachable": False,
            "protocol": protocol,
            "latency_ms": None,
            "detail": "missing_host_or_port",
        }
    started = time.perf_counter()
    try:
        with socket.create_connection((host, int(port)), timeout=2.5):
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            return {
                "attempted": True,
                "reachable": True,
                "protocol": protocol,
                "latency_ms": latency_ms,
                "detail": "tcp_ok",
            }
    except Exception as exc:
        return {
            "attempted": True,
            "reachable": False,
            "protocol": protocol,
            "latency_ms": None,
            "detail": str(exc),
        }


def _parse_url(url: str) -> dict[str, Any]:
    if not url:
        return {"scheme": None, "host": None, "port": None}
    parsed = urlparse(str(url))
    return {
        "scheme": parsed.scheme or None,
        "host": parsed.hostname or None,
        "port": parsed.port,
    }


def _mask_url(url: str) -> str:
    if not url:
        return ""
    text = str(url)
    if "@" in text:
        prefix, suffix = text.rsplit("@", 1)
        scheme = prefix.split("://", 1)[0] if "://" in prefix else "url"
        return f"{scheme}://***@{suffix}"
    return text


def _cfg(config: dict[str, Any], key: str, default: Any) -> Any:
    value = config.get(key)
    return default if value is None else value
