import asyncio
import json
from datetime import datetime, timezone
import os
import tempfile
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import app.storage as storage
from app.core.config import settings
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.core.deps import get_current_teacher, get_current_user
from app.core.error_codes import ErrorCode
from app.core.openapi_examples import responses_with_success
from app.core.response import ok
from app.db.base import get_db
from app.integrations.preprocessors import detect_material_file_type
from app.models.chat import ReviewItem
from app.models.course import Class, Material
from app.models.knowledge import FileParseTask
from app.models.user import User
from app.schemas.chat import ChatQueryRequest, FeedbackRequest, PromoteChatAttachmentRequest, ResolveReviewRequest, SendMessageRequest
from app.services import chat_service, kb_service

router = APIRouter(prefix="/chat", tags=["chat"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _query_response_payload(result: dict) -> dict:
    ai_message = result["ai_message"]
    route_meta = result.get("route_meta") or {}
    return {
        "session_id": result["session_id"],
        "message_id": ai_message["id"],
        "content": ai_message["content"],
        "sources": ai_message["sources"],
        "suggestions": ai_message["suggestions"],
        "confidence": ai_message["confidence"],
        "quality": ai_message.get("quality"),
        "review_context": ai_message.get("review_context"),
        "needs_review": ai_message["needs_review"],
        "route_meta": route_meta,
        "answer_mode": route_meta.get("answer_mode"),
        "resolved_route": route_meta.get("route"),
        "retrieval_used": route_meta.get("retrieval_used"),
        "source_policy": route_meta.get("source_policy"),
    }


@router.post("/attachments/upload", response_model=None)
async def upload_chat_attachment(
    file: UploadFile = File(...),
    class_id: Optional[str] = Form(None),
    course_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolved_class_id = class_id
    if course_id and not class_id:
        resolved_class_id = kb_service.resolve_class_for_course(db, course_id, current_user).id
    created_at = datetime.now(timezone.utc)
    expires_at = chat_service.chat_attachment_expiry(created_at)

    content = await file.read()
    suffix = os.path.splitext(file.filename or "file")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    scope_id = chat_service.chat_attachment_scope_id(current_user.id)
    storage_key, stored_path = storage.save_upload(scope_id, file.filename or "file", tmp_path)
    os.unlink(tmp_path)
    file_type = detect_material_file_type(
        file.filename or "file",
        file.content_type or "application/octet-stream",
    )

    return ok(data={
        "id": storage_key,
        "name": file.filename or "file",
        "size": len(content),
        "mime_type": file.content_type or "application/octet-stream",
        "file_type": file_type,
        "storage_key": storage_key,
        "file_path": stored_path,
        "class_id": resolved_class_id,
        "temporary": True,
        "created_at": created_at,
        "expires_at": expires_at,
    })


@router.post("/attachments/cleanup", response_model=None)
def cleanup_chat_attachments(
    current_user: User = Depends(get_current_user),
):
    return ok(data=chat_service.cleanup_expired_chat_attachments(current_user.id))


@router.post("/attachments/promote", response_model=None)
async def promote_chat_attachment(
    body: PromoteChatAttachmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.class_id:
        cls = db.query(Class).filter(Class.id == body.class_id, Class.is_active == True).first()
        if not cls:
            raise BadRequestException("class_id is invalid")
    elif body.course_id:
        cls = kb_service.resolve_class_for_course(db, body.course_id, current_user)
    else:
        raise BadRequestException("course_id or class_id is required")

    scope_id = chat_service.chat_attachment_scope_id(current_user.id)
    stored_path = storage.get_file_path(scope_id, body.storage_key)
    if not stored_path or not os.path.exists(stored_path):
        raise BadRequestException("Attachment file is unavailable or already expired")

    content = Path(stored_path).read_bytes()
    file_hash = kb_service.compute_file_hash(content)
    duplicate = kb_service.find_duplicate_material(db, class_id=cls.id, file_hash=file_hash)
    if duplicate:
        existing_material, existing_task = duplicate
        return ok(data={
            "id": existing_material.id,
            "class_id": cls.id,
            "file_name": existing_material.file_name,
            "kb_status": existing_material.kb_status,
            "parse_task_id": existing_task.id if existing_task else None,
            "deduplicated": True,
            "promoted_from_chat_attachment": True,
        }, message="Chat attachment already exists in the course knowledge base")

    file_type = body.file_type or detect_material_file_type(body.name, body.mime_type or "application/octet-stream")
    material = Material(
        class_id=cls.id,
        uploaded_by=current_user.id,
        title=body.title or body.name or "Chat Attachment",
        file_name=body.name,
        file_path=stored_path,
        file_size=body.size or len(content),
        mime_type=body.mime_type or "application/octet-stream",
        file_type=file_type,
        description=body.description or "Promoted from temporary chat attachment",
        kb_status="pending",
    )
    db.add(material)
    db.commit()
    db.refresh(material)

    if body.async_index:
        parse_task = kb_service.prepare_parse_task_for_enqueue(
            db,
            cls=cls,
            material=material,
            file_hash=file_hash,
            force=False,
        )
        queue_info = kb_service.enqueue_parse_task(db, parse_task=parse_task, force=False)
        queue_task_id = queue_info.get("queue_task_id")
    else:
        parse_task, _action = await kb_service.ingest_material_with_retry(
            db,
            cls=cls,
            material=material,
            file_hash=file_hash,
            force=False,
        )
        queue_task_id = None

    db.expire_all()
    material = db.query(Material).filter(Material.id == material.id).first()
    if not parse_task:
        parse_task = db.query(FileParseTask).filter_by(material_id=material.id).first()

    return ok(data={
        "id": material.id,
        "class_id": cls.id,
        "file_name": material.file_name,
        "kb_status": material.kb_status,
        "kb_error": material.kb_error,
        "parse_task_id": parse_task.id if parse_task else None,
        "queue_task_id": queue_task_id,
        "promoted_from_chat_attachment": True,
    })


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


@router.delete("/sessions/{session_id}", response_model=None)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = chat_service.delete_session(db, session_id, current_user.id)
    return ok(data=data, message="Conversation deleted")


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
        answer_mode=body.answer_mode,
    )
    return ok(data=result)


@router.post(
    "/query",
    response_model=None,
    responses=responses_with_success(
        example_data={
            "session_id": "a7f6f0c4-16a7-4ad5-8d76-0eb4e9e614b1",
            "message_id": "89f7c67b-0f2a-4da6-9275-70fc4d715989",
            "content": "TCP slow start increases the congestion window exponentially until loss.",
            "sources": [
                {
                    "name": "network_notes.pdf",
                    "page": 12,
                    "type": "pdf",
                    "score": 0.91,
                    "chunk_id": "network_notes-p12-c3",
                }
            ],
            "suggestions": [
                "Explain how slow start differs from congestion avoidance.",
            ],
            "confidence": 0.87,
            "quality": {
                "confidence_band": "high",
                "grounding_level": "strong",
                "source_count": 1,
                "evidence_score": 0.82,
            },
            "review_context": {
                "needs_teacher_review": False,
                "review_priority": "none",
                "review_reasons": [],
                "recommended_action": "direct_answer",
            },
            "needs_review": False,
        },
        include_errors=(
            ErrorCode.BAD_REQUEST.value,
            ErrorCode.UNAUTHORIZED.value,
            ErrorCode.FORBIDDEN.value,
            ErrorCode.VALIDATION_ERROR.value,
            ErrorCode.INTERNAL_ERROR.value,
        ),
    ),
)
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
        answer_mode=body.answer_mode,
    )
    return ok(data=_query_response_payload(result))


@router.post("/query/stream", response_model=None)
async def query_chat_stream(
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

    queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()

    async def progress_callback(event: dict) -> None:
        await queue.put(("progress", event))

    async def run_query() -> None:
        try:
            result = await chat_service.send_message(
                db=db,
                class_id=class_id,
                user_id=current_user.id,
                content=body.message,
                session_id=body.session_id,
                attachments=body.attachments,
                role=current_user.role,
                answer_mode=body.answer_mode,
                progress_callback=progress_callback,
            )
            await queue.put(("final", _query_response_payload(result)))
        except Exception as exc:
            await queue.put(("error", {"message": str(exc) or "AI助教暂时不可用，请稍后重试。"}))
        finally:
            await queue.put(("done", {}))

    async def event_stream():
        task = asyncio.create_task(run_query())
        try:
            while True:
                event, data = await queue.get()
                if event == "done":
                    break
                yield _sse(event, data)
        finally:
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/query-with-image", response_model=None)
async def query_with_image(
    body: ChatQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await query_chat(body=body, db=db, current_user=current_user)


@router.post(
    "/messages/{message_id}/feedback",
    response_model=None,
    responses=responses_with_success(
        example_data={
            "message_id": "89f7c67b-0f2a-4da6-9275-70fc4d715989",
            "feedback": "dislike",
            "reason": "The answer misses congestion control details.",
            "recorded_at": "2026-04-17T01:22:00Z",
        },
        include_errors=(
            ErrorCode.BAD_REQUEST.value,
            ErrorCode.UNAUTHORIZED.value,
            ErrorCode.FORBIDDEN.value,
            ErrorCode.NOT_FOUND.value,
            ErrorCode.VALIDATION_ERROR.value,
            ErrorCode.INTERNAL_ERROR.value,
        ),
    ),
)
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
    cls = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == current_user.id,
        Class.is_active == True,
    ).first()
    if not cls:
        raise ForbiddenException("You do not have access to this class")
    data = chat_service.list_review_items(db, class_id, status)
    return ok(data=data)


@router.post("/reviews/{review_id}/resolve", response_model=None)
async def resolve_review(
    review_id: str,
    body: ResolveReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    review = db.query(ReviewItem).filter(ReviewItem.id == review_id).first()
    if not review:
        raise NotFoundException("Review item not found")
    cls = db.query(Class).filter(
        Class.id == review.class_id,
        Class.teacher_id == current_user.id,
        Class.is_active == True,
    ).first()
    if not cls:
        raise ForbiddenException("You do not have access to this review item")
    result = await chat_service.resolve_review(
        db, review_id, current_user.id, body.teacher_answer, body.add_to_kb
    )
    return ok(data=result)
