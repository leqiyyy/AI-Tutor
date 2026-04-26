from typing import Any, Mapping

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.admin import AdminSetting


def build_model_routing_snapshot(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    config = dict(overrides or {})
    generation = _resolve_generation(config)
    embedding = _resolve_embedding(config)
    vlm = _resolve_vlm(config)
    reranker = _resolve_reranker(config)
    return {
        "generation": generation,
        "embedding": embedding,
        "vlm": vlm,
        "reranker": reranker,
    }


def load_persisted_model_config() -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.query(AdminSetting).filter(AdminSetting.section == "model_config").all()
    return {row.key: row.value for row in rows}


def build_runtime_model_routing_snapshot() -> dict[str, Any]:
    try:
        persisted = load_persisted_model_config()
    except Exception:
        persisted = {}
    return build_model_routing_snapshot(persisted)


def flatten_routing_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    generation = snapshot.get("generation") or {}
    embedding = snapshot.get("embedding") or {}
    vlm = snapshot.get("vlm") or {}
    reranker = snapshot.get("reranker") or {}
    return {
        "llm_backend": generation.get("effective_backend"),
        "embedding_backend": embedding.get("effective_backend"),
        "vlm_backend": vlm.get("effective_backend"),
        "reranker_backend": reranker.get("effective_backend"),
        "llm_fallback_reason": generation.get("fallback_reason"),
        "embedding_fallback_reason": embedding.get("fallback_reason"),
        "vlm_fallback_reason": vlm.get("fallback_reason"),
        "reranker_fallback_reason": reranker.get("fallback_reason"),
    }


def _resolve_generation(config: Mapping[str, Any]) -> dict[str, Any]:
    llm_provider = str(_cfg(config, "llm_provider", settings.LLM_PROVIDER) or "unknown").strip().lower()
    requested = _normalize_backend(_cfg(config, "llm_backend", settings.LLM_BACKEND))
    llm_model = str(_cfg(config, "llm_model", settings.LLM_MODEL) or settings.LLM_MODEL)
    local_base = _normalize_base(_cfg(config, "llm_local_api_base", settings.LLM_LOCAL_API_BASE))
    api_base = _normalize_base(_cfg(config, "llm_api_base", settings.EFFECTIVE_LLM_API_BASE))
    api_key_configured = bool(settings.EFFECTIVE_LLM_API_KEY)

    if requested == "auto":
        effective = "mock" if llm_provider == "mock" else "api"
    else:
        effective = requested
    fallback_reason = None

    if effective == "local" and not local_base:
        if api_key_configured:
            effective = "api"
            fallback_reason = "missing_local_base"
        else:
            effective = "mock"
            fallback_reason = "missing_local_base_and_api_key"

    if effective == "api" and not api_key_configured:
        effective = "mock"
        fallback_reason = fallback_reason or "missing_api_key"

    provider = {
        "mock": "mock",
        "api": llm_provider or "openai-compatible",
        "local": "local-openai-compatible",
    }.get(effective, "mock")
    model = "mock-llm" if effective == "mock" else llm_model
    effective_base = None
    if effective == "api":
        effective_base = api_base
    if effective == "local":
        effective_base = local_base

    return {
        "requested_backend": requested,
        "effective_backend": effective,
        "provider": provider,
        "model": model,
        "api_base": effective_base,
        "api_key_configured": api_key_configured if effective == "api" else None,
        "fallback_reason": fallback_reason,
    }


def _resolve_embedding(config: Mapping[str, Any]) -> dict[str, Any]:
    requested = _normalize_backend(_cfg(config, "embedding_backend", settings.EMBEDDING_BACKEND))
    model = str(_cfg(config, "embedding_model", settings.EMBEDDING_MODEL) or settings.EMBEDDING_MODEL)
    local_base = _normalize_base(_cfg(config, "embedding_local_api_base", settings.EMBEDDING_LOCAL_API_BASE))
    api_base = _normalize_base(_cfg(config, "embedding_api_base", settings.EFFECTIVE_EMBEDDING_API_BASE))
    api_key_configured = bool(settings.EFFECTIVE_EMBEDDING_API_KEY)
    llm_provider = str(_cfg(config, "llm_provider", settings.LLM_PROVIDER) or "unknown").strip().lower()

    if requested == "auto":
        effective = "mock" if llm_provider == "mock" and not api_key_configured else "api"
    else:
        effective = requested
    fallback_reason = None

    if effective == "local" and not local_base:
        if api_key_configured:
            effective = "api"
            fallback_reason = "missing_local_base"
        else:
            effective = "mock"
            fallback_reason = "missing_local_base_and_api_key"

    if effective == "api" and not api_key_configured:
        effective = "mock"
        fallback_reason = fallback_reason or "missing_api_key"

    provider = {
        "mock": "mock",
        "api": "openai-compatible-embedding",
        "local": "local-embedding",
    }.get(effective, "mock")
    effective_base = None
    if effective == "api":
        effective_base = api_base
    if effective == "local":
        effective_base = local_base

    return {
        "requested_backend": requested,
        "effective_backend": effective,
        "provider": provider,
        "model": "mock-embedding-v1" if effective == "mock" else model,
        "api_base": effective_base,
        "api_key_configured": api_key_configured if effective == "api" else None,
        "fallback_reason": fallback_reason,
    }


def _resolve_vlm(config: Mapping[str, Any]) -> dict[str, Any]:
    requested = _normalize_backend(_cfg(config, "vlm_backend", settings.VLM_BACKEND))
    model = str(_cfg(config, "vlm_model", settings.EFFECTIVE_VLM_MODEL) or settings.EFFECTIVE_VLM_MODEL)
    local_base = _normalize_base(_cfg(config, "vlm_local_api_base", settings.VLM_LOCAL_API_BASE))
    api_base = _normalize_base(_cfg(config, "vlm_api_base", settings.EFFECTIVE_VLM_API_BASE))
    api_key_configured = bool(settings.EFFECTIVE_VLM_API_KEY)
    llm_provider = str(_cfg(config, "llm_provider", settings.LLM_PROVIDER) or "unknown").strip().lower()

    if requested == "auto":
        effective = "mock" if llm_provider == "mock" and not api_key_configured else "api"
    else:
        effective = requested
    fallback_reason = None

    if effective == "local" and not local_base:
        if api_key_configured:
            effective = "api"
            fallback_reason = "missing_local_base"
        else:
            effective = "mock"
            fallback_reason = "missing_local_base_and_api_key"

    if effective == "api" and not api_key_configured:
        effective = "mock"
        fallback_reason = fallback_reason or "missing_api_key"

    provider = {
        "mock": "mock",
        "api": "openai-compatible-vlm",
        "local": "local-vlm",
    }.get(effective, "mock")
    effective_base = None
    if effective == "api":
        effective_base = api_base
    if effective == "local":
        effective_base = local_base

    return {
        "requested_backend": requested,
        "effective_backend": effective,
        "provider": provider,
        "model": "mock-vlm-v1" if effective == "mock" else model,
        "api_base": effective_base,
        "api_key_configured": api_key_configured if effective == "api" else None,
        "fallback_reason": fallback_reason,
    }


def _resolve_reranker(config: Mapping[str, Any]) -> dict[str, Any]:
    requested = str(_cfg(config, "reranker_provider", settings.RERANKER_PROVIDER) or "mock").strip().lower()
    if requested not in {"mock", "none", "api", "local"}:
        requested = "mock"
    effective = requested
    fallback_reason = None

    if effective == "api" and not _normalize_base(_cfg(config, "reranker_api_base", settings.RERANKER_API_BASE)):
        effective = "mock"
        fallback_reason = "missing_api_base"

    if effective == "local":
        model = str(_cfg(config, "reranker_local_model", settings.RERANKER_LOCAL_MODEL) or settings.RERANKER_LOCAL_MODEL)
    elif effective == "none":
        model = "none"
    else:
        model = str(_cfg(config, "reranker_model", settings.RERANKER_MODEL) or settings.RERANKER_MODEL)

    return {
        "requested_backend": requested,
        "effective_backend": effective,
        "provider": effective,
        "model": model,
        "api_base": _normalize_base(_cfg(config, "reranker_api_base", settings.RERANKER_API_BASE)) if effective == "api" else None,
        "api_key_configured": bool(
            settings.RERANKER_API_KEY
            or settings.EFFECTIVE_EMBEDDING_API_KEY
            or settings.EFFECTIVE_EXTRACT_API_KEY
            or settings.EFFECTIVE_LLM_API_KEY
        ) if effective == "api" else None,
        "fallback_reason": fallback_reason,
    }


def _normalize_backend(value: Any) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized not in {"auto", "api", "local", "mock"}:
        return "auto"
    return normalized


def _cfg(config: Mapping[str, Any], key: str, default: Any) -> Any:
    value = config.get(key)
    return default if value is None else value


def _normalize_base(value: Any) -> str:
    text = str(value or "").strip()
    return text.rstrip("/")
