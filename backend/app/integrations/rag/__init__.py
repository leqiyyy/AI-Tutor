import importlib.util

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.rag.simple_engine import SimpleRAGEngine

logger = get_logger(__name__)
_engine = None
_engine_name = None


def get_rag_engine(requested_engine: str | None = None):
    global _engine, _engine_name
    target_engine = (requested_engine or settings.RAG_ENGINE or "simple").lower().strip()
    if target_engine not in {"simple", "raganything"}:
        target_engine = "simple"

    if _engine is not None and _engine_name == target_engine:
        return _engine

    if target_engine == "raganything":
        try:
            if importlib.util.find_spec("raganything") is None:
                raise ModuleNotFoundError("raganything package is not installed in the current Python environment")
            from app.integrations.rag.raganything_adapter import RAGAnythingAdapter

            _engine = RAGAnythingAdapter()
            _engine_name = "raganything"
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
    _engine_name = "simple"
    logger.info("rag_engine_selected", engine="simple")
    return _engine
