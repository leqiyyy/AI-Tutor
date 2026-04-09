from typing import Literal, Optional

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_teacher, get_current_user
from app.core.exceptions import ForbiddenException
from app.core.response import ok
from app.db.base import get_db
from app.models.course import ClassMember, Class
from app.models.notification import Notification
from app.models.user import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


class CreateNotificationRequest(BaseModel):
    class_id: str
    title: str
    content: str
    type: Literal["deadline", "reply", "exam", "ai", "material", "question", "dislike", "system"] = "system"
    scope: str = "students"
    extra_data: Optional[dict] = None


@router.get("", response_model=None)
def list_notifications(
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.is_read == False)
    items = query.order_by(Notification.created_at.desc()).limit(50).all()
    data = [{
        "id": notification.id,
        "type": notification.type,
        "title": notification.title,
        "content": notification.content,
        "is_read": notification.is_read,
        "created_at": notification.created_at,
        "meta": notification.extra_data,
    } for notification in items]
    unread_count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).count()
    return ok(data={"items": data, "unread_count": unread_count})


@router.post("/{notification_id}/read", response_model=None)
def mark_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if notification:
        notification.is_read = True
        db.commit()
    return ok(message="Notification marked as read")


@router.post("/read-all", response_model=None)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return ok(message="All notifications marked as read")


@router.post("/mark-read", response_model=None)
def mark_read_alias(
    notification_ids: list[str] | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if notification_ids:
        query = query.filter(Notification.id.in_(notification_ids))
    query.update({"is_read": True}, synchronize_session=False)
    db.commit()
    return ok(message="Notifications marked as read")


@router.post("", response_model=None)
def create_notifications(
    body: CreateNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    cls = db.query(Class).filter(Class.id == body.class_id, Class.teacher_id == current_user.id).first()
    if not cls:
        raise ForbiddenException("You do not have access to this class")

    member_query = db.query(ClassMember).filter(ClassMember.class_id == body.class_id)
    if body.scope == "students":
        member_query = member_query.filter(ClassMember.role == "student")
    recipients = member_query.all()

    created = 0
    for recipient in recipients:
        db.add(Notification(
            user_id=recipient.user_id,
            type=body.type,
            title=body.title,
            content=body.content,
            extra_data={
                "class_id": body.class_id,
                "scope": body.scope,
                **(body.extra_data or {}),
            },
        ))
        created += 1
    db.commit()
    return ok(data={"recipient_count": created, "class_id": body.class_id}, message="Notifications published")
