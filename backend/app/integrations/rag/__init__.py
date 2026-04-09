import importlib.util

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.rag.simple_engine import SimpleRAGEngine

logger = get_logger(__name__)
_engine = None


def get_rag_engine():
    global _engine
    if _engine is not None:
        return _engine

    if settings.RAG_ENGINE == "raganything":
        try:
            if importlib.util.find_spec("raganything") is None:
                raise ModuleNotFoundError("raganything package is not installed in the current Python environment")
            from app.integrations.rag.raganything_adapter import RAGAnythingAdapter

            _engine = RAGAnythingAdapter()
            logger.info("rag_engine_selected", engine="raganything")
            return _engine
        except Exception as exc:  # pragma: no cover - environment-specific fallback
            logger.warning(
                "rag_engine_fallback",
                requested="raganything",
                fallback="simple",
                reason=str(exc),
            )

    _engine = SimpleRAGEngine()
    logger.info("rag_engine_selected", engine="simple")
    return _engine
