"""AI chat orchestration service for the AI tutor system."""
import base64
import mimetypes
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.core.logging import get_logger
from app.integrations.rag import get_rag_engine
from app.integrations.parser.simple import SimpleParserProvider
from app.integrations.preprocessors import preprocess_for_raganything
from app.integrations.rag.quality import build_evidence_quality, build_review_context
from app.models.course import Class
from app.models.chat import ChatCitation, ChatMessage, ChatSession, ReviewItem, ReviewSyncRecord
from app.models.knowledge import KBSpace
from app.models.user import User
from app.services import admin_service, analytics_service, conversation_context_service, model_routing_service, rag_metrics_service

log = get_logger(__name__)
_fallback_attachment_parser = SimpleParserProvider()

def chat_attachment_scope_id(user_id: str) -> str:
    return f"{settings.CHAT_ATTACHMENT_SCOPE_PREFIX}/{user_id}"


def chat_attachment_expiry(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return current + timedelta(hours=max(1, int(settings.CHAT_ATTACHMENT_TTL_HOURS)))


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
    quality = build_evidence_quality(sources or [], message.confidence)
    review_context = build_review_context(
        sources or [],
        message.confidence,
        trigger="dislike" if message.feedback == "dislike" else ("low_confidence" if message.needs_review else "none"),
        feedback=message.feedback,
    )
    return {
        "id": message.id,
        "session_id": message.session_id,
        "role": message.role,
        "content": message.content,
        "attachments": message.attachments,
        "sources": sources,
        "suggestions": message.suggestions,
        "confidence": message.confidence,
        "quality": quality,
        "review_context": review_context,
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
    prepared_attachments = prepare_chat_attachments(attachments)
    conversation_context = conversation_context_service.build_conversation_context(
        db,
        session,
        content,
        max_recent_turns=10,
    )
    retrieval_question = conversation_context.standalone_question or content

    if not session.title:
        session.title = content[:50]
        db.add(session)

    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=content,
        attachments=prepared_attachments,
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

    history = conversation_context.recent_turns[-10:]

    persisted_model_config = admin_service.get_model_config(db)
    rag = get_rag_engine(requested_engine=persisted_model_config.get("rag_engine"))
    routing_snapshot = model_routing_service.build_model_routing_snapshot(persisted_model_config)
    routing_meta = model_routing_service.flatten_routing_snapshot(routing_snapshot)
    rag_started = perf_counter()
    rag_latency_ms = None
    try:
        result = await rag.query(
            question=retrieval_question,
            class_id=class_id,
            history=history,
            attachments=prepared_attachments,
            role=role,
        )
        rag_latency_ms = round((perf_counter() - rag_started) * 1000, 2)
        result_meta = getattr(result, "meta", {}) or {}
        evidence_quality = build_evidence_quality(result.sources or [], result.confidence)
        review_context = build_review_context(
            result.sources or [],
            result.confidence,
            trigger="low_confidence",
        )
        rag_metrics_service.record_query_event(
            db,
            class_id=class_id,
            user_id=user_id,
            role=role,
            engine=result_meta.get("engine") or settings.RAG_ENGINE or "unknown",
            query_mode=result_meta.get("query_mode") or settings.RAGANYTHING_QUERY_MODE,
            query_method=result_meta.get("query_method"),
            used_multimodal=bool(result_meta.get("used_multimodal")) or any(
                (item or {}).get("file_type") == "image" for item in (prepared_attachments or [])
            ),
            used_fallback=bool(result_meta.get("used_fallback")),
            fallback_reason=result_meta.get("fallback_reason"),
            success=True,
            latency_ms=rag_latency_ms,
            confidence=result.confidence,
            source_count=len(result.sources or []),
            extra_data={
                "path": result_meta.get("path"),
                "retrieval_strategy": result_meta.get("retrieval_strategy"),
                "reranker_provider": result_meta.get("reranker_provider"),
                "reranker_model": result_meta.get("reranker_model"),
                "candidate_count": result_meta.get("candidate_count"),
                "selected_count": result_meta.get("selected_count"),
                "graph_term_count": result_meta.get("graph_term_count"),
                "evidence_quality": evidence_quality,
                "confidence_band": evidence_quality["confidence_band"],
                "grounding_level": evidence_quality["grounding_level"],
                "avg_source_score": evidence_quality["avg_source_score"],
                "max_source_score": evidence_quality["max_source_score"],
                "evidence_score": evidence_quality["evidence_score"],
                "grounded": evidence_quality["grounded"],
                "review_context": review_context,
                "query_rewrite_enabled": bool(result_meta.get("query_rewrite_enabled", settings.RAG_QUERY_REWRITE_ENABLED)),
                "query_rewrite_mode": result_meta.get("query_rewrite_mode") or settings.RAG_QUERY_REWRITE_MODE,
                "query_variant_count": result_meta.get("query_variant_count"),
                "conversation_context": conversation_context.to_rag_meta(),
                "llm_backend": routing_meta.get("llm_backend"),
                "embedding_backend": routing_meta.get("embedding_backend"),
                "vlm_backend": routing_meta.get("vlm_backend"),
                "reranker_backend": routing_meta.get("reranker_backend"),
            },
        )
    except Exception as exc:
        rag_latency_ms = round((perf_counter() - rag_started) * 1000, 2)
        log.error("rag_query_failed", error=str(exc))
        evidence_quality = build_evidence_quality([], 0.0)
        review_context = build_review_context([], 0.0, trigger="low_confidence")
        rag_metrics_service.record_query_event(
            db,
            class_id=class_id,
            user_id=user_id,
            role=role,
            engine=settings.RAG_ENGINE or "unknown",
            query_mode=settings.RAGANYTHING_QUERY_MODE,
            query_method=None,
            used_multimodal=any((item or {}).get("file_type") == "image" for item in (prepared_attachments or [])),
            used_fallback=True,
            fallback_reason="chat_service_exception",
            success=False,
            latency_ms=rag_latency_ms,
            confidence=0.0,
            source_count=0,
            extra_data={
                "error": str(exc),
                "retrieval_strategy": settings.RAG_RETRIEVAL_STRATEGY,
                "reranker_provider": settings.RERANKER_PROVIDER,
                "reranker_model": settings.RERANKER_MODEL,
                "candidate_count": 0,
                "selected_count": 0,
                "graph_term_count": 0,
                "evidence_quality": evidence_quality,
                "confidence_band": evidence_quality["confidence_band"],
                "grounding_level": evidence_quality["grounding_level"],
                "avg_source_score": evidence_quality["avg_source_score"],
                "max_source_score": evidence_quality["max_source_score"],
                "evidence_score": evidence_quality["evidence_score"],
                "grounded": evidence_quality["grounded"],
                "review_context": review_context,
                "query_rewrite_enabled": bool(settings.RAG_QUERY_REWRITE_ENABLED),
                "query_rewrite_mode": settings.RAG_QUERY_REWRITE_MODE,
                "query_variant_count": 1,
                "conversation_context": conversation_context.to_rag_meta(),
                "llm_backend": routing_meta.get("llm_backend"),
                "embedding_backend": routing_meta.get("embedding_backend"),
                "vlm_backend": routing_meta.get("vlm_backend"),
                "reranker_backend": routing_meta.get("reranker_backend"),
            },
        )
        result = type("R", (), {
            "answer": "The AI assistant is temporarily unavailable. Please try again later.",
            "sources": [],
            "confidence": 0.0,
            "suggestions": [],
            "meta": {
                "engine": settings.RAG_ENGINE,
                "used_fallback": True,
                "fallback_reason": "chat_service_exception",
            },
        })()

    review_context = build_review_context(
        result.sources or [],
        result.confidence,
        trigger="low_confidence",
    )
    needs_review = bool(review_context["needs_teacher_review"])

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
            ai_answer=_build_review_ai_answer_payload(
                answer=result.answer,
                review_context=review_context,
            ),
        )
        db.add(review)
        log.info(
            "review_triggered",
            class_id=class_id,
            confidence=result.confidence,
            review_priority=review_context.get("review_priority"),
            review_reasons=",".join(review_context.get("review_reasons") or []),
        )

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
            review_context = build_review_context(
                message.sources or [],
                message.confidence,
                trigger="dislike",
                feedback=feedback,
            )
            review = ReviewItem(
                message_id=message_id,
                class_id=session.class_id,
                student_id=user_id,
                trigger="dislike",
                question_content=question,
                ai_answer=_build_review_ai_answer_payload(
                    answer=message.content,
                    review_context=review_context,
                ),
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
    return {
        "message_id": message_id,
        "feedback": feedback,
        "review_context": build_review_context(
            message.sources or [],
            message.confidence,
            trigger="dislike" if feedback == "dislike" else "feedback_only",
            feedback=feedback,
        ),
    }


def prepare_chat_attachments(attachments: Optional[List[dict]]) -> List[dict]:
    prepared: list[dict] = []
    for attachment in attachments or []:
        if not isinstance(attachment, dict):
            continue
        item = dict(attachment)
        file_path = item.get("file_path")
        file_type = item.get("file_type")
        file_name = item.get("name") or item.get("file_name") or "attachment"
        mime_type = item.get("mime_type") or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        if _attachment_is_expired(item):
            item["attachment_context"] = f"Attachment expired and should be re-uploaded: {file_name}"
            prepared.append(item)
            continue
        if not file_path:
            prepared.append(item)
            continue

        path = Path(file_path)
        if not path.exists():
            item["attachment_context"] = f"Attachment file is no longer available: {file_name}"
            prepared.append(item)
            continue

        if file_type == "image":
            item = _attach_image_payload(item, path, mime_type)

        item["attachment_context"] = _build_attachment_context(
            file_path=str(path),
            mime_type=mime_type,
            file_name=file_name,
            file_type=file_type or "other",
        )
        prepared.append(item)
    return prepared


def cleanup_expired_chat_attachments(user_id: str) -> dict:
    scope_dir = settings.LOCAL_STORAGE_ROOT / chat_attachment_scope_id(user_id)
    if settings.STORAGE_BACKEND != "local":
        return {"deleted_count": 0, "deleted_files": [], "supported": False}
    if not scope_dir.exists():
        return {"deleted_count": 0, "deleted_files": [], "supported": True}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, int(settings.CHAT_ATTACHMENT_TTL_HOURS)))
    deleted_files: list[str] = []
    for path in scope_dir.iterdir():
        if not path.is_file():
            continue
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if modified_at < cutoff:
            path.unlink(missing_ok=True)
            deleted_files.append(path.name)
    return {
        "deleted_count": len(deleted_files),
        "deleted_files": deleted_files,
        "supported": True,
        "scope": str(scope_dir),
    }


def _attach_image_payload(attachment: dict, path: Path, mime_type: str) -> dict:
    if attachment.get("data_url") or attachment.get("image_base64") or attachment.get("base64"):
        return attachment
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return {
        **attachment,
        "image_base64": encoded,
        "data_url": f"data:{mime_type};base64,{encoded}",
    }


def _build_attachment_context(
    *,
    file_path: str,
    mime_type: str,
    file_name: str,
    file_type: str,
) -> str:
    preprocess_result = preprocess_for_raganything(file_path, mime_type, file_name)
    snippets: list[str] = []
    for content in preprocess_result.content_list[:4]:
        if not isinstance(content, dict):
            continue
        text = (
            content.get("text")
            or content.get("caption")
            or content.get("ocr_text")
            or content.get("table_markdown")
            or content.get("equation")
            or ""
        )
        text = str(text).strip()
        if text:
            snippets.append(text[:300])

    preview = "\n".join(snippets).strip()
    if not preview:
        fallback = _fallback_attachment_parser.parse(file_path, mime_type, file_name)
        preview = str(fallback.get("text") or "").strip()
    if not preview:
        preview = f"Temporary {file_type} attachment: {file_name}."

    preview = preview[: max(200, int(settings.CHAT_ATTACHMENT_PREVIEW_CHARS))]
    warning_text = ""
    if preprocess_result.warnings:
        warning_text = f"\nWarnings: {', '.join(preprocess_result.warnings[:3])}"

    return (
        f"Attachment: {file_name}\n"
        f"Type: {file_type}\n"
        f"Preview:\n{preview}"
        f"{warning_text}"
    )


def _attachment_is_expired(attachment: dict) -> bool:
    expires_at = attachment.get("expires_at")
    if not expires_at:
        return False
    if isinstance(expires_at, datetime):
        expiry = expires_at
    else:
        try:
            expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        except ValueError:
            return False
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry <= datetime.now(timezone.utc)


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
            "quality": build_evidence_quality((item.message.sources if item.message else []) or [], item.message.confidence if item.message else 0.0),
            "review_context": build_review_context(
                (item.message.sources if item.message else []) or [],
                item.message.confidence if item.message else 0.0,
                trigger=item.trigger,
                feedback=item.message.feedback if item.message else None,
            ),
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
    faq_entry = _build_review_faq_entry(item, teacher_id, teacher_answer)

    if add_to_kb:
        rag = get_rag_engine()
        try:
            await rag.add_qa_pair(item.class_id, item.question_content, teacher_answer)
            sync_record.sync_status = "synced"
            sync_record.sync_note = "Teacher answer synced to fallback knowledge base"
            sync_record.synced_at = datetime.now(timezone.utc)
            _sync_review_feedback_to_kb_space(
                db,
                class_id=item.class_id,
                faq_entry={**faq_entry, "sync_status": "synced"},
            )
        except Exception as exc:
            log.error("add_qa_pair_failed", error=str(exc))
            sync_record.sync_status = "failed"
            sync_record.sync_note = str(exc)
            _sync_review_feedback_to_kb_space(
                db,
                class_id=item.class_id,
                faq_entry={**faq_entry, "sync_status": "failed", "sync_note": str(exc)},
            )
    else:
        sync_record.sync_status = "pending"
        sync_record.sync_note = "Sync skipped by teacher choice"
        _sync_review_feedback_to_kb_space(
            db,
            class_id=item.class_id,
            faq_entry={**faq_entry, "sync_status": "pending", "sync_note": sync_record.sync_note},
        )

    db.commit()

    return {
        "review_id": review_id,
        "status": "resolved",
        "sync_status": sync_record.sync_status,
        "sync_note": sync_record.sync_note,
    }


def _build_review_faq_entry(item: ReviewItem, teacher_id: str, teacher_answer: str) -> dict:
    topics = analytics_service.extract_terms_for_recommendation(item.question_content)[:6]
    reviewed_at = datetime.now(timezone.utc).isoformat()
    return {
        "review_id": item.id,
        "class_id": item.class_id,
        "question": item.question_content,
        "answer": teacher_answer,
        "teacher_id": teacher_id,
        "topics": topics,
        "trigger": item.trigger,
        "reviewed_at": reviewed_at,
    }


def _build_review_ai_answer_payload(*, answer: str, review_context: dict) -> str:
    reasons = ", ".join(review_context.get("review_reasons") or []) or "none"
    priority = review_context.get("review_priority") or "none"
    return (
        f"{answer}\n\n"
        f"[review_context] priority={priority}; reasons={reasons}"
    )


def _sync_review_feedback_to_kb_space(db: Session, *, class_id: str, faq_entry: dict) -> None:
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        return
    kb_space = db.query(KBSpace).filter(
        KBSpace.course_id == cls.course_id,
        KBSpace.class_id == class_id,
    ).first()
    if not kb_space:
        kb_space = KBSpace(
            course_id=cls.course_id,
            class_id=class_id,
            status="ready",
            extra_data={},
        )
        db.add(kb_space)
        db.flush()

    extra = kb_space.extra_data or {}
    review_faq = list(extra.get("review_faq") or [])
    review_faq = [
        row for row in review_faq
        if isinstance(row, dict) and row.get("review_id") != faq_entry.get("review_id")
    ]
    review_faq.append(faq_entry)
    review_faq = review_faq[-20:]

    topic_counts: dict[str, int] = {}
    for row in review_faq:
        for topic in row.get("topics") or []:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

    extra["review_faq"] = review_faq
    extra["recommendation_signals"] = {
        "review_topic_counts": topic_counts,
        "review_faq_count": len(review_faq),
        "last_review_sync_at": faq_entry.get("reviewed_at"),
    }
    kb_space.extra_data = extra
    db.add(kb_space)
