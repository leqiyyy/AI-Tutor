import importlib.util
import inspect

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
_engine = None
_engine_name = None


def get_rag_engine(requested_engine: str | None = None):
    global _engine, _engine_name
    target_engine = (requested_engine or settings.RAG_ENGINE or "raganything").lower().strip()
    if target_engine != "raganything":
        raise RuntimeError(
            "Only RAG-Anything is supported as the formal RAG engine. "
            f"Received `{target_engine}`; set RAG_ENGINE=raganything."
        )

    if _engine is not None and _engine_name == target_engine:
        return _engine

    try:
        if importlib.util.find_spec("raganything") is None:
            raise ModuleNotFoundError("raganything package is not installed in the current Python environment")
        from app.integrations.rag.raganything_adapter import RAGAnythingAdapter

        _engine = RAGAnythingAdapter()
        _engine_name = "raganything"
        logger.info("rag_engine_selected", engine="raganything")
        return _engine
    except Exception as exc:  # pragma: no cover - environment-specific dependency failure
        logger.error(
            "rag_engine_raganything_failure",
            requested="raganything",
            strict=settings.RAGANYTHING_STRICT_MODE,
            reason=str(exc),
        )
        raise RuntimeError(
            "RAG-Anything is configured as the only formal RAG engine, but it "
            f"could not be initialized: {exc}"
        ) from exc


async def shutdown_rag_engine() -> None:
    global _engine, _engine_name
    engine = _engine
    _engine = None
    _engine_name = None
    if engine is None:
        return

    close = getattr(engine, "aclose", None)
    if not callable(close):
        close = getattr(engine, "close", None)
    if not callable(close):
        return

    result = close()
    if inspect.isawaitable(result):
        await result
    logger.info("rag_engine_shutdown", engine="raganything")
