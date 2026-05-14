from __future__ import annotations

import importlib.util
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.rag.storage_config import build_runtime_rag_storage_config_snapshot
from app.integrations.preprocessors.multimodal import (
    AUDIO_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
)
from app.models.admin import AdminSetting
from app.models.course import Material
from app.models.knowledge import FileParseTask, KBSpace, KnowledgeEntity, KnowledgeRelation
from app.services import model_routing_service, rag_metrics_service


MODEL_CONFIG_KEYS = {
    "llm_provider": lambda: settings.LLM_PROVIDER,
    "llm_model": lambda: settings.LLM_MODEL,
    "llm_backend": lambda: settings.LLM_BACKEND,
    "llm_local_api_base": lambda: settings.LLM_LOCAL_API_BASE,
    "llm_temperature": lambda: settings.LLM_TEMPERATURE,
    "llm_top_p": lambda: settings.LLM_TOP_P,
    "llm_enable_thinking": lambda: settings.LLM_ENABLE_THINKING,
    "llm_thinking_budget": lambda: settings.LLM_THINKING_BUDGET,
    "extract_model": lambda: settings.EFFECTIVE_EXTRACT_MODEL,
    "extract_temperature": lambda: settings.EXTRACT_TEMPERATURE,
    "extract_top_p": lambda: settings.EXTRACT_TOP_P,
    "extract_enable_thinking": lambda: settings.EXTRACT_ENABLE_THINKING,
    "extract_thinking_budget": lambda: settings.EXTRACT_THINKING_BUDGET,
    "embedding_model": lambda: settings.EMBEDDING_MODEL,
    "embedding_backend": lambda: settings.EMBEDDING_BACKEND,
    "embedding_local_api_base": lambda: settings.EMBEDDING_LOCAL_API_BASE,
    "vlm_model": lambda: settings.VLM_MODEL,
    "vlm_backend": lambda: settings.VLM_BACKEND,
    "vlm_local_api_base": lambda: settings.VLM_LOCAL_API_BASE,
    "vlm_temperature": lambda: settings.VLM_TEMPERATURE,
    "vlm_top_p": lambda: settings.VLM_TOP_P,
    "vlm_enable_thinking": lambda: settings.VLM_ENABLE_THINKING,
    "vlm_thinking_budget": lambda: settings.VLM_THINKING_BUDGET,
    "reranker_provider": lambda: settings.RERANKER_PROVIDER,
    "reranker_model": lambda: settings.RERANKER_MODEL,
    "reranker_local_model": lambda: settings.RERANKER_LOCAL_MODEL,
    "rag_engine": lambda: settings.RAG_ENGINE,
    "storage_backend": lambda: settings.STORAGE_BACKEND,
    "email_dev_mode": lambda: settings.EMAIL_DEV_MODE,
}

RAG_STORAGE_CONFIG_KEYS = {
    "rag_storage_backend": lambda: settings.RAG_STORAGE_BACKEND,
    "vector_db_provider": lambda: getattr(settings, "VECTOR_DB_PROVIDER", "auto"),
    "vector_db_url": lambda: settings.VECTOR_DB_URL,
    "vector_db_collection": lambda: getattr(settings, "VECTOR_DB_COLLECTION", "raganything_chunks"),
    "graph_db_provider": lambda: getattr(settings, "GRAPH_DB_PROVIDER", "auto"),
    "graph_db_url": lambda: settings.GRAPH_DB_URL,
    "graph_db_database": lambda: getattr(settings, "GRAPH_DB_DATABASE", "neo4j"),
    "graph_db_username": lambda: getattr(settings, "GRAPH_DB_USERNAME", ""),
}


def get_model_config(db: Session) -> dict:
    stored = {
        setting.key: setting.value
        for setting in db.query(AdminSetting).filter(AdminSetting.section == "model_config").all()
    }
    return {
        key: stored.get(key, getter())
        for key, getter in MODEL_CONFIG_KEYS.items()
    }


def update_model_config(db: Session, payload: dict) -> dict:
    current = get_model_config(db)
    updates = {key: value for key, value in payload.items() if value is not None}
    if "rag_engine" in updates and str(updates["rag_engine"]).strip().lower() != "raganything":
        updates["rag_engine"] = "raganything"
    current.update(updates)

    for key, value in updates.items():
        setting = db.query(AdminSetting).filter(AdminSetting.key == key).first()
        if not setting:
            setting = AdminSetting(
                section="model_config",
                key=key,
                value=value,
                description=f"Persisted model config value for {key}",
            )
            db.add(setting)
        else:
            setting.value = value

    db.commit()
    return current


def get_rag_storage_config(db: Session) -> dict[str, Any]:
    stored = {
        setting.key: setting.value
        for setting in db.query(AdminSetting).filter(AdminSetting.section == "rag_storage_config").all()
    }
    return {
        key: stored.get(key, getter())
        for key, getter in RAG_STORAGE_CONFIG_KEYS.items()
    }


def update_rag_storage_config(db: Session, payload: dict) -> dict[str, Any]:
    current = get_rag_storage_config(db)
    updates = {key: value for key, value in payload.items() if value is not None}
    current.update(updates)

    for key, value in updates.items():
        setting = db.query(AdminSetting).filter(
            AdminSetting.section == "rag_storage_config",
            AdminSetting.key == key,
        ).first()
        if not setting:
            setting = AdminSetting(
                section="rag_storage_config",
                key=key,
                value=value,
                description=f"Persisted RAG storage config value for {key}",
            )
            db.add(setting)
        else:
            setting.value = value

    db.commit()
    return current


def get_rag_system_status(
    db: Session,
    *,
    days: int = 7,
    class_id: str | None = None,
) -> dict[str, Any]:
    """Build a lightweight backend readiness snapshot for the whole RAG chain."""

    model_config = get_model_config(db)
    model_routing = model_routing_service.build_model_routing_snapshot(model_config)
    performance = rag_metrics_service.get_rag_performance(db, days=days, class_id=class_id)
    dependency_status = _build_dependency_status()
    ingestion_status = _build_ingestion_status(db, class_id=class_id)
    graph_status = _build_graph_status(db, class_id=class_id)
    storage_status = _build_storage_status()
    multimodal_status = _build_multimodal_status()
    checks = _build_readiness_checks(
        dependency_status=dependency_status,
        ingestion_status=ingestion_status,
        graph_status=graph_status,
        storage_status=storage_status,
        model_routing=model_routing,
        performance=performance,
    )

    return {
        "generated_at": datetime.now(timezone.utc),
        "window_days": days,
        "filters": {"class_id": class_id},
        "overall_status": _overall_status(checks),
        "raganything": {
            "requested_engine": settings.RAG_ENGINE,
            "package_available": dependency_status["packages"]["raganything"]["available"],
            "strict_mode": settings.RAGANYTHING_STRICT_MODE,
            "query_fallback_enabled": False,
            "metadata_fallback_enabled": settings.RAGANYTHING_METADATA_FALLBACK_ENABLED,
            "require_official_metadata": settings.RAGANYTHING_REQUIRE_OFFICIAL_METADATA,
            "parser": settings.RAGANYTHING_PARSER,
            "parse_method": settings.RAGANYTHING_PARSE_METHOD,
            "query_mode": settings.RAGANYTHING_QUERY_MODE,
            "max_concurrent_files": settings.RAGANYTHING_MAX_CONCURRENT_FILES,
            "working_dir": _path_snapshot(settings.RAGANYTHING_WORKING_DIR),
            "output_dir": _path_snapshot(settings.RAGANYTHING_OUTPUT_DIR),
        },
        "dependencies": dependency_status,
        "storage": storage_status,
        "models": {
            "configured": model_config,
            "routing": model_routing,
        },
        "multimodal": multimodal_status,
        "ingestion": ingestion_status,
        "knowledge_graph": graph_status,
        "retrieval": {
            "strategy": settings.RAG_RETRIEVAL_STRATEGY,
            "candidate_k": settings.RAG_RETRIEVAL_CANDIDATE_K,
            "answer_top_k": settings.RAG_ANSWER_TOP_K,
            "lightrag_top_k": getattr(settings, "RAG_LIGHTRAG_TOP_K", 12),
            "lightrag_chunk_top_k": getattr(settings, "RAG_LIGHTRAG_CHUNK_TOP_K", 6),
            "lightrag_max_entity_tokens": getattr(settings, "RAG_LIGHTRAG_MAX_ENTITY_TOKENS", 2000),
            "lightrag_max_relation_tokens": getattr(settings, "RAG_LIGHTRAG_MAX_RELATION_TOKENS", 3000),
            "lightrag_max_total_tokens": getattr(settings, "RAG_LIGHTRAG_MAX_TOTAL_TOKENS", 8000),
            "query_rewrite_enabled": settings.RAG_QUERY_REWRITE_ENABLED,
            "query_rewrite_mode": settings.RAG_QUERY_REWRITE_MODE,
            "query_rewrite_max_variants": settings.RAG_QUERY_REWRITE_MAX_VARIANTS,
            "reranker_provider": settings.RERANKER_PROVIDER,
            "reranker_model": settings.RERANKER_MODEL,
        },
        "performance": performance,
        "readiness_checks": checks,
        "next_actions": _suggest_next_actions(checks),
    }


def _build_dependency_status() -> dict[str, Any]:
    parser_module = settings.RAGANYTHING_PARSER if settings.RAGANYTHING_PARSER != "auto" else ""
    packages = {
        "raganything": _package_snapshot("raganything"),
        "mineru": _package_snapshot("mineru"),
        "faster_whisper": _package_snapshot("faster_whisper"),
        "qdrant_client": _package_snapshot("qdrant_client"),
        "neo4j": _package_snapshot("neo4j"),
    }
    if parser_module and parser_module not in packages:
        packages[parser_module] = _package_snapshot(parser_module)

    return {
        "packages": packages,
        "binaries": {
            "ffmpeg": _binary_snapshot(settings.MULTIMODAL_FFMPEG_PATH),
            "ffprobe": _binary_snapshot(settings.MULTIMODAL_FFPROBE_PATH),
            "libreoffice": _binary_snapshot(settings.LIBREOFFICE_PATH) if settings.LIBREOFFICE_PATH else {
                "configured": False,
                "available": False,
                "path": "",
            },
        },
    }


def _build_storage_status() -> dict[str, Any]:
    storage = build_runtime_rag_storage_config_snapshot()
    return {
        "application_storage_backend": settings.STORAGE_BACKEND,
        "rag_storage_backend": storage["requested_backend"],
        "rag_storage_effective_backend": storage["effective_backend"],
        "activation_state": storage["activation_state"],
        "external_configured": storage["external_configured"],
        "external_ready": storage["external_ready"],
        "supports_external_vector": storage["supports_external_vector"],
        "supports_external_graph": storage["supports_external_graph"],
        "vector_db": storage["vector_db"],
        "graph_db": storage["graph_db"],
        "local_storage": _path_snapshot(str(settings.LOCAL_STORAGE_ROOT)),
        "rag_working_dir": storage["working_dir"],
        "rag_output_dir": storage["output_dir"],
        "note": storage["note"],
    }


def _build_multimodal_status() -> dict[str, Any]:
    return {
        "auto_preprocess_enabled": settings.MULTIMODAL_AUTO_PREPROCESS_ENABLED,
        "allow_metadata_only_index": settings.MULTIMODAL_ALLOW_METADATA_ONLY_INDEX,
        "preprocess_output_dir": _path_snapshot(settings.MULTIMODAL_PREPROCESS_OUTPUT_DIR),
        "supported_direct_inputs": {
            "documents": sorted(DOCUMENT_EXTENSIONS.keys()),
            "images": sorted(IMAGE_EXTENSIONS),
        },
        "preprocessed_inputs": {
            "audio": sorted(AUDIO_EXTENSIONS),
            "video": sorted(VIDEO_EXTENSIONS),
            "raganything_entrypoint": "insert_content_list",
        },
        "asr": {
            "provider": settings.ASR_PROVIDER,
            "model": settings.ASR_MODEL,
            "language": settings.ASR_LANGUAGE or "auto",
            "device": settings.ASR_DEVICE,
            "compute_type": settings.ASR_COMPUTE_TYPE,
            "api_base_configured": bool(settings.EFFECTIVE_ASR_API_BASE),
            "api_key_configured": bool(settings.EFFECTIVE_ASR_API_KEY),
            "api_path": settings.ASR_API_PATH,
            "api_auth_header": settings.ASR_API_AUTH_HEADER,
            "package_available": _package_snapshot("faster_whisper")["available"],
        },
        "video": {
            "keyframe_interval_seconds": settings.MULTIMODAL_VIDEO_KEYFRAME_INTERVAL_SECONDS,
            "max_keyframes": settings.MULTIMODAL_VIDEO_MAX_KEYFRAMES,
        },
    }


def _build_ingestion_status(db: Session, *, class_id: str | None) -> dict[str, Any]:
    material_query = db.query(Material)
    task_query = db.query(FileParseTask)
    kb_query = db.query(KBSpace)
    if class_id:
        material_query = material_query.filter(Material.class_id == class_id)
        task_query = task_query.filter(FileParseTask.class_id == class_id)
        kb_query = kb_query.filter(KBSpace.class_id == class_id)

    materials = material_query.all()
    tasks = task_query.order_by(FileParseTask.updated_at.desc()).all()
    kb_spaces = kb_query.all()
    completed_tasks = [task for task in tasks if str(task.status) == "completed"]
    failed_tasks = [task for task in tasks if str(task.status) == "failed"]
    raganything_tasks = [
        task
        for task in tasks
        if (task.parser_name or "").lower() == "raganything"
        or bool(((task.extra_data or {}).get("raganything_status")))
    ]
    content_list_tasks = [
        task
        for task in tasks
        if (((task.extra_data or {}).get("preprocess") or {}).get("mode") == "content_list")
    ]
    metadata_only_tasks = [
        task
        for task in tasks
        if (((task.extra_data or {}).get("preprocess") or {}).get("metadata") or {}).get("preprocess_quality") == "metadata_only"
    ]

    latest_task = tasks[0] if tasks else None
    return {
        "kb_spaces": {
            "total": len(kb_spaces),
            "by_status": dict(Counter(str(space.status) for space in kb_spaces)),
            "ready": sum(1 for space in kb_spaces if str(space.status) == "ready"),
        },
        "materials": {
            "total": len(materials),
            "by_file_type": dict(Counter((material.file_type or "unknown") for material in materials)),
            "by_kb_status": dict(Counter(str(material.kb_status) for material in materials)),
        },
        "parse_tasks": {
            "total": len(tasks),
            "by_status": dict(Counter(str(task.status) for task in tasks)),
            "by_parser": dict(Counter((task.parser_name or "unknown") for task in tasks)),
            "completed": len(completed_tasks),
            "failed": len(failed_tasks),
            "raganything_tasks": len(raganything_tasks),
            "content_list_tasks": len(content_list_tasks),
            "metadata_only_tasks": len(metadata_only_tasks),
            "latest": _task_snapshot(latest_task),
        },
    }


def _build_graph_status(db: Session, *, class_id: str | None) -> dict[str, Any]:
    entity_query = db.query(KnowledgeEntity)
    relation_query = db.query(KnowledgeRelation)
    kb_query = db.query(KBSpace)
    task_query = db.query(FileParseTask)
    if class_id:
        entity_query = entity_query.filter(KnowledgeEntity.class_id == class_id)
        relation_query = relation_query.filter(KnowledgeRelation.class_id == class_id)
        kb_query = kb_query.filter(KBSpace.class_id == class_id)
        task_query = task_query.filter(FileParseTask.class_id == class_id)

    entities = entity_query.all()
    relations = relation_query.all()
    kb_spaces = kb_query.all()
    tasks = task_query.all()
    projected_spaces = [
        space
        for space in kb_spaces
        if bool(((space.extra_data or {}).get("last_graph_projection")))
    ]
    projected_tasks = [
        task
        for task in tasks
        if bool(((task.extra_data or {}).get("graph_projection")))
    ]
    explicit_graph_tasks = [
        task
        for task in projected_tasks
        if bool((((task.extra_data or {}).get("graph_projection") or {}).get("used_explicit_raganything_graph")))
    ]

    return {
        "entities": {
            "total": len(entities),
            "by_type": dict(Counter((entity.entity_type or "unknown") for entity in entities)),
            "by_status": dict(Counter(str(entity.status) for entity in entities)),
        },
        "relations": {
            "total": len(relations),
            "by_type": dict(Counter((relation.relation_type or "unknown") for relation in relations)),
        },
        "raganything_projection": {
            "kb_spaces_with_projection": len(projected_spaces),
            "tasks_with_projection": len(projected_tasks),
            "tasks_using_explicit_raganything_graph": len(explicit_graph_tasks),
            "latest_projection": _latest_projection_snapshot(projected_tasks),
        },
    }


def _build_readiness_checks(
    *,
    dependency_status: dict[str, Any],
    ingestion_status: dict[str, Any],
    graph_status: dict[str, Any],
    storage_status: dict[str, Any],
    model_routing: dict[str, Any],
    performance: dict[str, Any],
) -> list[dict[str, Any]]:
    packages = dependency_status["packages"]
    generation = model_routing.get("generation") or {}
    embedding = model_routing.get("embedding") or {}
    reranker = model_routing.get("reranker") or {}
    parse_tasks = ingestion_status["parse_tasks"]
    graph_projection = graph_status["raganything_projection"]
    performance_totals = performance.get("totals") or {}

    return [
        _check(
            "raganything_package",
            packages["raganything"]["available"],
            "RAG-Anything package is importable.",
            "Install backend/requirements-raganything.txt; this backend no longer falls back to Simple RAG.",
        ),
        _check(
            "parser_package",
            packages.get(settings.RAGANYTHING_PARSER, packages.get("mineru", {})).get("available", False),
            f"Configured parser `{settings.RAGANYTHING_PARSER}` is importable.",
            "Install the parser dependency used by RAG-Anything, usually MinerU for document parsing.",
        ),
        _check(
            "generation_model",
            generation.get("effective_backend") != "mock",
            "Generation model is routed to API/local backend.",
            "Configure LLM API/local endpoint if this environment should generate real answers instead of mock output.",
            severity="warning",
        ),
        _check(
            "embedding_model",
            embedding.get("effective_backend") != "mock",
            "Embedding model is routed to API/local backend.",
            "Configure embedding API/local endpoint before evaluating retrieval quality.",
        ),
        _check(
            "reranker",
            reranker.get("effective_backend") not in {"mock", "none"},
            "Reranker is configured as API/local.",
            "Set RERANKER_PROVIDER=local/api for the planned evidence reordering stage.",
            severity="warning",
        ),
        _check(
            "rag_storage",
            bool(storage_status["rag_storage_backend"]),
            "RAG storage backend is configured.",
            "Set RAG_STORAGE_BACKEND and optional VECTOR_DB_URL/GRAPH_DB_URL for explicit storage documentation.",
        ),
        _check(
            "external_vector_storage",
            (not storage_status["supports_external_vector"]) or bool(storage_status["vector_db"]["ready"]),
            "External vector storage is ready when requested by the configured RAG storage backend.",
            "For Qdrant-backed storage, complete VECTOR_DB_PROVIDER / VECTOR_DB_URL / VECTOR_DB_API_KEY and install qdrant-client.",
            severity="warning",
        ),
        _check(
            "external_graph_storage",
            (not storage_status["supports_external_graph"]) or bool(storage_status["graph_db"]["ready"]),
            "External graph storage is ready when requested by the configured RAG storage backend.",
            "For Neo4j-backed storage, complete GRAPH_DB_PROVIDER / GRAPH_DB_URL / GRAPH_DB_DATABASE / credentials and install neo4j.",
            severity="warning",
        ),
        _check(
            "ingestion_completed",
            parse_tasks["completed"] > 0,
            "At least one material has completed parsing/indexing.",
            "Upload and index one course material to validate the full ingestion chain.",
        ),
        _check(
            "raganything_ingestion",
            parse_tasks["raganything_tasks"] > 0,
            "At least one parse task used RAG-Anything metadata/status.",
            "Run ingestion with RAG_ENGINE=raganything after installing RAG-Anything dependencies.",
        ),
        _check(
            "graph_projection",
            graph_projection["tasks_with_projection"] > 0,
            "Knowledge graph projection has been generated from RAG-Anything metadata.",
            "Index a material through the RAG-Anything adapter so entity/relation projection can be stored.",
            severity="warning",
        ),
        _check(
            "query_observability",
            int(performance_totals.get("queries") or 0) > 0,
            "RAG query events are being recorded.",
            "Ask at least one question through /chat/query to populate RAG quality metrics.",
            severity="warning",
        ),
    ]


def _suggest_next_actions(checks: list[dict[str, Any]]) -> list[str]:
    failed = [check for check in checks if check["status"] != "pass"]
    return [check["remediation"] for check in failed[:5]]


def _overall_status(checks: list[dict[str, Any]]) -> str:
    required_failed = [check for check in checks if check["status"] == "fail" and check["severity"] == "required"]
    warning_failed = [check for check in checks if check["status"] == "fail"]
    if required_failed:
        return "not_ready"
    if warning_failed:
        return "degraded"
    return "ready"


def _check(
    key: str,
    passed: bool,
    message: str,
    remediation: str,
    *,
    severity: str = "required",
) -> dict[str, Any]:
    return {
        "key": key,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "message": message,
        "remediation": remediation,
    }


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


def _binary_snapshot(command: str) -> dict[str, Any]:
    value = str(command or "").strip()
    resolved = shutil.which(value) if value else None
    return {
        "configured": bool(value),
        "available": bool(resolved),
        "path": resolved or value,
    }


def _path_snapshot(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_absolute():
        path = Path(settings.LOCAL_STORAGE_ROOT).parents[0] / path
    return {
        "path": str(path.resolve()),
        "exists": path.exists(),
    }
def _task_snapshot(task: FileParseTask | None) -> dict[str, Any] | None:
    if not task:
        return None
    extra = task.extra_data or {}
    return {
        "id": task.id,
        "material_id": task.material_id,
        "status": str(task.status),
        "parser_name": task.parser_name,
        "updated_at": task.updated_at,
        "raganything_quality": extra.get("raganything_quality"),
        "preprocess": extra.get("preprocess"),
        "graph_projection": extra.get("graph_projection"),
        "raganything_storage": extra.get("raganything_storage"),
        "error_message": task.error_message,
    }


def _latest_projection_snapshot(tasks: list[FileParseTask]) -> dict[str, Any] | None:
    if not tasks:
        return None
    latest = sorted(tasks, key=lambda item: item.updated_at or item.created_at, reverse=True)[0]
    projection = ((latest.extra_data or {}).get("graph_projection") or {})
    return {
        "task_id": latest.id,
        "material_id": latest.material_id,
        "updated_at": latest.updated_at,
        "projection": projection,
    }
