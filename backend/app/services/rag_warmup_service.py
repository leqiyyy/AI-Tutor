import asyncio
from time import perf_counter

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.integrations.rag import get_rag_engine
from app.models.chat import ChatSession
from app.models.course import Material
from app.models.knowledge import FileParseTask

logger = get_logger(__name__)


def _warmup_class_sync(engine: object, class_id: str) -> None:
    get_instance = getattr(engine, "_get_instance")
    ensure_ready = getattr(engine, "_ensure_rag_query_ready")
    rag = get_instance(class_id)
    result = ensure_ready(rag)
    if asyncio.iscoroutine(result) or hasattr(result, "__await__"):
        asyncio.run(result)


def find_warmup_class_ids(limit: int | None = None) -> list[str]:
    max_classes = max(0, int(limit if limit is not None else settings.RAG_WARMUP_MAX_CLASSES))
    if max_classes <= 0:
        return []

    with SessionLocal() as db:
        active_chat_rows = (
            db.query(ChatSession.class_id)
            .join(Material, Material.class_id == ChatSession.class_id)
            .join(FileParseTask, FileParseTask.material_id == Material.id)
            .filter(
                ChatSession.is_active == True,
                FileParseTask.status == "completed",
                Material.kb_status == "indexed",
                Material.is_active == True,
            )
            .order_by(ChatSession.updated_at.desc(), FileParseTask.updated_at.desc())
            .all()
        )
        indexed_rows = (
            db.query(FileParseTask.class_id)
            .join(Material, Material.id == FileParseTask.material_id)
            .filter(
                FileParseTask.status == "completed",
                Material.kb_status == "indexed",
                Material.is_active == True,
            )
            .order_by(FileParseTask.updated_at.desc(), FileParseTask.created_at.desc())
            .all()
        )

    class_ids: list[str] = []
    seen = set()
    for (class_id,) in [*active_chat_rows, *indexed_rows]:
        if not class_id or class_id in seen:
            continue
        seen.add(class_id)
        class_ids.append(str(class_id))
        if len(class_ids) >= max_classes:
            break
    return class_ids


async def warmup_rag_classes(class_ids: list[str] | None = None) -> dict:
    if not settings.RAG_WARMUP_ON_STARTUP and class_ids is None:
        return {"enabled": False, "class_count": 0, "warmed": [], "failed": []}

    selected_class_ids = class_ids if class_ids is not None else find_warmup_class_ids()
    if not selected_class_ids:
        logger.info("rag_warmup_skipped", reason="no_indexed_classes")
        return {"enabled": True, "class_count": 0, "warmed": [], "failed": []}

    engine = get_rag_engine()
    warmed: list[dict] = []
    failed: list[dict] = []
    logger.info("rag_warmup_started", class_count=len(selected_class_ids), class_ids=selected_class_ids)

    for class_id in selected_class_ids:
        started = perf_counter()
        try:
            await asyncio.to_thread(_warmup_class_sync, engine, class_id)
            elapsed_ms = round((perf_counter() - started) * 1000, 2)
            warmed.append({"class_id": class_id, "elapsed_ms": elapsed_ms})
            logger.info("rag_warmup_class_ready", class_id=class_id, elapsed_ms=elapsed_ms)
        except Exception as exc:
            elapsed_ms = round((perf_counter() - started) * 1000, 2)
            failed.append({"class_id": class_id, "elapsed_ms": elapsed_ms, "error": str(exc)[:500]})
            logger.warning("rag_warmup_class_failed", class_id=class_id, elapsed_ms=elapsed_ms, error=str(exc))

    logger.info("rag_warmup_finished", warmed=len(warmed), failed=len(failed))
    return {"enabled": True, "class_count": len(selected_class_ids), "warmed": warmed, "failed": failed}


def schedule_rag_warmup() -> asyncio.Task | None:
    if not settings.RAG_WARMUP_ON_STARTUP:
        logger.info("rag_warmup_disabled")
        return None

    async def _delayed_warmup() -> dict:
        delay = max(0.0, float(getattr(settings, "RAG_WARMUP_STARTUP_DELAY_SECONDS", 5.0) or 0.0))
        if delay:
            await asyncio.sleep(delay)
        return await warmup_rag_classes()

    return asyncio.create_task(_delayed_warmup())
