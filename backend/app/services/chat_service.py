"""AI chat orchestration service for the AI tutor system."""
import base64
import asyncio
import mimetypes
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Awaitable, Callable, List, Optional

import httpx
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session

import app.storage as storage
from app.ai.base import LLMMessage
from app.ai.providers.mock_llm import MockLLMProvider
from app.core.config import settings
from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.logging import get_logger
from app.integrations.rag import get_rag_engine
from app.integrations.parser.simple import SimpleParserProvider
from app.integrations.preprocessors import preprocess_for_raganything
from app.integrations.rag.quality import build_evidence_quality, build_review_context
from app.models.course import Class, ClassMember, Material, Submission, Task
from app.models.chat import ChatCitation, ChatMessage, ChatSession, ReviewItem, ReviewSyncRecord
from app.models.knowledge import FileParseTask, KBSpace
from app.models.user import User
from app.services import admin_service, analytics_service, audit_service, conversation_context_service, model_routing_service, rag_metrics_service
from app.services.question_router import QuestionRoute, classify_direct_intent, route_question

log = get_logger(__name__)
_fallback_attachment_parser = SimpleParserProvider()
ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]
THINKING_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>", re.IGNORECASE | re.DOTALL)


def _strip_thinking_blocks(text: str) -> str:
    if not text or not bool(getattr(settings, "STRIP_THINKING_BLOCKS", True)):
        return text or ""
    return THINKING_BLOCK_RE.sub("", text).strip()


def _qwen_thinking_extra_body(
    *,
    model: str,
    enable_thinking: bool | None,
    thinking_budget: int | None,
    top_k: int | None = None,
    min_p: float | None = None,
    repetition_penalty: float | None = None,
) -> dict[str, Any] | None:
    if "qwen" not in str(model or "").lower():
        return None
    body: dict[str, Any] = {}
    if enable_thinking is not None:
        body["enable_thinking"] = bool(enable_thinking)
    if thinking_budget is not None and int(thinking_budget) > 0:
        body["thinking_budget"] = int(thinking_budget)
    if top_k is not None and int(top_k) > 0:
        body["top_k"] = int(top_k)
    if min_p is not None:
        body["min_p"] = float(min_p)
    if repetition_penalty is not None:
        body["repetition_penalty"] = float(repetition_penalty)
    return body or None


def _looks_like_thinking_param_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        key in text
        for key in ("enable_thinking", "thinking_budget", "top_k", "min_p", "repetition_penalty")
    )


async def _emit_progress(
    progress_callback: Optional[ProgressCallback],
    *,
    stage: str,
    status: str,
    label: str,
    started_at: float,
    details: Optional[dict[str, Any]] = None,
) -> None:
    if progress_callback is None:
        return
    event: dict[str, Any] = {
        "stage": stage,
        "status": status,
        "label": label,
        "elapsed_ms": round((perf_counter() - started_at) * 1000, 2),
    }
    if details:
        event["details"] = details
    try:
        await progress_callback(event)
    except Exception as exc:  # pragma: no cover - progress must never break chat
        log.debug("chat_progress_emit_failed", stage=stage, error=str(exc))

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


def delete_session(db: Session, session_id: str, user_id: str) -> dict:
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id,
        ChatSession.is_active == True,
    ).first()
    if not session:
        raise NotFoundException("Chat session not found")
    session.is_active = False
    session.updated_at = datetime.now(timezone.utc)
    db.add(session)
    db.commit()
    return {"id": session.id, "deleted": True}


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
        "attachments": sanitize_chat_attachments_for_history(message.attachments),
        "sources": sources,
        "suggestions": message.suggestions,
        "confidence": message.confidence,
        "quality": quality,
        "review_context": review_context,
        "feedback": message.feedback,
        "needs_review": message.needs_review,
        "created_at": message.created_at,
    }


def _role_label(role: str) -> str:
    return {"student": "学生", "teacher": "教师", "admin": "管理员"}.get(role, role)


async def send_message(
    db: Session,
    class_id: str,
    user_id: str,
    content: str,
    session_id: Optional[str] = None,
    attachments: Optional[List[dict]] = None,
    role: str = "student",
    answer_mode: str | None = "auto",
    progress_callback: Optional[ProgressCallback] = None,
) -> dict:
    progress_started = perf_counter()
    await _emit_progress(
        progress_callback,
        stage="request_received",
        status="done",
        label="问题已提交",
        started_at=progress_started,
    )
    await _emit_progress(
        progress_callback,
        stage="conversation_context",
        status="running",
        label="正在理解上下文与追问关系",
        started_at=progress_started,
    )
    session = get_or_create_session(db, class_id, user_id, session_id)
    prepared_attachments = prepare_chat_attachments(attachments, user_id=user_id)
    conversation_context = conversation_context_service.build_conversation_context(
        db,
        session,
        content,
        max_recent_turns=10,
    )
    retrieval_question = conversation_context.standalone_question or content
    await _emit_progress(
        progress_callback,
        stage="conversation_context",
        status="done",
        label="上下文理解完成",
        started_at=progress_started,
        details=conversation_context.to_rag_meta(),
    )

    if not session.title:
        session.title = content[:50]
        db.add(session)

    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=content,
        attachments=sanitize_chat_attachments_for_history(prepared_attachments),
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
    audit_service.record_event(
        event_type="chat.query_started",
        actor_id=user_id,
        actor_role=role,
        target_type="chat_message",
        target_id=user_msg.id,
        class_id=class_id,
        summary=f"{_role_label(role)}提交 AI 助教问题",
        extra_data={
            "session_id": session.id,
            "question_preview": content[:200],
            "answer_mode": answer_mode,
            "attachment_count": len(prepared_attachments or []),
        },
    )
    await _emit_progress(
        progress_callback,
        stage="message_saved",
        status="done",
        label="消息已记录，正在判断是否需要检索",
        started_at=progress_started,
    )

    question_route = route_question(
        question=content,
        role=role,
        answer_mode=answer_mode,
        has_attachments=bool(prepared_attachments),
    )
    await _emit_progress(
        progress_callback,
        stage="question_route",
        status="done",
        label=_route_progress_label(question_route),
        started_at=progress_started,
        details=question_route.to_meta(),
    )

    routed_answer = _build_routed_answer(
        db,
        class_id,
        content,
        role=role,
        user_id=user_id,
        route=question_route,
    )
    if routed_answer:
        await _emit_progress(
            progress_callback,
            stage="direct_answer",
            status="done",
            label="无需检索，已生成直接回复",
            started_at=progress_started,
        )
        direct_result = _persist_direct_ai_answer(
            db=db,
            session=session,
            user_msg=user_msg,
            answer=routed_answer["answer"],
            suggestions=routed_answer.get("suggestions") or [],
            confidence=routed_answer.get("confidence", 1.0),
        )
        direct_result["route_meta"] = _build_response_route_meta(question_route, retrieval_used=False)
        audit_service.record_event(
            event_type="chat.query_completed",
            actor_id=user_id,
            actor_role=role,
            target_type="chat_message",
            target_id=direct_result["ai_message"]["id"],
            class_id=class_id,
            summary=f"{_role_label(role)}的 AI 助教问题已直接回答",
            extra_data={
                "session_id": session.id,
                "user_message_id": user_msg.id,
                "question_preview": content[:200],
                "route": question_route.route,
                "intent": question_route.intent,
                "retrieval_used": False,
                "latency_ms": round((perf_counter() - progress_started) * 1000, 2),
            },
        )
        await _emit_progress(
            progress_callback,
            stage="completed",
            status="done",
            label="回答生成完成",
            started_at=progress_started,
        )
        return direct_result

    if question_route.route in {"quick_llm", "teacher_tool"}:
        await _emit_progress(
            progress_callback,
            stage="direct_generation",
            status="running",
            label="正在生成无需检索的快速回复",
            started_at=progress_started,
            details=question_route.to_meta(),
        )
        generated_answer = await _generate_direct_llm_answer(
            db=db,
            class_id=class_id,
            question=content,
            role=role,
            route=question_route,
            attachments=prepared_attachments,
        )
        await _emit_progress(
            progress_callback,
            stage="direct_generation",
            status="done",
            label="快速回复生成完成",
            started_at=progress_started,
            details=question_route.to_meta(),
        )
        direct_result = _persist_direct_ai_answer(
            db=db,
            session=session,
            user_msg=user_msg,
            answer=generated_answer,
            suggestions=_default_direct_suggestions(role),
            confidence=0.82,
        )
        direct_result["route_meta"] = _build_response_route_meta(question_route, retrieval_used=False)
        audit_service.record_event(
            event_type="chat.query_completed",
            actor_id=user_id,
            actor_role=role,
            target_type="chat_message",
            target_id=direct_result["ai_message"]["id"],
            class_id=class_id,
            summary=f"{_role_label(role)}的 AI 助教问题已快速回答",
            extra_data={
                "session_id": session.id,
                "user_message_id": user_msg.id,
                "question_preview": content[:200],
                "route": question_route.route,
                "intent": question_route.intent,
                "retrieval_used": False,
                "latency_ms": round((perf_counter() - progress_started) * 1000, 2),
            },
        )
        await _emit_progress(
            progress_callback,
            stage="completed",
            status="done",
            label="回答生成完成",
            started_at=progress_started,
        )
        return direct_result

    history = conversation_context.recent_turns[-10:]

    persisted_model_config = admin_service.get_model_config(db)
    rag = get_rag_engine(requested_engine=persisted_model_config.get("rag_engine"))
    routing_snapshot = model_routing_service.build_model_routing_snapshot(persisted_model_config)
    routing_meta = model_routing_service.flatten_routing_snapshot(routing_snapshot)
    await _emit_progress(
        progress_callback,
        stage="rag_prepare",
        status="done",
        label="课程知识库与模型路由已准备",
        started_at=progress_started,
        details={
            "rag_engine": persisted_model_config.get("rag_engine") or settings.RAG_ENGINE,
            "llm_backend": routing_meta.get("llm_backend"),
            "embedding_backend": routing_meta.get("embedding_backend"),
        },
    )
    rag_started = perf_counter()
    rag_latency_ms = None
    try:
        await _emit_progress(
            progress_callback,
            stage="rag_query",
            status="running",
            label="正在检索课程资料并生成回答",
            started_at=progress_started,
        )
        result = await rag.query(
            question=retrieval_question,
            class_id=class_id,
            history=history,
            attachments=prepared_attachments,
            role=role,
            progress_callback=progress_callback,
        )
        rag_latency_ms = round((perf_counter() - rag_started) * 1000, 2)
        await _emit_progress(
            progress_callback,
            stage="rag_query",
            status="done",
            label="课程资料检索与回答生成完成",
            started_at=progress_started,
            details={"latency_ms": rag_latency_ms},
        )
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
                "query_trace": result_meta.get("query_trace"),
                "question_intent": result_meta.get("question_intent"),
                "question_intent_confidence": result_meta.get("question_intent_confidence"),
                "question_intent_signals": result_meta.get("question_intent_signals"),
                "retrieval_focus_terms": result_meta.get("retrieval_focus_terms"),
                "conversation_context": conversation_context.to_rag_meta(),
                "question_route": question_route.to_meta(),
                "llm_backend": routing_meta.get("llm_backend"),
                "embedding_backend": routing_meta.get("embedding_backend"),
                "vlm_backend": routing_meta.get("vlm_backend"),
                "reranker_backend": routing_meta.get("reranker_backend"),
            },
        )
    except Exception as exc:
        rag_latency_ms = round((perf_counter() - rag_started) * 1000, 2)
        log.error("rag_query_failed", error=str(exc))
        await _emit_progress(
            progress_callback,
            stage="rag_query",
            status="error",
            label="检索生成失败，正在返回兜底回复",
            started_at=progress_started,
            details={"error": str(exc), "latency_ms": rag_latency_ms},
        )
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
                "question_route": question_route.to_meta(),
                "llm_backend": routing_meta.get("llm_backend"),
                "embedding_backend": routing_meta.get("embedding_backend"),
                "vlm_backend": routing_meta.get("vlm_backend"),
                "reranker_backend": routing_meta.get("reranker_backend"),
            },
        )
        result = type("R", (), {
            "answer": "AI助教暂时不可用，请稍后再试。如果问题比较紧急，可以先联系课程教师。",
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
    await _emit_progress(
        progress_callback,
        stage="persist_answer",
        status="running",
        label="正在保存回答与引用来源",
        started_at=progress_started,
    )
    db.commit()
    db.refresh(ai_msg)
    result_meta = getattr(result, "meta", {}) or {}
    used_fallback = bool(result_meta.get("used_fallback"))
    audit_service.record_event(
        event_type="chat.query_failed" if used_fallback else "chat.query_completed",
        status="failed" if used_fallback else "success",
        actor_id=user_id,
        actor_role=role,
        target_type="chat_message",
        target_id=ai_msg.id,
        class_id=class_id,
        summary=(
            f"{_role_label(role)}的 AI 助教问题触发兜底回复"
            if used_fallback
            else f"{_role_label(role)}的 AI 助教问题已完成检索回答"
        ),
        extra_data={
            "session_id": session.id,
            "user_message_id": user_msg.id,
            "question_preview": content[:200],
            "route": question_route.route,
            "intent": question_route.intent,
            "retrieval_used": True,
            "engine": result_meta.get("engine"),
            "query_mode": result_meta.get("query_mode"),
            "query_method": result_meta.get("query_method"),
            "used_fallback": used_fallback,
            "fallback_reason": result_meta.get("fallback_reason"),
            "latency_ms": round((perf_counter() - progress_started) * 1000, 2),
            "source_count": len(result.sources or []),
            "confidence": result.confidence,
        },
    )
    await _emit_progress(
        progress_callback,
        stage="completed",
        status="done",
        label="回答生成完成",
        started_at=progress_started,
    )

    return {
        "session_id": session.id,
        "user_message": _msg_to_dict(user_msg),
        "ai_message": _msg_to_dict(ai_msg),
        "route_meta": _build_response_route_meta(question_route, retrieval_used=True),
    }


def _persist_direct_ai_answer(
    *,
    db: Session,
    session: ChatSession,
    user_msg: ChatMessage,
    answer: str,
    suggestions: list[str] | None = None,
    confidence: float = 1.0,
) -> dict:
    ai_msg = ChatMessage(
        session_id=session.id,
        role="ai",
        content=answer,
        sources=[],
        suggestions=suggestions or [],
        confidence=confidence,
        needs_review=False,
    )
    db.add(ai_msg)
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ai_msg)
    return {
        "session_id": session.id,
        "user_message": _msg_to_dict(user_msg),
        "ai_message": _msg_to_dict(ai_msg),
    }


def _build_routed_answer(
    db: Session,
    class_id: str,
    content: str,
    role: str = "student",
    user_id: str | None = None,
    route: QuestionRoute | None = None,
) -> dict | None:
    intent = route.intent if route and route.route in {
        "direct_answer",
        "system_status",
        "user_profile",
        "off_topic",
    } else _classify_direct_intent(content)
    if intent == "greeting":
        return {
            "answer": _build_greeting_answer(role),
            "suggestions": _default_direct_suggestions(role),
        }
    if intent == "identity":
        return {
            "answer": "我是珞樱学堂 AI 助教，负责在当前课程中帮助你理解知识点、整理学习思路，并结合课程资料回答问题。",
            "suggestions": _default_direct_suggestions(role),
        }
    if intent == "capability":
        return {
            "answer": _build_capability_answer(role),
            "suggestions": [
                "帮我解释一个课程概念",
                "目前知识库里有资料吗",
                "我可以上传资料让你分析吗",
            ],
        }
    if intent == "kb_status":
        return {
            "answer": _build_kb_status_answer(db, class_id),
            "suggestions": [
                "老师上传了哪些资料",
                "哪些资料已经完成知识库构建",
                "我可以问哪些课程问题",
            ],
        }
    if intent == "user_profile":
        return {
            "answer": _build_user_profile_answer(db, user_id),
            "suggestions": _default_direct_suggestions(role),
        }
    if intent == "off_topic":
        return {
            "answer": "这个问题看起来和当前课程学习关系不大。我主要负责课程答疑、资料解释、学习建议和知识点梳理。你可以换成课程相关问题继续问我。",
            "suggestions": _default_direct_suggestions(role),
            "confidence": 0.9,
        }
    return None


def _classify_direct_intent(content: str) -> str | None:
    return classify_direct_intent(content)


def _normalize_intent_text(content: str) -> str:
    text = str(content or "").strip().lower()
    text = re.sub(r"[\s，。！？!?、,.；;：:\"'“”‘’（）()\[\]{}<>《》]+", "", text)
    return text


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _build_greeting_answer(role: str = "student") -> str:
    if str(role or "").lower() in {"teacher", "admin", "instructor"}:
        return (
            "您好，我是珞樱学堂 AI 助教。您可以让我协助整理课程知识点、生成教学材料、"
            "分析学生问题，或根据课程资料回答教学相关问题。"
        )
    return (
        "你好，我是珞樱学堂 AI 助教。你可以直接问我课程里的概念、例题、作业思路，"
        "也可以上传资料让我结合内容帮你解释。"
    )


def _build_capability_answer(role: str = "student") -> str:
    if str(role or "").lower() in {"teacher", "admin", "instructor"}:
        return (
            "我可以协助您完成这些教学相关工作：\n"
            "1. 根据课程资料回答学生或教师提出的问题。\n"
            "2. 帮助梳理知识点、易错点和课堂讲解思路。\n"
            "3. 结合上传的文档、图片、课件生成摘要或教学建议。\n"
            "4. 对低置信度或学生反馈不佳的回答生成待教师审核的问题。\n\n"
            "如果课程资料还没有完成知识库构建，我会明确提示资料不足。"
        )
    return (
        "我可以帮助你做这些课程学习相关的事情：\n"
        "1. 解答课程概念、例题和作业思路问题。\n"
        "2. 根据教师上传的课程资料进行解释和总结。\n"
        "3. 帮你梳理学习重点、易错点和复习方向。\n"
        "4. 支持你上传图片或文档，让我结合内容分析。\n\n"
        "如果当前知识库没有相关资料，我会告诉你资料不足，而不是随便编答案。"
    )


def _build_kb_status_answer(db: Session, class_id: str) -> str:
    materials = db.query(Material).filter(
        Material.class_id == class_id,
        Material.is_active == True,
    ).order_by(Material.created_at.desc()).all()
    tasks = db.query(FileParseTask).filter(FileParseTask.class_id == class_id).all()
    kb_space = db.query(KBSpace).filter(KBSpace.class_id == class_id).order_by(KBSpace.updated_at.desc()).first()

    if not materials:
        return (
            "当前课程知识库里还没有可用资料。教师上传课程资料并完成知识库构建后，"
            "我就可以结合资料回答更具体的课程问题。"
        )

    material_status = Counter(str(material.kb_status or "unknown") for material in materials)
    task_status = Counter(str(task.status or "unknown") for task in tasks)
    indexed = material_status.get("indexed", 0)
    processing = material_status.get("processing", 0) + material_status.get("pending", 0)
    failed = material_status.get("failed", 0)
    recent_names = "、".join(material.file_name for material in materials[:3])

    lines = [
        f"当前课程已上传 {len(materials)} 份资料，其中 {indexed} 份已完成知识库构建。",
    ]
    if processing:
        lines.append(f"还有 {processing} 份资料正在等待或处理中。")
    if failed:
        lines.append(f"有 {failed} 份资料处理失败，需要教师在资料管理中查看原因。")
    if recent_names:
        lines.append(f"最近的资料包括：{recent_names}。")
    if kb_space:
        lines.append(
            f"知识库空间状态：{kb_space.status}，文档数 {kb_space.document_count or 0}，"
            f"分块数 {kb_space.chunk_count or 0}。"
        )
    if task_status:
        completed_tasks = task_status.get("completed", 0)
        failed_tasks = task_status.get("failed", 0)
        processing_tasks = task_status.get("processing", 0) + task_status.get("pending", 0)
        lines.append(
            f"解析任务状态：完成 {completed_tasks} 个，处理中/等待 {processing_tasks} 个，失败 {failed_tasks} 个。"
        )
    if indexed <= 0:
        lines.append("目前还没有已索引资料，所以课程知识类问题可能无法得到可靠回答。")
    return "\n".join(lines)


def _build_user_profile_answer(db: Session, user_id: str | None) -> str:
    if not user_id:
        return "我暂时没有拿到你的登录身份信息，所以不能可靠判断你叫什么。"
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return "我暂时没有在系统中找到你的用户资料，所以不能可靠判断你叫什么。"
    role_label = {
        "student": "学生",
        "teacher": "教师",
        "admin": "管理员",
    }.get(str(user.role or ""), str(user.role or "用户"))
    id_text = user.student_id or user.teacher_id
    extra = f"，编号是 {id_text}" if id_text else ""
    return f"系统资料显示，你的姓名是 {user.real_name}，身份是{role_label}{extra}。"


def _route_progress_label(route: QuestionRoute) -> str:
    if route.route == "course_rag":
        return "已判断需要检索课程资料"
    if route.route == "quick_llm":
        return "已选择快速回答，不进入课程检索"
    if route.route == "teacher_tool":
        return "已识别为教学工具任务"
    if route.route == "system_status":
        return "已识别为系统状态查询"
    if route.route == "user_profile":
        return "已识别为个人资料查询"
    if route.route == "off_topic":
        return "已识别为非课程相关问题"
    return "已判断无需检索课程资料"


async def _generate_direct_llm_answer(
    *,
    db: Session,
    class_id: str,
    question: str,
    role: str,
    route: QuestionRoute,
    attachments: list[dict] | None = None,
) -> str:
    system_prompt = _build_direct_llm_system_prompt(role=role, route=route)
    context = _build_direct_generation_context(db=db, class_id=class_id, route=route)
    direct_attachments = attachments or []
    attachment_context = _build_direct_attachment_context(direct_attachments)
    if attachment_context:
        context = f"{context}\n\n本轮附件摘要：\n{attachment_context}".strip()
    user_content = question if not context else f"{question}\n\n可用系统上下文：\n{context}"
    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=user_content),
    ]
    try:
        return await _call_generation_llm(db=db, messages=messages, attachments=direct_attachments)
    except Exception as exc:
        log.warning("direct_llm_generation_failed", route=route.route, error=str(exc))
        if route.route == "teacher_tool":
            return _teacher_tool_fallback_answer(question=question, route=route, context=context)
        return (
            "快速回答暂时不可用。你可以切换到“严格课程资料”模式，让我根据课程知识库检索后回答。"
        )


def _build_direct_llm_system_prompt(*, role: str, route: QuestionRoute) -> str:
    if route.route == "teacher_tool":
        return (
            "你是珞樱学堂的教师助教。请用简体中文回答，面向教师，输出结构化、可直接使用的教学内容。"
            "如果系统上下文不足，要明确说明哪些部分需要教师补充，不要伪造学生数据。"
        )
    return (
        "你是珞樱学堂 AI 助教。请用简体中文快速回答用户问题。"
        "当前模式不要求检索课程知识库，因此不要声称答案来自课程资料；如涉及课程事实，应提醒用户可切换到检索模式核验。"
        "如果用户上传了图片，图片会作为多模态输入直接提供给你，请直接阅读图片内容并回答。"
    )


async def _call_generation_llm(
    *,
    db: Session,
    messages: list[LLMMessage],
    attachments: list[dict] | None = None,
) -> str:
    persisted_model_config = admin_service.get_model_config(db)
    routing_snapshot = model_routing_service.build_model_routing_snapshot(persisted_model_config)
    generation = routing_snapshot.get("generation") or {}
    if generation.get("effective_backend") == "mock":
        return await MockLLMProvider().chat(messages)

    api_base = str(generation.get("api_base") or settings.EFFECTIVE_LLM_API_BASE or "").strip()
    api_key = settings.EFFECTIVE_LLM_API_KEY or "local"
    model = str(generation.get("model") or settings.LLM_MODEL or "").strip()
    if not api_base or not model:
        return await MockLLMProvider().chat(messages)

    wire_api = str(settings.LLM_WIRE_API or "chat_completions").strip().lower()
    if wire_api == "responses":
        answer = await _call_responses_generation_api(
            messages=messages,
            attachments=attachments or [],
            model=model,
            api_base=api_base,
            api_key=api_key,
            generation_route=generation,
        )
        if answer:
            return answer
        raise RuntimeError("quick LLM responses API returned empty output")

    try:
        import openai  # type: ignore

        AsyncOpenAI = getattr(openai, "AsyncOpenAI")
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        raise RuntimeError("openai package is unavailable for quick LLM generation") from exc

    client = AsyncOpenAI(api_key=api_key, base_url=api_base, timeout=60)
    chat_messages = _build_chat_completion_messages(messages=messages, attachments=attachments or [])
    request_kwargs: dict[str, Any] = {
        "model": model,
        "messages": chat_messages,
        "temperature": generation.get("temperature", settings.LLM_TEMPERATURE),
        "top_p": generation.get("top_p", settings.LLM_TOP_P),
        "max_tokens": generation.get("max_tokens", settings.LLM_MAX_TOKENS),
        "presence_penalty": generation.get("presence_penalty", settings.LLM_PRESENCE_PENALTY),
        "frequency_penalty": generation.get("frequency_penalty", settings.LLM_FREQUENCY_PENALTY),
    }
    extra_body = _qwen_thinking_extra_body(
        model=model,
        enable_thinking=generation.get("enable_thinking", settings.LLM_ENABLE_THINKING),
        thinking_budget=generation.get("thinking_budget", settings.LLM_THINKING_BUDGET),
        top_k=generation.get("top_k", settings.LLM_TOP_K),
        min_p=generation.get("min_p", settings.LLM_MIN_P),
        repetition_penalty=generation.get("repetition_penalty", settings.LLM_REPETITION_PENALTY),
    )
    if extra_body:
        request_kwargs["extra_body"] = extra_body
    try:
        response = await client.chat.completions.create(**request_kwargs)
    except Exception as exc:
        if extra_body and _looks_like_thinking_param_error(exc):
            request_kwargs.pop("extra_body", None)
            response = await client.chat.completions.create(**request_kwargs)
        else:
            raise
    return _strip_thinking_blocks(response.choices[0].message.content or "")


async def _call_responses_generation_api(
    *,
    messages: list[LLMMessage],
    attachments: list[dict],
    model: str,
    api_base: str,
    api_key: str,
    generation_route: dict[str, Any] | None = None,
) -> str:
    input_items = _build_responses_input_items(messages=messages, attachments=attachments)
    endpoint = api_base.rstrip("/") + "/responses"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "model": model,
        "input": input_items,
        "temperature": (generation_route or {}).get("temperature", settings.LLM_TEMPERATURE),
        "top_p": (generation_route or {}).get("top_p", settings.LLM_TOP_P),
        "max_tokens": (generation_route or {}).get("max_tokens", settings.LLM_MAX_TOKENS),
        "presence_penalty": (generation_route or {}).get("presence_penalty", settings.LLM_PRESENCE_PENALTY),
        "frequency_penalty": (generation_route or {}).get("frequency_penalty", settings.LLM_FREQUENCY_PENALTY),
    }
    extra_body = _qwen_thinking_extra_body(
        model=model,
        enable_thinking=(generation_route or {}).get("enable_thinking", settings.LLM_ENABLE_THINKING),
        thinking_budget=(generation_route or {}).get("thinking_budget", settings.LLM_THINKING_BUDGET),
        top_k=(generation_route or {}).get("top_k", settings.LLM_TOP_K),
        min_p=(generation_route or {}).get("min_p", settings.LLM_MIN_P),
        repetition_penalty=(generation_route or {}).get("repetition_penalty", settings.LLM_REPETITION_PENALTY),
    )
    thinking_payload_keys = set(extra_body or {})
    if extra_body:
        payload.update(extra_body)
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=120.0) as client:
        for attempt in range(3):
            try:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                break
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if (
                    thinking_payload_keys
                    and exc.response.status_code in {400, 422}
                    and _looks_like_thinking_param_error(exc)
                ):
                    for key in thinking_payload_keys:
                        payload.pop(key, None)
                    thinking_payload_keys.clear()
                    response = await client.post(endpoint, headers=headers, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    break
                if exc.response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
            except Exception as exc:
                last_error = exc
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
        else:  # pragma: no cover
            raise last_error or RuntimeError("quick LLM responses API failed")

    if data.get("output_text"):
        return _strip_thinking_blocks(str(data["output_text"]))

    texts: list[str] = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if text:
                texts.append(str(text))
    return _strip_thinking_blocks("\n".join(texts))


def _build_responses_input_items(*, messages: list[LLMMessage], attachments: list[dict]) -> list[dict]:
    image_items = _direct_image_input_items(attachments, wire_api="responses")
    last_user_index = _last_user_message_index(messages)
    input_items: list[dict] = []
    for index, item in enumerate(messages):
        if not item.content:
            continue
        content: list[dict] = [{"type": "input_text", "text": item.content}]
        if index == last_user_index and image_items:
            content.extend(image_items)
        input_items.append({"role": item.role, "content": content})
    return input_items


def _build_chat_completion_messages(*, messages: list[LLMMessage], attachments: list[dict]) -> list[dict]:
    image_items = _direct_image_input_items(attachments, wire_api="chat_completions")
    last_user_index = _last_user_message_index(messages)
    chat_messages: list[dict] = []
    for index, item in enumerate(messages):
        if not item.content:
            continue
        if index == last_user_index and image_items:
            chat_messages.append({
                "role": item.role,
                "content": [{"type": "text", "text": item.content}, *image_items],
            })
        else:
            chat_messages.append({"role": item.role, "content": item.content})
    return chat_messages


def _direct_image_input_items(attachments: list[dict], *, wire_api: str) -> list[dict]:
    items: list[dict] = []
    for attachment in attachments[:3]:
        if str((attachment or {}).get("file_type") or "").lower() != "image":
            continue
        image_url = _direct_image_url(attachment)
        if not image_url:
            continue
        if wire_api == "responses":
            items.append({"type": "input_image", "image_url": image_url})
        else:
            items.append({"type": "image_url", "image_url": {"url": image_url}})
    return items


def _direct_image_url(attachment: dict) -> str:
    data_url = str((attachment or {}).get("data_url") or "").strip()
    if data_url.startswith("data:image"):
        return data_url
    image_data = (
        (attachment or {}).get("image_base64")
        or (attachment or {}).get("base64")
        or (attachment or {}).get("image_data")
    )
    if not image_data:
        return ""
    mime_type = str((attachment or {}).get("mime_type") or "image/png")
    return f"data:{mime_type};base64,{image_data}"


def _last_user_message_index(messages: list[LLMMessage]) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].role == "user":
            return index
    return None


def _build_direct_generation_context(*, db: Session, class_id: str, route: QuestionRoute) -> str:
    if route.intent != "class_learning_analysis":
        return ""
    student_count = db.query(ClassMember).filter(
        ClassMember.class_id == class_id,
        ClassMember.role == "student",
    ).count()
    task_count = db.query(Task).filter(Task.class_id == class_id, Task.is_published == True).count()
    total_questions = db.query(ChatMessage).join(
        ChatSession, ChatMessage.session_id == ChatSession.id,
    ).filter(
        ChatSession.class_id == class_id,
        ChatMessage.role == "user",
    ).count()
    submission_count = db.query(Submission).join(
        Task, Submission.task_id == Task.id,
    ).filter(Task.class_id == class_id).count()
    review_count = db.query(ReviewItem).filter(
        ReviewItem.class_id == class_id,
        ReviewItem.status == "pending",
    ).count()
    return (
        f"班级学生数：{student_count}\n"
        f"已发布任务数：{task_count}\n"
        f"学生提问数：{total_questions}\n"
        f"任务提交记录数：{submission_count}\n"
        f"待教师审核回答数：{review_count}"
    )


def _build_direct_attachment_context(attachments: list[dict]) -> str:
    lines: list[str] = []
    for attachment in attachments[:3]:
        is_image = str((attachment or {}).get("file_type") or "").lower() == "image"
        context = str((attachment or {}).get("attachment_context") or "").strip()
        name = str((attachment or {}).get("name") or ("图片" if is_image else "附件"))
        if is_image and _direct_image_url(attachment):
            lines.append(f"- {name}: 原图已作为多模态输入直接发送给快速回答模型。")
            continue
        if not context:
            continue
        lines.append(f"- {name}: {context[:1200]}")
    return "\n".join(lines)


def _teacher_tool_fallback_answer(*, question: str, route: QuestionRoute, context: str) -> str:
    if route.intent == "class_learning_analysis":
        context_text = f"\n\n当前可用数据：\n{context}" if context else ""
        return (
            "我可以协助做班级学情分析，但当前快速生成模型不可用。"
            f"{context_text}\n\n建议从学生提问热点、任务完成情况、待审核问题和薄弱知识点四个方面生成分析报告。"
        )
    return (
        "我可以协助生成教案、练习题或课堂活动，但当前快速生成模型不可用。"
        "你可以稍后重试，或切换到严格课程资料模式，先让我检索课程资料后再辅助整理。"
    )


def _build_response_route_meta(route: QuestionRoute, *, retrieval_used: bool) -> dict:
    meta = route.to_meta()
    meta["retrieval_used"] = bool(retrieval_used)
    meta["source_policy"] = "strict_course" if retrieval_used else "none"
    meta["display_label"] = _route_display_label(meta)
    return meta


def _route_display_label(meta: dict) -> str:
    route = meta.get("route")
    mode = meta.get("answer_mode")
    if route == "course_rag":
        return "检索" if mode == "strict_course" else "课程检索"
    if route == "quick_llm":
        return "快速回答"
    if route == "teacher_tool":
        return "教学"
    if route in {"system_status", "user_profile"}:
        return "系统查询"
    if route == "off_topic":
        return "课程范围外"
    return "直接回答"


def _default_direct_suggestions(role: str = "student") -> list[str]:
    if str(role or "").lower() in {"teacher", "admin", "instructor"}:
        return [
            "目前知识库里有资料吗",
            "帮我整理本课程的教学重点",
            "学生可能会在哪些地方困惑",
        ]
    return [
        "目前知识库里有资料吗",
        "帮我解释一个课程概念",
        "帮我梳理本章学习重点",
    ]


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
    session = db.query(ChatSession).filter(ChatSession.id == message.session_id).first()
    if not session or session.user_id != user_id:
        raise ForbiddenException("You do not have access to this message")
    if message.role != "ai":
        raise ForbiddenException("Only AI answers can receive this feedback")
    message.feedback = feedback
    message.feedback_reason = reason

    if feedback == "dislike":
        existing = db.query(ReviewItem).filter(ReviewItem.message_id == message_id).first()
        if not existing:
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


def prepare_chat_attachments(attachments: Optional[List[dict]], user_id: str | None = None) -> List[dict]:
    prepared: list[dict] = []
    for attachment in attachments or []:
        if not isinstance(attachment, dict):
            continue
        item = dict(attachment)
        file_path = _resolve_chat_attachment_file_path(item, user_id=user_id)
        if file_path:
            item["file_path"] = file_path
        file_type = item.get("file_type")
        file_name = item.get("name") or item.get("file_name") or "attachment"
        mime_type = item.get("mime_type") or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        if _attachment_is_expired(item):
            item["attachment_context"] = f"Attachment expired and should be re-uploaded: {file_name}"
            prepared.append(item)
            continue
        if not file_path:
            if item.get("storage_key"):
                item["attachment_context"] = f"Attachment file is no longer available: {file_name}"
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


def sanitize_chat_attachments_for_history(attachments: Optional[List[dict]]) -> List[dict]:
    """Keep only display-safe attachment metadata in persisted chat history."""
    sanitized: list[dict] = []
    for attachment in attachments or []:
        if not isinstance(attachment, dict):
            continue
        file_name = str(attachment.get("name") or attachment.get("file_name") or "attachment")
        mime_type = str(
            attachment.get("mime_type")
            or attachment.get("mimeType")
            or mimetypes.guess_type(file_name)[0]
            or "application/octet-stream"
        )
        file_type = str(attachment.get("file_type") or attachment.get("fileType") or _guess_attachment_file_type(file_name, mime_type))
        try:
            size = int(attachment.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        item = {
            "id": str(attachment.get("id") or attachment.get("storage_key") or attachment.get("storageKey") or file_name),
            "name": file_name,
            "size": size,
            "mime_type": mime_type,
            "file_type": file_type,
        }
        storage_key = attachment.get("storage_key") or attachment.get("storageKey")
        if storage_key:
            item["storage_key"] = str(storage_key)
        expires_at = attachment.get("expires_at") or attachment.get("expiresAt")
        if expires_at:
            item["expires_at"] = expires_at
        sanitized.append(item)
    return sanitized


def _guess_attachment_file_type(file_name: str, mime_type: str) -> str:
    lower_name = file_name.lower()
    lower_mime = mime_type.lower()
    if lower_mime.startswith("image/"):
        return "image"
    if lower_mime == "application/pdf" or lower_name.endswith(".pdf"):
        return "pdf"
    if lower_name.endswith((".docx", ".doc")):
        return "docx"
    if lower_name.endswith((".md", ".markdown")):
        return "md"
    if lower_name.endswith((".py", ".js", ".ts", ".tsx", ".java", ".cpp", ".c", ".go", ".rs")):
        return "code"
    return "other"


def _resolve_chat_attachment_file_path(attachment: dict, user_id: str | None = None) -> str | None:
    file_path = attachment.get("file_path")
    if file_path:
        return str(file_path)
    if not user_id:
        return None

    storage_key = str(attachment.get("storage_key") or "").strip()
    if not storage_key:
        return None
    if not _is_safe_chat_storage_key(storage_key):
        return None

    try:
        return storage.get_file_path(chat_attachment_scope_id(user_id), storage_key)
    except Exception as exc:  # pragma: no cover - storage backend defensive path
        log.warning("chat_attachment_path_resolution_failed", storage_key=storage_key, error=str(exc))
        return None


def _is_safe_chat_storage_key(storage_key: str) -> bool:
    if not storage_key or storage_key in {".", ".."}:
        return False
    if "/" in storage_key or "\\" in storage_key:
        return False
    return Path(storage_key).name == storage_key


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
            "feedback_reason": item.message.feedback_reason if item.message else None,
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
    flag_modified(kb_space, "extra_data")
    db.add(kb_space)
