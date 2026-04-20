import asyncio

from app.core.celery_app import celery_app
from app.core.logging import get_logger
from app.services import kb_service

logger = get_logger(__name__)


@celery_app.task(name="kb.index_parse_task")
def index_parse_task(parse_task_id: str, force: bool = False) -> dict:
    logger.info("kb_index_task_started", parse_task_id=parse_task_id, force=force)
    try:
        result = asyncio.run(kb_service.process_parse_task_by_id(parse_task_id, force=force))
        logger.info("kb_index_task_finished", parse_task_id=parse_task_id, result=result)
        return result
    except Exception as exc:  # pragma: no cover - defensive task path
        logger.error("kb_index_task_failed", parse_task_id=parse_task_id, error=str(exc))
        return {
            "ok": False,
            "reason": "worker_exception",
            "parse_task_id": parse_task_id,
            "error": str(exc),
        }
