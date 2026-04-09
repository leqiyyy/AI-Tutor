from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException
from app.core.deps import get_current_teacher, get_current_user
from app.core.response import ok
from app.db.base import get_db
from app.models.user import User
from app.schemas.chat import ChatQueryRequest, FeedbackRequest, ResolveReviewRequest, SendMessageRequest
from app.services import chat_service, kb_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions", response_model=None)
def list_sessions(
    class_id: Optional[str] = Query(None),
    course_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolved_class_id = class_id
    if course_id and not class_id:
        resolved_class_id = kb_service.resolve_class_for_course(db, course_id, current_user).id
    data = chat_service.list_sessions(db, current_user.id, resolved_class_id)
    return ok(data=data)


@router.get("/sessions/{session_id}/messages", response_model=None)
def get_messages(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = chat_service.get_session_messages(db, session_id, current_user.id)
    return ok(data=data)


@router.post("/send", response_model=None)
async def send_message(
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await chat_service.send_message(
        db=db,
        class_id=body.class_id,
        user_id=current_user.id,
        content=body.content,
        session_id=body.session_id,
        attachments=body.attachments,
        role=current_user.role,
    )
    return ok(data=result)


@router.post("/query", response_model=None)
async def query_chat(
    body: ChatQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.class_id:
        class_id = body.class_id
    elif body.course_id:
        class_id = kb_service.resolve_class_for_course(db, body.course_id, current_user).id
    else:
        raise BadRequestException("course_id or class_id is required")

    result = await chat_service.send_message(
        db=db,
        class_id=class_id,
        user_id=current_user.id,
        content=body.message,
        session_id=body.session_id,
        attachments=body.attachments,
        role=current_user.role,
    )
    ai_message = result["ai_message"]
    return ok(data={
        "session_id": result["session_id"],
        "message_id": ai_message["id"],
        "content": ai_message["content"],
        "sources": ai_message["sources"],
        "suggestions": ai_message["suggestions"],
        "confidence": ai_message["confidence"],
        "needs_review": ai_message["needs_review"],
    })


@router.post("/query-with-image", response_model=None)
async def query_with_image(
    body: ChatQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await query_chat(body=body, db=db, current_user=current_user)


@router.post("/messages/{message_id}/feedback", response_model=None)
def submit_feedback(
    message_id: str,
    body: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = chat_service.submit_feedback(
        db, message_id, current_user.id, body.feedback, body.reason
    )
    return ok(data=result)


@router.get("/reviews", response_model=None)
def list_reviews(
    class_id: str = Query(...),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    data = chat_service.list_review_items(db, class_id, status)
    return ok(data=data)


@router.post("/reviews/{review_id}/resolve", response_model=None)
async def resolve_review(
    review_id: str,
    body: ResolveReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    result = await chat_service.resolve_review(
        db, review_id, current_user.id, body.teacher_answer, body.add_to_kb
    )
    return ok(data=result)
