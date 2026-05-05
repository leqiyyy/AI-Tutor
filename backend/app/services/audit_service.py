from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.admin import AdminAuditEvent
from app.models.user import User

log = get_logger(__name__)


def record_event(
    *,
    event_type: str,
    status: str = "success",
    actor: User | None = None,
    actor_id: str | None = None,
    actor_role: str | None = None,
    actor_name: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    course_id: str | None = None,
    class_id: str | None = None,
    material_id: str | None = None,
    summary: str | None = None,
    extra_data: dict[str, Any] | None = None,
) -> str | None:
    """Best-effort administrator audit event recording.

    The write uses an independent session so audit logging cannot commit or
    roll back the caller's business transaction.
    """
    if actor is not None:
        actor_id = actor_id or actor.id
        actor_role = actor_role or actor.role
        actor_name = actor_name or actor.real_name or actor.email

    db = SessionLocal()
    try:
        event = AdminAuditEvent(
            event_type=event_type,
            status=status,
            actor_id=actor_id,
            actor_role=actor_role,
            actor_name=actor_name,
            target_type=target_type,
            target_id=target_id,
            course_id=course_id,
            class_id=class_id,
            material_id=material_id,
            summary=summary,
            extra_data=extra_data or {},
        )
        db.add(event)
        db.commit()
        return event.id
    except Exception as exc:  # pragma: no cover - observability must not break business paths
        db.rollback()
        log.warning(
            "admin_audit_event_failed",
            event_type=event_type,
            status=status,
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            error=str(exc),
        )
        return None
    finally:
        db.close()


def list_events(
    db: Session,
    *,
    event_type: str | None = None,
    status: str | None = None,
    actor_role: str | None = None,
    class_id: str | None = None,
    course_id: str | None = None,
    target_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 30,
) -> dict[str, Any]:
    query = db.query(AdminAuditEvent)
    if event_type:
        query = query.filter(AdminAuditEvent.event_type == event_type)
    if status:
        query = query.filter(AdminAuditEvent.status == status)
    if actor_role:
        query = query.filter(AdminAuditEvent.actor_role == actor_role)
    if class_id:
        query = query.filter(AdminAuditEvent.class_id == class_id)
    if course_id:
        query = query.filter(AdminAuditEvent.course_id == course_id)
    if target_type:
        query = query.filter(AdminAuditEvent.target_type == target_type)
    if date_from:
        query = query.filter(AdminAuditEvent.created_at >= _ensure_aware(date_from))
    if date_to:
        query = query.filter(AdminAuditEvent.created_at <= _ensure_aware(date_to))

    total = query.count()
    rows = (
        query.order_by(AdminAuditEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_event_to_dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _event_to_dict(event: AdminAuditEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "status": event.status,
        "actor_id": event.actor_id,
        "actor_role": event.actor_role,
        "actor_name": event.actor_name,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "course_id": event.course_id,
        "class_id": event.class_id,
        "material_id": event.material_id,
        "summary": event.summary,
        "extra_data": event.extra_data or {},
        "created_at": event.created_at,
    }


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
