"""Conversation-context helpers for multi-turn RAG.

This module is intentionally independent from chat_service so it can be wired
into the main AI assistant chain with a small, low-conflict hook later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession


FOLLOW_UP_PATTERNS = (
    r"^(那|那么|这个|那个|它|他们|它们|上述|前面|刚才|第二点|第一点|第三点)",
    r"(继续|展开|详细|再说|再解释|举例|对比|区别|为什么|怎么做)",
)

NEW_TOPIC_PATTERNS = (
    r"^(换个|另一个|新问题| unrelated |new topic)",
    r"(不讨论|先不说|另外问)",
)


@dataclass(frozen=True)
class ConversationContext:
    original_question: str
    standalone_question: str
    context_intent: str
    recent_turns: list[dict[str, str]]
    session_summary: str
    summary_used: bool
    history_turn_count: int
    context_version: str = "context_rules_v1"

    def to_rag_meta(self) -> dict[str, Any]:
        return {
            "original_question": self.original_question,
            "standalone_question": self.standalone_question,
            "context_intent": self.context_intent,
            "history_turn_count": self.history_turn_count,
            "summary_used": self.summary_used,
            "conversation_context_version": self.context_version,
        }


def build_conversation_context(
    db: Session,
    session: ChatSession,
    current_question: str,
    *,
    max_recent_turns: int = 10,
) -> ConversationContext:
    """Build a retrieval-ready multi-turn context without mutating chat state."""

    messages = _load_recent_messages(db, session.id, max_recent_turns=max_recent_turns)
    recent_turns = [{"role": item.role, "content": item.content} for item in messages]
    summary = str(getattr(session, "summary", "") or "")
    intent = classify_context_intent(recent_turns, current_question)
    standalone_question = rewrite_standalone_question(
        history=recent_turns,
        summary=summary,
        question=current_question,
        intent=intent,
    )
    return ConversationContext(
        original_question=current_question,
        standalone_question=standalone_question,
        context_intent=intent,
        recent_turns=recent_turns,
        session_summary=summary,
        summary_used=bool(summary.strip()),
        history_turn_count=len(recent_turns),
    )


def classify_context_intent(history: Iterable[dict[str, str]], question: str) -> str:
    """Classify the latest turn using conservative lexical rules."""

    text = _normalize(question)
    if not text:
        return "unknown"
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in NEW_TOPIC_PATTERNS):
        return "new_topic"
    if not list(history):
        return "new_topic"
    if "?" in text or "？" in text:
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in FOLLOW_UP_PATTERNS):
            return "follow_up"
        return "new_topic"
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in FOLLOW_UP_PATTERNS):
        return "follow_up"
    return "clarification" if len(text) <= 24 else "new_topic"


def rewrite_standalone_question(
    *,
    history: Iterable[dict[str, str]],
    summary: str,
    question: str,
    intent: str | None = None,
) -> str:
    """Create a retrieval query that is robust for short follow-up questions.

    This first version is deterministic and side-effect free. A later hook can
    replace it with an LLM-based CQR provider without changing chat_service.
    """

    clean_question = _normalize(question)
    if not clean_question:
        return question

    history_list = list(history)
    effective_intent = intent or classify_context_intent(history_list, clean_question)
    if effective_intent == "new_topic" or not history_list:
        return clean_question

    anchor = _last_user_question(history_list)
    if not anchor:
        anchor = _summary_anchor(summary)
    if not anchor:
        return clean_question

    if _contains_anchor_terms(clean_question, anchor):
        return clean_question

    return f"{anchor}。追问：{clean_question}"


def build_session_summary(
    messages: Iterable[dict[str, str]],
    *,
    max_chars: int = 1200,
) -> str:
    """Build a compact deterministic session summary for early implementation."""

    lines: list[str] = []
    for message in messages:
        role = str(message.get("role") or "unknown")
        content = _normalize(str(message.get("content") or ""))
        if not content:
            continue
        lines.append(f"{role}: {content}")
    summary = "\n".join(lines)
    if len(summary) <= max_chars:
        return summary
    return summary[-max_chars:]


def update_session_summary(
    db: Session,
    session: ChatSession,
    messages: Iterable[dict[str, str]],
    *,
    max_chars: int = 1200,
) -> str:
    """Persist summary only when ChatSession has summary fields available."""

    summary = build_session_summary(messages, max_chars=max_chars)
    if hasattr(session, "summary"):
        setattr(session, "summary", summary)
    if hasattr(session, "summary_updated_at"):
        setattr(session, "summary_updated_at", datetime.now(timezone.utc))
    if hasattr(session, "context_version"):
        setattr(session, "context_version", "context_rules_v1")
    db.add(session)
    db.flush()
    return summary


def _load_recent_messages(
    db: Session,
    session_id: str,
    *,
    max_recent_turns: int,
) -> list[ChatMessage]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(max(1, int(max_recent_turns)))
        .all()
    )
    return list(reversed(rows))


def _last_user_question(history: list[dict[str, str]]) -> str:
    for message in reversed(history):
        if message.get("role") == "user":
            content = _normalize(message.get("content") or "")
            if content:
                return content
    return ""


def _summary_anchor(summary: str) -> str:
    text = _normalize(summary)
    if not text:
        return ""
    parts = re.split(r"[。！？\n.!?]", text)
    for part in reversed(parts):
        clean = _normalize(part)
        if len(clean) >= 8:
            return clean[-160:]
    return text[-160:]


def _contains_anchor_terms(question: str, anchor: str) -> bool:
    question_terms = set(_terms(question))
    anchor_terms = set(_terms(anchor))
    if not question_terms or not anchor_terms:
        return False
    return len(question_terms.intersection(anchor_terms)) >= 2


def _terms(text: str) -> list[str]:
    latin = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    cjk = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
    return [*latin, *cjk]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()

