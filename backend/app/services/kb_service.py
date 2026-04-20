import hashlib
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.ai.mock_rag import get_rag_engine
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.logging import get_logger
from app.models.course import Class, ClassMember, Course, Material
from app.models.knowledge import FileParseTask, KBSpace
from app.models.notification import Notification
from app.models.user import User

_UNSET = object()
log = get_logger(__name__)


def _accessible_classes_for_course(db: Session, course_id: str, user: User) -> list[Class]:
    query = db.query(Class).filter(Class.course_id == course_id, Class.is_active == True)
    if user.role == "admin":
        return query.all()
    if user.role == "teacher":
        return query.filter(Class.teacher_id == user.id).all()

    memberships = db.query(ClassMember).filter(
        ClassMember.user_id == user.id,
        ClassMember.role == "student",
    ).all()
    class_ids = [membership.class_id for membership in memberships]
    if not class_ids:
        return []
    return query.filter(Class.id.in_(class_ids)).all()


def ensure_course_access(db: Session, course_id: str, user: User) -> Course:
    course = db.query(Course).filter(Course.id == course_id, Course.is_active == True).first()
    if not course:
        raise NotFoundException("Course not found")
    accessible_classes = _accessible_classes_for_course(db, course_id, user)
    if user.role != "admin" and not accessible_classes and course.created_by != user.id:
        raise ForbiddenException("You do not have access to this course")
    return course


def resolve_class_for_course(
    db: Session,
    course_id: str,
    user: User,
    class_id: Optional[str] = None,
) -> Class:
    accessible_classes = _accessible_classes_for_course(db, course_id, user)
    if class_id:
        for cls in accessible_classes:
            if cls.id == class_id:
                return cls
        raise ForbiddenException("You do not have access to the requested class")
    if accessible_classes:
        return sorted(accessible_classes, key=lambda cls: cls.created_at)[0]
    raise NotFoundException("No accessible class found for this course")


def _ensure_kb_space(db: Session, *, course_id: str, class_id: str | None) -> KBSpace:
    kb_space = db.query(KBSpace).filter(
        KBSpace.course_id == course_id,
        KBSpace.class_id == class_id,
    ).first()
    if kb_space:
        return kb_space
    kb_space = KBSpace(course_id=course_id, class_id=class_id, status="building", extra_data={})
    db.add(kb_space)
    db.flush()
    return kb_space


def list_course_files(db: Session, course_id: str, user: User) -> list[dict]:
    ensure_course_access(db, course_id, user)
    class_ids = [cls.id for cls in _accessible_classes_for_course(db, course_id, user)] if user.role != "admin" else [
        cls.id for cls in db.query(Class).filter(Class.course_id == course_id, Class.is_active == True).all()
    ]
    if not class_ids and user.role != "admin":
        return []
    query = db.query(Material).join(Class, Class.id == Material.class_id).filter(
        Class.course_id == course_id,
        Material.is_active == True,
    )
    if class_ids:
        query = query.filter(Material.class_id.in_(class_ids))
    items = query.order_by(Material.created_at.desc()).all()
    return [{
        "id": item.id,
        "class_id": item.class_id,
        "title": item.title,
        "file_name": item.file_name,
        "file_path": item.file_path,
        "file_size": item.file_size,
        "mime_type": item.mime_type,
        "file_type": item.file_type,
        "kb_status": item.kb_status,
        "kb_error": item.kb_error,
        "description": item.description,
        "created_at": item.created_at,
    } for item in items]


def get_material_for_user(db: Session, course_id: str, file_id: str, user: User) -> Material:
    ensure_course_access(db, course_id, user)
    material = db.query(Material).join(
        Class, Class.id == Material.class_id
    ).filter(
        Material.id == file_id,
        Class.course_id == course_id,
        Material.is_active == True,
    ).first()
    if not material:
        raise NotFoundException("File not found")

    if user.role == "admin":
        return material
    accessible_classes = {cls.id for cls in _accessible_classes_for_course(db, course_id, user)}
    if material.class_id not in accessible_classes and material.uploaded_by != user.id:
        raise ForbiddenException("You do not have access to this file")
    return material


def get_material_preview(db: Session, course_id: str, file_id: str, user: User) -> dict:
    material = get_material_for_user(db, course_id, file_id, user)
    parse_task = db.query(FileParseTask).filter(FileParseTask.material_id == material.id).first()
    extracted_text = (parse_task.extracted_text if parse_task else "") or ""
    return {
        "id": material.id,
        "file_name": material.file_name,
        "mime_type": material.mime_type,
        "file_type": material.file_type,
        "kb_status": material.kb_status,
        "preview_text": extracted_text[:1500],
        "summary": parse_task.summary if parse_task else None,
    }


def get_material_analysis(db: Session, course_id: str, file_id: str, user: User) -> dict:
    material = get_material_for_user(db, course_id, file_id, user)
    parse_task = db.query(FileParseTask).filter(FileParseTask.material_id == material.id).first()
    if not parse_task:
        return {
            "file_id": material.id,
            "status": "pending",
            "summary": None,
            "keywords": [],
            "chunk_count": 0,
            "chunks": [],
        }

    extra = parse_task.extra_data or {}
    ingest_meta = extra.get("ingest", {})
    alert_meta = ingest_meta.get("alert", {})
    return {
        "file_id": material.id,
        "status": parse_task.status,
        "parser_name": parse_task.parser_name,
        "summary": parse_task.summary,
        "keywords": extra.get("keywords", []),
        "chunk_count": len(parse_task.chunks or []),
        "chunks": (parse_task.chunks or [])[:5],
        "content_items": extra.get("content_items", []),
        "content_items_schema": extra.get("content_items_schema", "v0"),
        "raganything_status": extra.get("raganything_status"),
        "raganything_quality": extra.get("raganything_quality"),
        "attempt_count": int(ingest_meta.get("attempt_count", 0) or 0),
        "max_attempts": int(ingest_meta.get("max_attempts", settings.KB_PARSE_MAX_RETRIES) or settings.KB_PARSE_MAX_RETRIES),
        "retry_available": bool(ingest_meta.get("retry_available", parse_task.status == "failed")),
        "last_error_category": ingest_meta.get("last_error_category"),
        "queue_task_id": ingest_meta.get("queue_task_id"),
        "queue_status": ingest_meta.get("queue_status"),
        "auto_retry_round": int(ingest_meta.get("auto_retry_round", 0) or 0),
        "next_retry_after": ingest_meta.get("next_retry_after"),
        "cooldown_remaining_seconds": _cooldown_remaining_seconds(parse_task),
        "alert_count": int(alert_meta.get("count", 0) or 0),
        "last_alert_reason": alert_meta.get("last_reason"),
        "last_alert_at": alert_meta.get("last_alert_at"),
    }


def search_course_content(db: Session, course_id: str, query: str, user: User) -> list[dict]:
    ensure_course_access(db, course_id, user)
    tasks = db.query(FileParseTask).filter(FileParseTask.course_id == course_id, FileParseTask.status == "completed").all()
    query_terms = _terms(query)
    results = []
    for task in tasks:
        for chunk in task.chunks or []:
            chunk_text = chunk.get("text", "")
            overlap = len(query_terms & _terms(chunk_text))
            if overlap <= 0:
                continue
            results.append({
                "material_id": task.material_id,
                "source_name": chunk.get("source_name"),
                "source_type": chunk.get("source_type"),
                "page": chunk.get("page"),
                "chunk_id": chunk.get("chunk_id"),
                "score": round(overlap / max(len(query_terms), 1), 3),
                "snippet": chunk_text[:280],
            })
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:10]


def get_parse_task_for_user(db: Session, task_id: str, user: User) -> dict | None:
    task = db.query(FileParseTask).filter(FileParseTask.id == task_id).first()
    if not task:
        return None
    course = ensure_course_access(db, task.course_id, user)
    _ = course
    return get_rag_engine().get_parse_task(task_id)


def compute_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def find_duplicate_material(
    db: Session,
    *,
    class_id: str,
    file_hash: str,
) -> tuple[Material, FileParseTask] | None:
    tasks = db.query(FileParseTask).filter(
        FileParseTask.class_id == class_id,
    ).order_by(FileParseTask.updated_at.desc()).all()
    for task in tasks:
        extra = task.extra_data or {}
        ingest = extra.get("ingest", {})
        if ingest.get("file_hash") != file_hash:
            continue
        material = db.query(Material).filter(
            Material.id == task.material_id,
            Material.is_active == True,
        ).first()
        if not material:
            continue
        return material, task
    return None


def prepare_parse_task_for_enqueue(
    db: Session,
    *,
    cls: Class,
    material: Material,
    file_hash: str | None,
    force: bool = False,
) -> FileParseTask:
    max_attempts = max(1, int(settings.KB_PARSE_MAX_RETRIES))
    kb_space = _ensure_kb_space(db, course_id=cls.course_id, class_id=cls.id)
    task = db.query(FileParseTask).filter(FileParseTask.material_id == material.id).first()
    if not task:
        task = FileParseTask(
            kb_space_id=kb_space.id,
            course_id=cls.course_id,
            class_id=cls.id,
            material_id=material.id,
            parser_name=settings.RAG_ENGINE,
            status="pending",
        )
        db.add(task)
        db.flush()
    elif force and task.status != "processing":
        task.status = "pending"

    material.kb_status = "pending"
    if force:
        material.kb_error = None
    db.add(material)

    _upsert_ingest_meta(
        task,
        file_hash=file_hash,
        max_attempts=max_attempts,
        retry_available=True,
        append_event={
            "type": "queue_prepare",
            "force": force,
            "at": _utc_now_iso(),
        },
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def enqueue_parse_task(
    db: Session,
    *,
    parse_task: FileParseTask,
    force: bool = False,
) -> dict:
    from app.workers.tasks.kb_index import index_parse_task

    task_id = parse_task.id
    _upsert_ingest_meta(
        parse_task,
        retry_available=True,
        append_event={
            "type": "queue_submit",
            "force": force,
            "at": _utc_now_iso(),
        },
    )
    db.add(parse_task)
    db.commit()

    async_result = index_parse_task.delay(task_id, force=force)
    queue_task_id = getattr(async_result, "id", None) or f"local-{task_id}"
    queue_status = getattr(async_result, "status", None) or "queued"

    db.expire_all()
    refreshed = db.query(FileParseTask).filter(FileParseTask.id == task_id).first()
    if refreshed:
        _upsert_ingest_meta(
            refreshed,
            retry_available=True,
            queue_task_id=queue_task_id,
            queue_status=queue_status,
            append_event={
                "type": "queue_submitted",
                "force": force,
                "queue_task_id": queue_task_id,
                "queue_status": queue_status,
                "at": _utc_now_iso(),
            },
        )
        db.add(refreshed)
        db.commit()
        parse_task = refreshed

    return {
        "parse_task_id": task_id,
        "queue_task_id": queue_task_id,
        "queue_status": queue_status,
        "task_status": parse_task.status if parse_task else "unknown",
    }


async def process_parse_task_by_id(
    parse_task_id: str,
    *,
    force: bool = False,
) -> dict:
    with SessionLocal() as db:
        task = db.query(FileParseTask).filter(FileParseTask.id == parse_task_id).first()
        if not task:
            return {
                "ok": False,
                "reason": "task_not_found",
                "parse_task_id": parse_task_id,
            }

        material = db.query(Material).filter(Material.id == task.material_id).first()
        cls = db.query(Class).filter(Class.id == task.class_id).first()
        if not material or not cls:
            task.status = "failed"
            task.error_message = "material_or_class_not_found"
            _upsert_ingest_meta(
                task,
                retry_available=False,
                last_error_category="data",
                append_event={
                    "type": "attempt_done",
                    "status": "failed",
                    "error": "material_or_class_not_found",
                    "at": _utc_now_iso(),
                },
            )
            db.add(task)
            db.commit()
            return {
                "ok": False,
                "reason": "material_or_class_not_found",
                "parse_task_id": parse_task_id,
            }

        ingest = (task.extra_data or {}).get("ingest", {})
        file_hash = ingest.get("file_hash")
        new_task, action = await ingest_material_with_retry(
            db,
            cls=cls,
            material=material,
            file_hash=file_hash,
            force=force,
        )
        final_task = db.query(FileParseTask).filter(FileParseTask.id == parse_task_id).first()
        auto_retry = None
        if final_task and final_task.status == "failed":
            final_material = db.query(Material).filter(Material.id == final_task.material_id).first()
            auto_retry = _schedule_auto_retry_if_needed(
                db,
                task=final_task,
                material=final_material,
                force=force,
            )
            db.expire_all()
            final_task = db.query(FileParseTask).filter(FileParseTask.id == parse_task_id).first()
        return {
            "ok": bool(final_task and final_task.status == "completed"),
            "action": action,
            "parse_task_id": parse_task_id,
            "status": final_task.status if final_task else (new_task.status if new_task else "unknown"),
            "auto_retry": auto_retry,
        }


async def ingest_material_with_retry(
    db: Session,
    *,
    cls: Class,
    material: Material,
    file_hash: str | None,
    force: bool = False,
) -> tuple[FileParseTask | None, str]:
    max_attempts = max(1, int(settings.KB_PARSE_MAX_RETRIES))
    rag = get_rag_engine()
    material_id = material.id

    existing_task = db.query(FileParseTask).filter(FileParseTask.material_id == material_id).first()
    if existing_task and existing_task.status == "completed" and not force:
        _upsert_ingest_meta(
            existing_task,
            file_hash=file_hash,
            max_attempts=max_attempts,
            retry_available=False,
            append_event={
                "type": "skip",
                "status": "completed",
                "reason": "already_indexed",
                "at": _utc_now_iso(),
            },
        )
        db.commit()
        return existing_task, "already_indexed"

    if existing_task and existing_task.status == "processing" and not force:
        _upsert_ingest_meta(
            existing_task,
            file_hash=file_hash,
            max_attempts=max_attempts,
            retry_available=True,
            append_event={
                "type": "skip",
                "status": "processing",
                "reason": "already_processing",
                "at": _utc_now_iso(),
            },
        )
        db.commit()
        return existing_task, "already_processing"

    action = "indexed"
    task = existing_task
    for _ in range(max_attempts):
        task = db.query(FileParseTask).filter(FileParseTask.material_id == material_id).first()
        current_attempt = _next_attempt(task)

        material.kb_status = "processing"
        db.add(material)
        if task:
            task.status = "processing"
            _upsert_ingest_meta(
                task,
                file_hash=file_hash,
                max_attempts=max_attempts,
                attempt_count=current_attempt,
                retry_available=True,
                append_event={
                    "type": "attempt_start",
                    "attempt": current_attempt,
                    "at": _utc_now_iso(),
                },
            )
            db.add(task)
        db.commit()

        err: Exception | None = None
        ok = False
        try:
            ok = await rag.ingest_material(
                cls.id,
                material_id,
                material.file_path,
                material.mime_type or "application/octet-stream",
            )
        except Exception as exc:  # pragma: no cover - defensive integration path
            err = exc

        db.expire_all()
        task = db.query(FileParseTask).filter(FileParseTask.material_id == material_id).first()
        material = db.query(Material).filter(Material.id == material_id).first()
        if not material:
            return task, "failed"

        succeeded = bool(ok and task and task.status == "completed" and material.kb_status == "indexed")
        if succeeded:
            _normalize_task_content_items(task)
            _upsert_ingest_meta(
                task,
                file_hash=file_hash,
                max_attempts=max_attempts,
                attempt_count=current_attempt,
                retry_available=False,
                last_error_category=None,
                append_event={
                    "type": "attempt_done",
                    "attempt": current_attempt,
                    "status": "completed",
                    "at": _utc_now_iso(),
                },
            )
            db.commit()
            action = "reindexed" if force else "indexed"
            return task, action

        error_message = str(err) if err else (material.kb_error or (task.error_message if task else "indexing_failed"))
        error_category = _error_category_from_message(error_message)
        retry_available = current_attempt < max_attempts
        if task:
            task.status = "failed"
            task.error_message = error_message
            _upsert_ingest_meta(
                task,
                file_hash=file_hash,
                max_attempts=max_attempts,
                attempt_count=current_attempt,
                retry_available=retry_available,
                last_error_category=error_category,
                append_event={
                    "type": "attempt_done",
                    "attempt": current_attempt,
                    "status": "failed",
                    "error": error_message[:200],
                    "error_category": error_category,
                    "at": _utc_now_iso(),
                },
            )
            db.add(task)
            if not retry_available:
                _emit_failure_alert_if_needed(
                    db,
                    task=task,
                    material=material,
                    reason="max_attempts_reached",
                    details={
                        "source": "ingest_material_with_retry",
                        "attempt_count": current_attempt,
                        "max_attempts": max_attempts,
                        "error_category": error_category,
                        "error_message": error_message[:300],
                    },
                )

        material.kb_status = "failed"
        material.kb_error = error_message
        db.add(material)
        db.commit()

    return task, "failed"


def list_course_parse_tasks(
    db: Session,
    *,
    course_id: str,
    user: User,
    class_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    ensure_course_access(db, course_id, user)
    accessible_classes = _accessible_classes_for_course(db, course_id, user)
    accessible_class_ids = {cls.id for cls in accessible_classes}

    query = db.query(FileParseTask).filter(FileParseTask.course_id == course_id)
    if class_id:
        query = query.filter(FileParseTask.class_id == class_id)
    if status:
        query = query.filter(FileParseTask.status == status)
    if user.role != "admin":
        query = query.filter(FileParseTask.class_id.in_(list(accessible_class_ids)))

    total = query.count()
    tasks = query.order_by(FileParseTask.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    materials = {
        material.id: material
        for material in db.query(Material).filter(Material.id.in_([task.material_id for task in tasks])).all()
    }
    return {
        "items": [_task_to_summary(task, materials.get(task.material_id)) for task in tasks],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_parse_tasks_admin(
    db: Session,
    *,
    course_id: str | None = None,
    class_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    query = db.query(FileParseTask)
    if course_id:
        query = query.filter(FileParseTask.course_id == course_id)
    if class_id:
        query = query.filter(FileParseTask.class_id == class_id)
    if status:
        query = query.filter(FileParseTask.status == status)

    total = query.count()
    tasks = query.order_by(FileParseTask.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    materials = {
        material.id: material
        for material in db.query(Material).filter(Material.id.in_([task.material_id for task in tasks])).all()
    }
    return {
        "items": [_task_to_summary(task, materials.get(task.material_id)) for task in tasks],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_queue_task_status(db: Session, queue_task_id: str) -> dict[str, Any]:
    from app.core.celery_app import celery_app

    queue_backend = "dummy"
    queue_status = "UNKNOWN"
    queue_result: Any = None

    if hasattr(celery_app, "AsyncResult"):
        try:
            async_result = celery_app.AsyncResult(queue_task_id)
            queue_status = getattr(async_result, "status", "UNKNOWN")
            queue_backend = "celery"
            if getattr(async_result, "ready", lambda: False)():
                queue_result = getattr(async_result, "result", None)
        except Exception:  # pragma: no cover - best effort queue introspection
            queue_status = "UNKNOWN"
            queue_backend = "celery"

    task = _find_task_by_queue_task_id(db, queue_task_id)
    material = db.query(Material).filter(Material.id == task.material_id).first() if task else None
    return {
        "queue_task_id": queue_task_id,
        "queue_backend": queue_backend,
        "queue_status": queue_status,
        "queue_result": queue_result,
        "parse_task": _task_to_summary(task, material) if task else None,
    }


def retry_failed_tasks_admin(
    db: Session,
    *,
    course_id: str | None = None,
    class_id: str | None = None,
    limit: int | None = None,
    force: bool = False,
    ignore_cooldown: bool = False,
) -> dict[str, Any]:
    max_limit = max(1, int(settings.KB_INDEX_BATCH_RETRY_LIMIT))
    desired_limit = int(limit or max_limit)
    effective_limit = min(max(1, desired_limit), max_limit)

    query = db.query(FileParseTask).filter(FileParseTask.status == "failed")
    if course_id:
        query = query.filter(FileParseTask.course_id == course_id)
    if class_id:
        query = query.filter(FileParseTask.class_id == class_id)

    candidate_total = query.count()
    tasks = query.order_by(FileParseTask.updated_at.asc()).limit(effective_limit).all()

    queued: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    alerts_emitted = 0

    class_cache: dict[str, Class] = {}
    material_cache: dict[str, Material] = {}
    for task in tasks:
        cls = class_cache.get(task.class_id)
        if cls is None:
            cls = db.query(Class).filter(Class.id == task.class_id).first()
            if cls:
                class_cache[task.class_id] = cls

        material = material_cache.get(task.material_id)
        if material is None:
            material = db.query(Material).filter(Material.id == task.material_id).first()
            if material:
                material_cache[task.material_id] = material

        if not cls or not material:
            skipped.append({
                "task_id": task.id,
                "reason": "material_or_class_not_found",
            })
            continue

        can_retry, reason, cooldown_remaining = _can_retry_task_now(
            task,
            now=now,
            force=force,
            ignore_cooldown=ignore_cooldown,
        )
        if not can_retry:
            if reason == "max_attempts_reached":
                emitted = _emit_failure_alert_if_needed(
                    db,
                    task=task,
                    material=material,
                    reason="max_attempts_reached",
                    details={
                        "source": "retry_failed_tasks_admin",
                        "attempt_count": int((task.extra_data or {}).get("ingest", {}).get("attempt_count", 0) or 0),
                        "max_attempts": int((task.extra_data or {}).get("ingest", {}).get("max_attempts", settings.KB_PARSE_MAX_RETRIES) or settings.KB_PARSE_MAX_RETRIES),
                    },
                )
                if emitted:
                    alerts_emitted += 1
            skipped.append({
                "task_id": task.id,
                "reason": reason,
                "cooldown_remaining_seconds": cooldown_remaining,
            })
            continue

        ingest = (task.extra_data or {}).get("ingest", {})
        enqueue_force = True
        prepared_task = prepare_parse_task_for_enqueue(
            db,
            cls=cls,
            material=material,
            file_hash=ingest.get("file_hash"),
            force=enqueue_force,
        )
        queue_info = enqueue_parse_task(
            db,
            parse_task=prepared_task,
            force=enqueue_force,
        )
        queued.append({
            "task_id": prepared_task.id,
            "material_id": prepared_task.material_id,
            "queue_task_id": queue_info.get("queue_task_id"),
            "queue_status": queue_info.get("queue_status"),
        })

    if alerts_emitted > 0:
        db.commit()

    return {
        "filters": {
            "course_id": course_id,
            "class_id": class_id,
            "force": force,
            "ignore_cooldown": ignore_cooldown,
        },
        "candidate_total": candidate_total,
        "processed_count": len(tasks),
        "effective_limit": effective_limit,
        "queued_count": len(queued),
        "skipped_count": len(skipped),
        "alerts_emitted": alerts_emitted,
        "queued": queued,
        "skipped": skipped,
    }


def get_index_queue_metrics(
    db: Session,
    *,
    course_id: str | None = None,
    class_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    query = db.query(FileParseTask)
    if course_id:
        query = query.filter(FileParseTask.course_id == course_id)
    if class_id:
        query = query.filter(FileParseTask.class_id == class_id)

    tasks = query.all()
    total = len(tasks)

    status_counts = {
        "pending": 0,
        "processing": 0,
        "completed": 0,
        "failed": 0,
    }
    queued_total = 0
    queue_wait_samples: list[float] = []
    run_duration_samples: list[float] = []
    tasks_with_retry = 0
    retry_success = 0
    blocked_failed = 0
    attempt_counts: list[int] = []

    for task in tasks:
        status_key = str(task.status or "pending")
        if status_key not in status_counts:
            status_counts[status_key] = 0
        status_counts[status_key] += 1

        ingest = (task.extra_data or {}).get("ingest", {})
        if ingest.get("queue_task_id"):
            queued_total += 1

        attempt_count = int(ingest.get("attempt_count", 0) or 0)
        if attempt_count > 0:
            attempt_counts.append(attempt_count)
        if attempt_count > 1:
            tasks_with_retry += 1
            if task.status == "completed":
                retry_success += 1

        if task.status == "failed" and _cooldown_remaining_seconds(task, now=now) > 0:
            blocked_failed += 1

        wait_values, run_values = _collect_queue_history_latencies(ingest.get("history", []))
        queue_wait_samples.extend(wait_values)
        run_duration_samples.extend(run_values)

    queue_depth = int(status_counts.get("pending", 0)) + int(status_counts.get("processing", 0))
    return {
        "generated_at": now,
        "filters": {
            "course_id": course_id,
            "class_id": class_id,
        },
        "totals": {
            "tasks": total,
            "pending": int(status_counts.get("pending", 0)),
            "processing": int(status_counts.get("processing", 0)),
            "completed": int(status_counts.get("completed", 0)),
            "failed": int(status_counts.get("failed", 0)),
        },
        "queue": {
            "depth_current": queue_depth,
            "queued_total": queued_total,
            "cooldown_blocked_failed": blocked_failed,
        },
        "retry": {
            "tasks_with_retry": tasks_with_retry,
            "retry_success": retry_success,
            "retry_success_rate": _ratio(retry_success, tasks_with_retry),
            "avg_attempt_count": _avg(attempt_counts),
        },
        "latency_ms": {
            "queue_wait": _latency_summary(queue_wait_samples),
            "execution": _latency_summary(run_duration_samples),
        },
    }


def _task_to_summary(task: FileParseTask, material: Material | None) -> dict:
    extra = task.extra_data or {}
    ingest = extra.get("ingest", {})
    alert = ingest.get("alert", {})
    return {
        "id": task.id,
        "kind": "file_parse",
        "course_id": task.course_id,
        "class_id": task.class_id,
        "material_id": task.material_id,
        "material_name": material.file_name if material else None,
        "status": task.status,
        "parser_name": task.parser_name,
        "error_message": task.error_message,
        "attempt_count": int(ingest.get("attempt_count", 0) or 0),
        "max_attempts": int(ingest.get("max_attempts", settings.KB_PARSE_MAX_RETRIES) or settings.KB_PARSE_MAX_RETRIES),
        "retry_available": bool(ingest.get("retry_available", task.status == "failed")),
        "last_error_category": ingest.get("last_error_category"),
        "queue_task_id": ingest.get("queue_task_id"),
        "queue_status": ingest.get("queue_status"),
        "auto_retry_round": int(ingest.get("auto_retry_round", 0) or 0),
        "next_retry_after": ingest.get("next_retry_after"),
        "cooldown_remaining_seconds": _cooldown_remaining_seconds(task),
        "alert_count": int(alert.get("count", 0) or 0),
        "last_alert_reason": alert.get("last_reason"),
        "last_alert_at": alert.get("last_alert_at"),
        "updated_at": task.updated_at,
        "created_at": task.created_at,
    }


def _find_task_by_queue_task_id(db: Session, queue_task_id: str) -> FileParseTask | None:
    tasks = db.query(FileParseTask).order_by(FileParseTask.updated_at.desc()).limit(1000).all()
    for task in tasks:
        ingest = (task.extra_data or {}).get("ingest", {})
        if ingest.get("queue_task_id") == queue_task_id:
            return task
    return None


def _next_attempt(task: FileParseTask | None) -> int:
    if not task:
        return 1
    extra = task.extra_data or {}
    ingest = extra.get("ingest", {})
    return int(ingest.get("attempt_count", 0) or 0) + 1


def _normalize_task_content_items(task: FileParseTask) -> None:
    extra = dict(task.extra_data or {})
    raw_items = extra.get("content_items", [])
    extra["content_items"] = _normalize_content_items(raw_items, material_id=task.material_id)
    extra["content_items_schema"] = "v1"
    task.extra_data = extra


def _schedule_auto_retry_if_needed(
    db: Session,
    *,
    task: FileParseTask,
    material: Material | None,
    force: bool,
) -> dict[str, Any] | None:
    if force or not settings.KB_QUEUE_AUTO_RETRY_ENABLED:
        return None
    if task.status != "failed":
        return None

    ingest = (task.extra_data or {}).get("ingest", {})
    error_category = str(ingest.get("last_error_category") or "unknown").lower()
    if error_category in {"permission", "data"}:
        return None

    max_rounds = max(0, int(settings.KB_QUEUE_AUTO_RETRY_MAX_ROUNDS))
    if max_rounds <= 0:
        return None

    current_round = int(ingest.get("auto_retry_round", 0) or 0)
    if current_round >= max_rounds:
        emitted = _emit_failure_alert_if_needed(
            db,
            task=task,
            material=material,
            reason="auto_retry_exhausted",
            details={
                "source": "schedule_auto_retry",
                "auto_retry_round": current_round,
                "auto_retry_max_rounds": max_rounds,
            },
        )
        if emitted:
            db.commit()
        return None

    cooldown_seconds = max(0, int(settings.KB_QUEUE_RETRY_COOLDOWN_SECONDS))
    now = datetime.now(timezone.utc)
    next_retry_after = (now + timedelta(seconds=cooldown_seconds)).isoformat()

    from app.workers.tasks.kb_index import index_parse_task

    async_result = index_parse_task.apply_async(
        args=(task.id,),
        kwargs={"force": True},
        countdown=cooldown_seconds,
    )
    queue_task_id = getattr(async_result, "id", None) or f"auto-{task.id}-{current_round + 1}"
    queue_status = getattr(async_result, "status", None) or "queued"

    task.status = "pending"
    _upsert_ingest_meta(
        task,
        retry_available=True,
        queue_task_id=queue_task_id,
        queue_status=queue_status,
        auto_retry_round=current_round + 1,
        next_retry_after=next_retry_after,
        append_event={
            "type": "auto_retry_scheduled",
            "round": current_round + 1,
            "countdown_seconds": cooldown_seconds,
            "queue_task_id": queue_task_id,
            "queue_status": queue_status,
            "at": _utc_now_iso(),
        },
    )
    db.add(task)

    if material:
        material.kb_status = "pending"
        db.add(material)

    db.commit()
    return {
        "scheduled": True,
        "round": current_round + 1,
        "queue_task_id": queue_task_id,
        "queue_status": queue_status,
        "countdown_seconds": cooldown_seconds,
        "next_retry_after": next_retry_after,
    }


def _emit_failure_alert_if_needed(
    db: Session,
    *,
    task: FileParseTask,
    material: Material | None,
    reason: str,
    details: dict[str, Any] | None = None,
) -> bool:
    if not settings.KB_INDEX_ALERT_NOTIFY_ADMIN:
        return False

    extra = dict(task.extra_data or {})
    ingest = dict(extra.get("ingest", {}))
    alert = dict(ingest.get("alert", {}))
    attempt_count = int(ingest.get("attempt_count", 0) or 0)
    last_reason = alert.get("last_reason")
    last_attempt_count = int(alert.get("last_attempt_count", -1) or -1)
    if last_reason == reason and last_attempt_count == attempt_count:
        return False

    max_attempts = int(ingest.get("max_attempts", settings.KB_PARSE_MAX_RETRIES) or settings.KB_PARSE_MAX_RETRIES)
    alert_time = _utc_now_iso()
    alert_payload = {
        "alert_kind": "kb_index_failure_limit",
        "reason": reason,
        "task_id": task.id,
        "course_id": task.course_id,
        "class_id": task.class_id,
        "material_id": task.material_id,
        "material_name": material.file_name if material else None,
        "attempt_count": attempt_count,
        "max_attempts": max_attempts,
        "last_error_category": ingest.get("last_error_category"),
        "queue_task_id": ingest.get("queue_task_id"),
        "queue_status": ingest.get("queue_status"),
        "triggered_at": alert_time,
    }
    if details:
        alert_payload.update(details)

    title = "KB indexing failure threshold reached"
    content = (
        "A parsing/indexing task exceeded retry limits and now requires manual intervention."
    )
    admins = db.query(User).filter(User.role == "admin", User.is_active == True).all()
    for admin in admins:
        db.add(Notification(
            user_id=admin.id,
            type="system",
            title=title,
            content=content,
            extra_data=alert_payload,
        ))

    alert["count"] = int(alert.get("count", 0) or 0) + 1
    alert["last_reason"] = reason
    alert["last_alert_at"] = alert_time
    alert["last_attempt_count"] = attempt_count
    alert["last_alert_payload"] = {
        key: value
        for key, value in alert_payload.items()
        if key not in {"error_message"}
    }
    ingest["alert"] = alert
    extra["ingest"] = ingest
    task.extra_data = extra
    db.add(task)

    log.warning(
        "kb_index_failure_alert_emitted",
        task_id=task.id,
        reason=reason,
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        receivers=len(admins),
    )
    return True


def _normalize_content_items(items: Any, *, material_id: str) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        raw_type = item.get("type") or metadata.get("type")
        modality = _normalize_modality(
            item.get("modality")
            or raw_type
            or metadata.get("modality")
            or "text"
        )
        text = _first_text(
            item.get("text"),
            item.get("content"),
            item.get("caption"),
            item.get("ocr_text"),
            metadata.get("text"),
            metadata.get("ocr_text"),
            metadata.get("caption"),
        )
        source_name = _coalesce(
            item.get("source_name"),
            item.get("file_name"),
            item.get("document_name"),
            metadata.get("source_name"),
            metadata.get("file_name"),
            metadata.get("document_name"),
        )
        source_type = _coalesce(
            item.get("source_type"),
            item.get("mime_type"),
            item.get("file_type"),
            metadata.get("source_type"),
            metadata.get("mime_type"),
            metadata.get("file_type"),
        )
        page = _safe_int(_coalesce(
            item.get("page"),
            item.get("page_idx"),
            item.get("page_number"),
            metadata.get("page"),
            metadata.get("page_idx"),
            metadata.get("page_number"),
        ))
        score = _safe_float(_coalesce(
            item.get("score"),
            item.get("confidence"),
            item.get("relevance"),
            metadata.get("score"),
            metadata.get("confidence"),
            metadata.get("relevance"),
        ))
        bbox = _normalize_bbox(_coalesce(
            item.get("bbox"),
            item.get("bounding_box"),
            item.get("coordinates"),
            metadata.get("bbox"),
            metadata.get("bounding_box"),
            metadata.get("coordinates"),
        ))

        normalized.append({
            "item_id": str(item.get("item_id") or item.get("id") or f"{material_id}-ci-{idx + 1}"),
            "modality": modality,
            "raw_type": str(raw_type).lower() if raw_type else None,
            "text": text or "",
            "source_name": source_name,
            "source_type": source_type,
            "page": page,
            "score": score,
            "bbox": bbox,
            "layout_type": _coalesce(
                item.get("layout_type"),
                item.get("block_type"),
                item.get("region_type"),
                metadata.get("layout_type"),
                metadata.get("block_type"),
                metadata.get("region_type"),
            ),
            "doc_id": _coalesce(
                item.get("doc_id"),
                item.get("document_id"),
                metadata.get("doc_id"),
                metadata.get("document_id"),
            ),
            "chunk_id": _coalesce(
                item.get("chunk_id"),
                metadata.get("chunk_id"),
            ),
            "table_html": _coalesce(
                item.get("table_html"),
                item.get("html_table"),
                metadata.get("table_html"),
                metadata.get("html_table"),
            ),
            "table_markdown": _coalesce(
                item.get("table_markdown"),
                item.get("table_md"),
                metadata.get("table_markdown"),
                metadata.get("table_md"),
            ),
            "formula_latex": _coalesce(
                item.get("formula_latex"),
                item.get("latex"),
                item.get("equation"),
                metadata.get("formula_latex"),
                metadata.get("latex"),
                metadata.get("equation"),
            ),
            "image_path": _coalesce(
                item.get("image_path"),
                item.get("image_url"),
                item.get("url"),
                metadata.get("image_path"),
                metadata.get("image_url"),
                metadata.get("url"),
            ),
            "ocr_text": _coalesce(
                item.get("ocr_text"),
                metadata.get("ocr_text"),
            ),
            "timestamp_start": _coalesce(
                item.get("timestamp_start"),
                item.get("start_time"),
                item.get("start"),
                metadata.get("timestamp_start"),
                metadata.get("start_time"),
                metadata.get("start"),
            ),
            "timestamp_end": _coalesce(
                item.get("timestamp_end"),
                item.get("end_time"),
                item.get("end"),
                metadata.get("timestamp_end"),
                metadata.get("end_time"),
                metadata.get("end"),
            ),
            "meta": metadata,
        })
    return normalized


def _normalize_modality(value: Any) -> str:
    token = str(value or "text").strip().lower()
    alias_map = {
        "paragraph": "text",
        "title": "text",
        "header": "text",
        "caption": "text",
        "equation": "formula",
        "math": "formula",
        "latex": "formula",
        "figure": "image",
        "diagram": "image",
        "chart": "image",
        "photo": "image",
        "screenshot": "image",
        "dataframe": "table",
        "csv": "table",
        "spreadsheet": "table",
        "speech": "audio",
    }
    normalized = alias_map.get(token, token)
    allowed = {"text", "table", "formula", "image", "audio", "video", "code"}
    return normalized if normalized in allowed else "text"


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return value.strip()
            continue
        return value
    return None


def _normalize_bbox(value: Any) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        points = [_safe_float(item) for item in value[:4]]
        if all(item is not None for item in points):
            return [float(item) for item in points]
        return None
    if isinstance(value, dict):
        x1 = _safe_float(_coalesce(value.get("x1"), value.get("left"), value.get("x")))
        y1 = _safe_float(_coalesce(value.get("y1"), value.get("top"), value.get("y")))
        x2 = _safe_float(_coalesce(value.get("x2"), value.get("right")))
        y2 = _safe_float(_coalesce(value.get("y2"), value.get("bottom")))

        if x2 is None and x1 is not None:
            width = _safe_float(_coalesce(value.get("w"), value.get("width")))
            if width is not None:
                x2 = x1 + width
        if y2 is None and y1 is not None:
            height = _safe_float(_coalesce(value.get("h"), value.get("height")))
            if height is not None:
                y2 = y1 + height

        if None not in {x1, y1, x2, y2}:
            return [float(x1), float(y1), float(x2), float(y2)]
    return None


def _can_retry_task_now(
    task: FileParseTask,
    *,
    now: datetime | None = None,
    force: bool = False,
    ignore_cooldown: bool = False,
) -> tuple[bool, str | None, int]:
    if force:
        return True, None, 0

    ingest = (task.extra_data or {}).get("ingest", {})
    retry_available = bool(ingest.get("retry_available", task.status == "failed"))
    attempt_count = int(ingest.get("attempt_count", 0) or 0)
    max_attempts = int(ingest.get("max_attempts", settings.KB_PARSE_MAX_RETRIES) or settings.KB_PARSE_MAX_RETRIES)

    if task.status != "failed":
        return False, "not_failed", 0
    if not retry_available:
        return False, "retry_not_available", 0
    if max_attempts > 0 and attempt_count >= max_attempts:
        return False, "max_attempts_reached", 0

    cooldown_remaining = 0 if ignore_cooldown else _cooldown_remaining_seconds(task, now=now)
    if cooldown_remaining > 0:
        return False, "cooldown_active", cooldown_remaining
    return True, None, 0


def _cooldown_remaining_seconds(task: FileParseTask, *, now: datetime | None = None) -> int:
    cooldown_seconds = max(0, int(settings.KB_QUEUE_RETRY_COOLDOWN_SECONDS))
    if cooldown_seconds <= 0:
        return 0

    ingest = (task.extra_data or {}).get("ingest", {})
    failure_at = _last_failed_at(ingest)
    if not failure_at:
        return 0

    current = now or datetime.now(timezone.utc)
    elapsed = (current - failure_at).total_seconds()
    remaining = cooldown_seconds - elapsed
    if remaining <= 0:
        return 0
    return int(math.ceil(remaining))


def _last_failed_at(ingest: dict[str, Any]) -> datetime | None:
    history = ingest.get("history", [])
    if isinstance(history, list):
        for item in reversed(history):
            if not isinstance(item, dict):
                continue
            if item.get("type") != "attempt_done" or item.get("status") != "failed":
                continue
            parsed = _parse_iso_datetime(item.get("at"))
            if parsed:
                return parsed

    if ingest.get("last_error_category"):
        return _parse_iso_datetime(ingest.get("last_attempt_at"))
    return None


def _upsert_ingest_meta(
    task: FileParseTask,
    *,
    file_hash: str | None = None,
    max_attempts: int | None = None,
    attempt_count: int | None = None,
    retry_available: bool | None = None,
    last_error_category: str | None | object = _UNSET,
    queue_task_id: str | None | object = _UNSET,
    queue_status: str | None | object = _UNSET,
    auto_retry_round: int | object = _UNSET,
    next_retry_after: str | None | object = _UNSET,
    append_event: dict | None = None,
) -> None:
    extra = dict(task.extra_data or {})
    ingest = dict(extra.get("ingest", {}))

    if file_hash:
        ingest["file_hash"] = file_hash
        ingest["idempotency_key"] = f"{task.class_id}:{file_hash}"
    if max_attempts is not None:
        ingest["max_attempts"] = int(max_attempts)
    if attempt_count is not None:
        ingest["attempt_count"] = int(attempt_count)
    if retry_available is not None:
        ingest["retry_available"] = bool(retry_available)
    if last_error_category is not _UNSET:
        ingest["last_error_category"] = last_error_category
    if queue_task_id is not _UNSET:
        ingest["queue_task_id"] = queue_task_id
    if queue_status is not _UNSET:
        ingest["queue_status"] = queue_status
    if auto_retry_round is not _UNSET:
        ingest["auto_retry_round"] = int(auto_retry_round)
    if next_retry_after is not _UNSET:
        ingest["next_retry_after"] = next_retry_after
    ingest["last_attempt_at"] = _utc_now_iso()

    if append_event:
        history = list(ingest.get("history", []))
        history.append(append_event)
        ingest["history"] = history[-30:]

    extra["ingest"] = ingest
    task.extra_data = extra


def _error_category_from_message(message: str) -> str:
    lowered = (message or "").lower()
    if "timeout" in lowered:
        return "timeout"
    if "api" in lowered or "http" in lowered or "connection" in lowered:
        return "upstream"
    if "parser" in lowered or "extract" in lowered:
        return "parser"
    if "permission" in lowered or "forbidden" in lowered:
        return "permission"
    return "unknown"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _collect_queue_history_latencies(history: Any) -> tuple[list[float], list[float]]:
    if not isinstance(history, list):
        return [], []

    events: list[dict[str, Any]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        at = _parse_iso_datetime(item.get("at"))
        if not at:
            continue
        events.append({
            "type": item.get("type"),
            "status": item.get("status"),
            "attempt": item.get("attempt"),
            "at": at,
        })
    events.sort(key=lambda item: item["at"])

    queue_waits: list[float] = []
    run_durations: list[float] = []

    for index, event in enumerate(events):
        if event["type"] == "queue_submitted":
            for follower in events[index + 1:]:
                if follower["type"] != "attempt_start":
                    continue
                delta_ms = (follower["at"] - event["at"]).total_seconds() * 1000.0
                if delta_ms >= 0:
                    queue_waits.append(delta_ms)
                break

        if event["type"] == "attempt_start":
            attempt = event.get("attempt")
            for follower in events[index + 1:]:
                if follower["type"] != "attempt_done":
                    continue
                if attempt is not None and follower.get("attempt") != attempt:
                    continue
                delta_ms = (follower["at"] - event["at"]).total_seconds() * 1000.0
                if delta_ms >= 0:
                    run_durations.append(delta_ms)
                break

    return queue_waits, run_durations


def _avg(values: list[int | float]) -> float:
    if not values:
        return 0.0
    return round(sum(float(value) for value in values) / len(values), 4)


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(part / total, 4)


def _latency_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {
            "avg": 0.0,
            "p50": 0.0,
            "p95": 0.0,
            "max": 0.0,
            "samples": 0,
        }

    sorted_values = sorted(float(item) for item in values)
    return {
        "avg": _avg(sorted_values),
        "p50": _percentile(sorted_values, 50),
        "p95": _percentile(sorted_values, 95),
        "max": round(sorted_values[-1], 4),
        "samples": len(sorted_values),
    }


def _percentile(sorted_values: list[float], percentile: int) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return round(sorted_values[0], 4)
    k = (len(sorted_values) - 1) * (percentile / 100)
    lower = int(k)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = k - lower
    value = sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
    return round(value, 4)


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _terms(text: str) -> set[str]:
    import re

    latin = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    cjk = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
    return {token for token in [*latin, *cjk] if token}
