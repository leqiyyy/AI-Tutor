from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.integrations.rag.storage_config import build_runtime_rag_storage_config_snapshot
from app.services import model_routing_service


def build_raganything_runtime_report() -> dict[str, Any]:
    routing = model_routing_service.build_runtime_model_routing_snapshot()
    routing["extraction"] = _build_extraction_route()
    routing["asr"] = _build_asr_route()
    storage = build_runtime_rag_storage_config_snapshot()
    env_requirements = _build_env_requirements(routing)
    dependencies = {
        "packages": {
            "raganything": _package_snapshot("raganything"),
            "mineru": _package_snapshot("mineru"),
            "faster_whisper": _package_snapshot("faster_whisper"),
            "qdrant_client": _package_snapshot("qdrant_client"),
            "neo4j": _package_snapshot("neo4j"),
        },
        "binaries": {
            "libreoffice": _binary_snapshot(settings.LIBREOFFICE_PATH),
            "ffmpeg": _binary_snapshot(settings.MULTIMODAL_FFMPEG_PATH),
            "ffprobe": _binary_snapshot(settings.MULTIMODAL_FFPROBE_PATH),
            "mineru": _binary_snapshot("mineru"),
        },
    }
    paths = {
        "rag_working_dir": _path_snapshot(settings.RAGANYTHING_WORKING_DIR),
        "rag_output_dir": _path_snapshot(settings.RAGANYTHING_OUTPUT_DIR),
        "multimodal_preprocess_dir": _path_snapshot(settings.MULTIMODAL_PREPROCESS_OUTPUT_DIR),
    }
    config = {
        "rag_engine": settings.RAG_ENGINE,
        "strict_mode": settings.RAGANYTHING_STRICT_MODE,
        "metadata_fallback_enabled": settings.RAGANYTHING_METADATA_FALLBACK_ENABLED,
        "require_official_metadata": settings.RAGANYTHING_REQUIRE_OFFICIAL_METADATA,
        "parser": settings.RAGANYTHING_PARSER,
        "parse_method": settings.RAGANYTHING_PARSE_METHOD,
        "query_mode": settings.RAGANYTHING_QUERY_MODE,
        "default_llm_timeout_seconds": settings.RAGANYTHING_DEFAULT_LLM_TIMEOUT_SECONDS,
        "storage_backend": settings.RAG_STORAGE_BACKEND,
        "vector_db_configured": bool(settings.VECTOR_DB_URL),
        "graph_db_configured": bool(settings.GRAPH_DB_URL),
        "external_storage_activation_state": storage["activation_state"],
        "multimodal_auto_preprocess_enabled": settings.MULTIMODAL_AUTO_PREPROCESS_ENABLED,
        "asr_provider": settings.ASR_PROVIDER,
        "asr_api_base_configured": bool(settings.EFFECTIVE_ASR_API_BASE),
        "asr_api_key_configured": bool(settings.EFFECTIVE_ASR_API_KEY),
    }
    blockers = _build_blockers(
        dependencies=dependencies,
        routing=routing,
        config=config,
        env_requirements=env_requirements,
        storage=storage,
    )
    return {
        "status": "ready" if not blockers else "blocked",
        "blocker_count": len(blockers),
        "blockers": blockers,
        "config": config,
        "routing": routing,
        "env_requirements": env_requirements,
        "dependencies": dependencies,
        "storage": storage,
        "paths": paths,
        "recommendations": _build_recommendations(blockers),
        "quick_start": _build_quick_start(),
    }


def _build_blockers(
    *,
    dependencies: dict[str, Any],
    routing: dict[str, Any],
    config: dict[str, Any],
    env_requirements: dict[str, Any],
    storage: dict[str, Any],
) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    packages = dependencies["packages"]
    binaries = dependencies["binaries"]
    generation = routing.get("generation") or {}
    embedding = routing.get("embedding") or {}
    asr = routing.get("asr") or {}
    vector_db = storage.get("vector_db") or {}
    graph_db = storage.get("graph_db") or {}

    if config["rag_engine"] != "raganything":
        blockers.append(_blocker("rag_engine", "RAG_ENGINE must be `raganything`."))
    if not packages["raganything"]["available"]:
        blockers.append(_blocker("raganything_package", "Python package `raganything` is not installed."))
    if not packages["mineru"]["available"]:
        blockers.append(_blocker("mineru_package", "Python package `mineru` is not installed."))
    if not binaries["libreoffice"]["available"]:
        blockers.append(_blocker("libreoffice", "LibreOffice executable is not configured or not reachable."))
    if str(config.get("parser") or "").lower() == "mineru" and not binaries["mineru"]["available"]:
        blockers.append(_blocker("mineru_cli", "MinerU CLI is not reachable from PATH or the current Python environment."))
    if generation.get("effective_backend") == "mock":
        blockers.append(_blocker("llm_backend", "Generation backend is still `mock`; configure a real API/local model."))
    if embedding.get("effective_backend") == "mock":
        blockers.append(_blocker("embedding_backend", "Embedding backend is still `mock`; configure a real API/local model."))
    if storage.get("supports_external_vector") and not vector_db.get("config_ready"):
        blockers.append(_blocker("vector_db", "RAG_STORAGE_BACKEND expects an external vector database, but VECTOR_DB configuration is incomplete."))
    elif storage.get("supports_external_vector") and (vector_db.get("connectivity") or {}).get("attempted") and not (vector_db.get("connectivity") or {}).get("reachable"):
        blockers.append(_blocker("vector_db_connectivity", f"Qdrant is configured but unreachable: {(vector_db.get('connectivity') or {}).get('detail') or 'unknown error'}.")) 
    if storage.get("supports_external_graph") and not graph_db.get("config_ready"):
        blockers.append(_blocker("graph_db", "RAG_STORAGE_BACKEND expects an external graph database, but GRAPH_DB configuration is incomplete."))
    elif storage.get("supports_external_graph") and (graph_db.get("connectivity") or {}).get("attempted") and not (graph_db.get("connectivity") or {}).get("reachable"):
        blockers.append(_blocker("graph_db_connectivity", f"Neo4j is configured but unreachable: {(graph_db.get('connectivity') or {}).get('detail') or 'unknown error'}.")) 
    if config.get("multimodal_auto_preprocess_enabled"):
        if str(config.get("asr_provider") or "").lower() == "faster_whisper" and not packages["faster_whisper"]["available"]:
            blockers.append(_blocker("asr_provider", "ASR provider `faster_whisper` is enabled but the package is not installed."))
        if asr.get("effective_backend") == "api":
            missing = (env_requirements.get("asr") or {}).get("missing") or []
            if missing:
                blockers.append(
                    _blocker(
                        "asr_env",
                        f"Missing required ASR environment variables: {', '.join(missing)}.",
                    )
                )
    for scope, payload in env_requirements.items():
        if scope == "asr":
            continue
        missing = payload.get("missing") or []
        if missing:
            blockers.append(
                _blocker(
                    f"{scope}_env",
                    f"Missing required {scope} environment variables: {', '.join(missing)}.",
                )
            )
    return blockers


def _build_recommendations(blockers: list[dict[str, str]]) -> list[str]:
    recommendations: list[str] = []
    for blocker in blockers:
        key = blocker["key"]
        if key == "raganything_package":
            recommendations.append("Install `backend/requirements-raganything.txt` into the backend Python environment.")
        elif key == "mineru_package":
            recommendations.append("Install MinerU and verify the parser environment used by RAG-Anything.")
        elif key == "mineru_cli":
            recommendations.append("Ensure the current Python environment exposes `mineru` on PATH, or run the backend with the same Conda environment activated.")
        elif key == "libreoffice":
            recommendations.append("Set `LIBREOFFICE_PATH` to `soffice.exe` and verify the file exists.")
        elif key == "llm_backend":
            recommendations.append("Configure `LLM_API_KEY`, `LLM_API_BASE`, and `LLM_MODEL` for real answer generation.")
        elif key == "embedding_backend":
            recommendations.append("Configure `EMBEDDING_API_KEY`, `EMBEDDING_API_BASE`, and `EMBEDDING_MODEL`.")
        elif key == "rag_engine":
            recommendations.append("Keep `RAG_ENGINE=raganything`; the backend no longer supports a Simple fallback.")
        elif key == "llm_env":
            recommendations.append("Fill in the missing LLM variables in `backend/.env` based on `backend/.env.example`.")
        elif key == "extract_env":
            recommendations.append("Configure `EXTRACT_MODEL`, `EXTRACT_API_BASE`, and `EXTRACT_API_KEY`, or let them inherit a working LLM route.")
        elif key == "embedding_env":
            recommendations.append("Fill in the missing embedding variables in `backend/.env` based on `backend/.env.example`.")
        elif key == "vlm_env":
            recommendations.append("If you need image understanding, fill in the missing VLM variables in `backend/.env`.")
        elif key == "asr_provider":
            recommendations.append("Install `faster-whisper` in the backend environment, or switch `ASR_PROVIDER` to `api` and configure an ASR API route.")
        elif key == "asr_env":
            recommendations.append("Fill in `ASR_API_BASE`, `ASR_API_KEY`, and `ASR_MODEL` for API-based automatic audio/video transcription.")
        elif key == "vector_db":
            recommendations.append("For Qdrant-backed storage, set `RAG_STORAGE_BACKEND=qdrant` or `qdrant-neo4j`, then fill in `VECTOR_DB_PROVIDER`, `VECTOR_DB_URL`, and optional `VECTOR_DB_API_KEY` / `VECTOR_DB_COLLECTION`.")
        elif key == "vector_db_connectivity":
            recommendations.append("Start Qdrant and verify the URL/API key. You can use `backend/deploy/docker-compose.rag-storage.yml` as a local bootstrap template.")
        elif key == "graph_db":
            recommendations.append("For Neo4j-backed graph storage, set `RAG_STORAGE_BACKEND=neo4j` or `qdrant-neo4j`, then fill in `GRAPH_DB_PROVIDER`, `GRAPH_DB_URL`, `GRAPH_DB_DATABASE`, and optional credentials.")
        elif key == "graph_db_connectivity":
            recommendations.append("Start Neo4j and verify the Bolt URL and credentials. You can use `backend/deploy/docker-compose.rag-storage.yml` as a local bootstrap template.")
    return recommendations


def _build_env_requirements(routing: dict[str, Any]) -> dict[str, Any]:
    generation = routing.get("generation") or {}
    embedding = routing.get("embedding") or {}
    vlm = routing.get("vlm") or {}
    return {
        "llm": _env_scope(
            backend=generation.get("effective_backend"),
            required={
                "LLM_MODEL": bool(settings.LLM_MODEL),
                "LLM_API_BASE": bool(settings.LLM_API_BASE or settings.OPENAI_API_BASE),
                "LLM_API_KEY": bool(settings.LLM_API_KEY or settings.OPENAI_API_KEY),
            },
        ),
        "embedding": _env_scope(
            backend=embedding.get("effective_backend"),
            required={
                "EMBEDDING_MODEL": bool(settings.EMBEDDING_MODEL),
                "EMBEDDING_API_BASE": bool(settings.EMBEDDING_API_BASE or settings.OPENAI_API_BASE or settings.LLM_API_BASE),
                "EMBEDDING_API_KEY": bool(settings.EMBEDDING_API_KEY or settings.OPENAI_API_KEY),
            },
        ),
        "extract": _env_scope(
            backend=generation.get("effective_backend"),
            required={
                "EXTRACT_MODEL_OR_LLM_MODEL": bool(settings.EFFECTIVE_EXTRACT_MODEL),
                "EXTRACT_API_BASE_OR_LLM_API_BASE": bool(settings.EFFECTIVE_EXTRACT_API_BASE),
                "EXTRACT_API_KEY_OR_LLM_API_KEY": bool(settings.EFFECTIVE_EXTRACT_API_KEY),
            },
        ),
        "vlm": _env_scope(
            backend=vlm.get("effective_backend"),
            required={
                "VLM_MODEL": bool(settings.VLM_MODEL or settings.LLM_MODEL),
                "VLM_API_BASE": bool(settings.VLM_API_BASE or settings.LLM_API_BASE or settings.OPENAI_API_BASE),
                "VLM_API_KEY": bool(settings.VLM_API_KEY or settings.LLM_API_KEY or settings.OPENAI_API_KEY),
            },
            optional=True,
        ),
        "asr": _env_scope(
            backend=(routing.get("asr") or {}).get("effective_backend"),
            required={
                "ASR_MODEL": bool(settings.ASR_MODEL),
                "ASR_API_BASE": bool(settings.EFFECTIVE_ASR_API_BASE),
                "ASR_API_KEY": bool(settings.EFFECTIVE_ASR_API_KEY),
            },
            optional=True,
        ),
    }


def _build_extraction_route() -> dict[str, Any]:
    return {
        "requested_backend": settings.LLM_BACKEND,
        "effective_backend": "api" if settings.EFFECTIVE_EXTRACT_API_KEY else "mock",
        "provider": "openai-compatible-extraction",
        "model": settings.EFFECTIVE_EXTRACT_MODEL,
        "api_base": settings.EFFECTIVE_EXTRACT_API_BASE,
        "wire_api": settings.EXTRACT_WIRE_API,
        "api_key_configured": bool(settings.EFFECTIVE_EXTRACT_API_KEY),
        "uses_dedicated_extract_model": bool(settings.EXTRACT_MODEL),
        "uses_dedicated_extract_base": bool(settings.EXTRACT_API_BASE),
    }


def _build_asr_route() -> dict[str, Any]:
    provider = (settings.ASR_PROVIDER or "none").strip().lower()
    if provider == "faster_whisper":
        return {
            "requested_backend": "local",
            "effective_backend": "local",
            "provider": "faster_whisper",
            "model": settings.ASR_MODEL,
            "api_base": None,
            "api_key_configured": False,
        }
    if provider in {"api", "openai", "openai_compatible"}:
        return {
            "requested_backend": "api",
            "effective_backend": "api",
            "provider": "openai-compatible-asr",
            "model": settings.ASR_MODEL,
            "api_base": settings.EFFECTIVE_ASR_API_BASE,
            "api_key_configured": bool(settings.EFFECTIVE_ASR_API_KEY),
        }
    return {
        "requested_backend": "disabled",
        "effective_backend": "disabled",
        "provider": provider or "none",
        "model": settings.ASR_MODEL,
        "api_base": settings.EFFECTIVE_ASR_API_BASE or None,
        "api_key_configured": bool(settings.EFFECTIVE_ASR_API_KEY),
    }


def _env_scope(*, backend: str | None, required: dict[str, bool], optional: bool = False) -> dict[str, Any]:
    missing = [key for key, ok in required.items() if not ok]
    return {
        "backend": backend or "unknown",
        "optional": optional,
        "required": sorted(required.keys()),
        "missing": missing,
        "ready": not missing,
    }


def _build_quick_start() -> list[str]:
    return [
        "Install dependencies: `python -m pip install -r requirements.txt -r requirements-raganything.txt`",
        "Configure `backend/.env` from `backend/.env.example` and keep `RAG_ENGINE=raganything`",
        "Run `python scripts/check_raganything_runtime.py` until status becomes `ready`",
        "Start the API with `uvicorn app.main:app --reload`",
        "Use `/api/v1/admin/rag-system-status` to verify runtime status inside the app",
    ]


def _package_snapshot(name: str) -> dict[str, Any]:
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ModuleNotFoundError, ValueError):
        spec = None
    return {
        "name": name,
        "available": spec is not None,
        "origin": getattr(spec, "origin", None) if spec else None,
    }


def _binary_snapshot(path_or_name: str) -> dict[str, Any]:
    configured = str(path_or_name or "").strip()
    if not configured:
        return {"configured": False, "available": False, "resolved": ""}
    resolved = shutil.which(configured)
    if not resolved:
        python_dir = Path(sys.executable).resolve().parent
        env_candidates = []
        if os.name == "nt":
            env_candidates.extend([
                python_dir / f"{configured}.exe",
                python_dir / "Scripts" / f"{configured}.exe",
                python_dir / configured,
                python_dir / "Scripts" / configured,
            ])
        else:
            env_candidates.extend([
                python_dir / configured,
                python_dir / "bin" / configured,
            ])
        for candidate in env_candidates:
            if candidate.exists():
                resolved = str(candidate.resolve())
                break
    if not resolved and Path(configured).exists():
        resolved = str(Path(configured).resolve())
    return {
        "configured": True,
        "available": bool(resolved),
        "resolved": resolved or configured,
    }


def _path_snapshot(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_absolute():
        path = (Path(__file__).resolve().parents[3] / path).resolve()
    return {
        "path": str(path),
        "exists": path.exists(),
    }


def _blocker(key: str, message: str) -> dict[str, str]:
    return {"key": key, "message": message}
