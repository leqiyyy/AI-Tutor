from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.reranker.api_reranker import APIReranker
from app.integrations.reranker.base import BaseReranker
from app.integrations.reranker.local_reranker import LocalReranker
from app.integrations.reranker.mock_reranker import MockReranker

logger = get_logger(__name__)
_reranker: BaseReranker | None = None


class NoopReranker(BaseReranker):
    provider_name = "none"
    model_name = "none"

    async def rerank(
        self,
        *,
        query: str,
        candidates: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        _ = (query, context)
        outputs = []
        for item in candidates:
            outputs.append({
                **item,
                "rerank_score": float(item.get("retrieval_score") or item.get("score") or 0.0),
                "rerank_components": {"base_score": float(item.get("retrieval_score") or item.get("score") or 0.0)},
                "reranker_provider": self.provider_name,
                "reranker_model": self.model_name,
            })
        outputs.sort(key=lambda item: item.get("rerank_score", 0.0), reverse=True)
        return outputs


def reset_reranker_cache() -> None:
    global _reranker
    _reranker = None


def _build_reranker(provider: str) -> BaseReranker:
    if provider == "none":
        return NoopReranker()
    if provider == "mock":
        return MockReranker()
    if provider == "api":
        if not (settings.RERANKER_API_BASE or "").strip():
            logger.warning("reranker_provider_fallback", requested="api", fallback="mock", reason="missing_api_base")
            return MockReranker()
        return APIReranker()
    if provider == "local":
        return LocalReranker()

    logger.warning("reranker_provider_fallback", requested=provider, fallback="mock")
    return MockReranker()


def get_reranker() -> BaseReranker:
    global _reranker
    if _reranker is not None:
        return _reranker

    provider = (settings.RERANKER_PROVIDER or "mock").lower().strip()
    _reranker = _build_reranker(provider)
    logger.info(
        "reranker_selected",
        provider=getattr(_reranker, "provider_name", "unknown"),
        model=getattr(_reranker, "model_name", "unknown"),
    )
    return _reranker
