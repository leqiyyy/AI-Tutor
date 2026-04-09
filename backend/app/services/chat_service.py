"""AI chat orchestration service for the AI tutor system."""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.ai.mock_rag import get_rag_engine
from app.core.exceptions import NotFoundException
from app.core.logging import get_logger
from app.models.chat import ChatCitation, ChatMessage, ChatSession, ReviewItem, ReviewSyncRecord
from app.models.user import User
from app.services import analytics_service

log = get_logger(__name__)

CONFIDENCE_THRESHOLD = 0.7


def get_or_create_session(
    db: Session,
    class_id: str,
    user_id: str,
    session_id: Optional[str] = None,
) -> ChatSession:
    if session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        ).first()
        if not session:
            raise NotFoundException("Chat session not found")
        return session
    session = ChatSession(class_id=class_id, user_id=user_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_sessions(db: Session, user_id: str, class_id: Optional[str] = None) -> List[dict]:
    query = db.query(ChatSession).filter(
        ChatSession.user_id == user_id,
        ChatSession.is_active == True,
    )
    if class_id:
        query = query.filter(ChatSession.class_id == class_id)
    sessions = query.order_by(ChatSession.updated_at.desc()).all()
    result = []
    for session in sessions:
        last_msg = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(ChatMessage.created_at.desc()).first()
        result.append({
            "id": session.id,
            "class_id": session.class_id,
            "user_id": session.user_id,
            "title": session.title or "New conversation",
            "is_active": session.is_active,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "last_message": last_msg.content[:80] if last_msg else "",
        })
    return result


def get_session_messages(db: Session, session_id: str, user_id: str) -> List[dict]:
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id,
    ).first()
    if not session:
        raise NotFoundException("Chat session not found")
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()
    return [_msg_to_dict(message) for message in messages]


def _msg_to_dict(message: ChatMessage) -> dict:
    sources = message.sources
    if not sources and message.citations:
        sources = [{
            "name": citation.source_name,
            "page": citation.page,
            "type": citation.source_type,
            "score": citation.score,
            "chunk_id": citation.chunk_id,
        } for citation in message.citations]
    return {
        "id": message.id,
        "session_id": message.session_id,
        "role": message.role,
        "content": message.content,
        "attachments": message.attachments,
        "sources": sources,
        "suggestions": message.suggestions,
        "confidence": message.confidence,
        "feedback": message.feedback,
        "needs_review": message.needs_review,
        "created_at": message.created_at,
    }


async def send_message(
    db: Session,
    class_id: str,
    user_id: str,
    content: str,
    session_id: Optional[str] = None,
    attachments: Optional[List[dict]] = None,
    role: str = "student",
) -> dict:
    session = get_or_create_session(db, class_id, user_id, session_id)

    if not session.title:
        session.title = content[:50]
        db.add(session)

    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=content,
        attachments=attachments,
    )
    db.add(user_msg)
    db.flush()
    analytics_service.record_learning(
        db,
        user_id=user_id,
        class_id=class_id,
        activity_type="ask_question",
        ref_id=user_msg.id,
        extra_data={"role": role},
    )
    analytics_service.record_question_topics(db, class_id, content)

    history_msgs = db.query(ChatMessage).filter(
        ChatMessage.session_id == session.id,
        ChatMessage.id != user_msg.id,
    ).order_by(ChatMessage.created_at.asc()).all()
    history = [{"role": message.role, "content": message.content} for message in history_msgs[-10:]]

    rag = get_rag_engine()
    try:
        result = await rag.query(
            question=content,
            class_id=class_id,
            history=history,
            attachments=attachments,
            role=role,
        )
    except Exception as exc:
        log.error("rag_query_failed", error=str(exc))
        result = type("R", (), {
            "answer": "The AI assistant is temporarily unavailable. Please try again later.",
            "sources": [],
            "confidence": 0.0,
            "suggestions": [],
        })()

    needs_review = result.confidence < CONFIDENCE_THRESHOLD

    ai_msg = ChatMessage(
        session_id=session.id,
        role="ai",
        content=result.answer,
        sources=result.sources,
        suggestions=result.suggestions,
        confidence=result.confidence,
        needs_review=needs_review,
    )
    db.add(ai_msg)
    db.flush()

    for source in result.sources or []:
        db.add(ChatCitation(
            message_id=ai_msg.id,
            source_name=source.get("name") or "unknown",
            source_type=source.get("type"),
            page=source.get("page"),
            score=source.get("score"),
            chunk_id=source.get("chunk_id"),
            extra_data={"raw": source},
        ))

    if needs_review:
        review = ReviewItem(
            message_id=ai_msg.id,
            class_id=class_id,
            student_id=user_id,
            trigger="low_confidence",
            question_content=content,
            ai_answer=result.answer,
        )
        db.add(review)
        log.info("review_triggered", class_id=class_id, confidence=result.confidence)

    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ai_msg)

    return {
        "session_id": session.id,
        "user_message": _msg_to_dict(user_msg),
        "ai_message": _msg_to_dict(ai_msg),
    }


def submit_feedback(
    db: Session,
    message_id: str,
    user_id: str,
    feedback: str,
    reason: Optional[str] = None,
) -> dict:
    message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if not message:
        raise NotFoundException("Message not found")
    message.feedback = feedback
    message.feedback_reason = reason

    if feedback == "dislike":
        existing = db.query(ReviewItem).filter(ReviewItem.message_id == message_id).first()
        if not existing:
            session = db.query(ChatSession).filter(ChatSession.id == message.session_id).first()
            user_msgs = db.query(ChatMessage).filter(
                ChatMessage.session_id == message.session_id,
                ChatMessage.role == "user",
            ).order_by(ChatMessage.created_at.desc()).all()
            question = user_msgs[0].content if user_msgs else "(unknown question)"
            review = ReviewItem(
                message_id=message_id,
                class_id=session.class_id,
                student_id=user_id,
                trigger="dislike",
                question_content=question,
                ai_answer=message.content,
                status="pending",
            )
            db.add(review)
        message.needs_review = True
        session = db.query(ChatSession).filter(ChatSession.id == message.session_id).first()
        if session:
            analytics_service.record_learning(
                db,
                user_id=user_id,
                class_id=session.class_id,
                activity_type="message_dislike",
                ref_id=message.id,
                extra_data={"reason": reason},
            )

    db.commit()
    return {"message_id": message_id, "feedback": feedback}


def list_review_items(db: Session, class_id: str, status: Optional[str] = None) -> List[dict]:
    query = db.query(ReviewItem).filter(ReviewItem.class_id == class_id)
    if status:
        query = query.filter(ReviewItem.status == status)
    items = query.order_by(ReviewItem.created_at.desc()).all()
    result = []
    for item in items:
        student = db.query(User).filter(User.id == item.student_id).first()
        result.append({
            "id": item.id,
            "message_id": item.message_id,
            "class_id": item.class_id,
            "student_id": item.student_id,
            "student_name": student.real_name if student else "",
            "trigger": item.trigger,
            "question_content": item.question_content,
            "ai_answer": item.ai_answer,
            "teacher_answer": item.teacher_answer,
            "status": item.status,
            "created_at": item.created_at,
        })
    return result


async def resolve_review(
    db: Session,
    review_id: str,
    teacher_id: str,
    teacher_answer: str,
    add_to_kb: bool = True,
) -> dict:
    item = db.query(ReviewItem).filter(ReviewItem.id == review_id).first()
    if not item:
        raise NotFoundException("Review item not found")
    item.teacher_answer = teacher_answer
    item.status = "resolved"
    item.reviewed_by = teacher_id
    item.reviewed_at = datetime.now(timezone.utc)
    sync_record = ReviewSyncRecord(
        review_id=item.id,
        class_id=item.class_id,
        question_content=item.question_content,
        final_answer=teacher_answer,
        sync_status="pending",
    )
    db.add(sync_record)
    db.commit()

    if add_to_kb:
        rag = get_rag_engine()
        try:
            await rag.add_qa_pair(item.class_id, item.question_content, teacher_answer)
            sync_record.sync_status = "synced"
            sync_record.sync_note = "Teacher answer synced to fallback knowledge base"
            sync_record.synced_at = datetime.now(timezone.utc)
        except Exception as exc:
            log.error("add_qa_pair_failed", error=str(exc))
            sync_record.sync_status = "failed"
            sync_record.sync_note = str(exc)
    else:
        sync_record.sync_status = "pending"
        sync_record.sync_note = "Sync skipped by teacher choice"

    db.commit()

    return {
        "review_id": review_id,
        "status": "resolved",
        "sync_status": sync_record.sync_status,
        "sync_note": sync_record.sync_note,
    }
