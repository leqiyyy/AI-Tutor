from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Integer, Float, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.db.base import Base


def _uuid():
    return str(uuid.uuid4())


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(300), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    cls = relationship("Class", back_populates="chat_sessions")
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(Enum("user", "ai", "system", name="message_role"), nullable=False)
    content = Column(Text, nullable=False)
    # Attachments stored as JSON list of {id, name, size, mimeType, fileType}
    attachments = Column(JSON, nullable=True)
    # Knowledge sources: [{name, page, type, score}]
    sources = Column(JSON, nullable=True)
    # Suggested follow-up questions
    suggestions = Column(JSON, nullable=True)
    # Confidence score 0-1
    confidence = Column(Float, nullable=True)
    # User feedback
    feedback = Column(Enum("like", "dislike", name="message_feedback"), nullable=True)
    feedback_reason = Column(Text, nullable=True)
    # Whether this was escalated to review
    needs_review = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("ChatSession", back_populates="messages")
    review = relationship("ReviewItem", back_populates="message", uselist=False)
    citations = relationship("ChatCitation", back_populates="message", order_by="ChatCitation.created_at")


class ReviewItem(Base):
    """Low-confidence or disliked AI answers awaiting teacher review."""
    __tablename__ = "review_items"

    id = Column(String(36), primary_key=True, default=_uuid)
    message_id = Column(String(36), ForeignKey("chat_messages.id"), nullable=False)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    student_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    trigger = Column(Enum("low_confidence", "dislike", "manual", name="review_trigger"), nullable=False)
    question_content = Column(Text, nullable=False)
    ai_answer = Column(Text, nullable=False)
    teacher_answer = Column(Text, nullable=True)
    status = Column(
        Enum("pending", "resolved", "dismissed", name="review_status"),
        default="pending"
    )
    reviewed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    message = relationship("ChatMessage", back_populates="review")
    student = relationship("User", foreign_keys=[student_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    sync_records = relationship("ReviewSyncRecord", back_populates="review", order_by="ReviewSyncRecord.created_at")


class ChatCitation(Base):
    __tablename__ = "chat_citations"

    id = Column(String(36), primary_key=True, default=_uuid)
    message_id = Column(String(36), ForeignKey("chat_messages.id"), nullable=False)
    source_name = Column(String(300), nullable=False)
    source_type = Column(String(50), nullable=True)
    page = Column(Integer, nullable=True)
    score = Column(Float, nullable=True)
    chunk_id = Column(String(100), nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    message = relationship("ChatMessage", back_populates="citations")


class ReviewSyncRecord(Base):
    __tablename__ = "review_sync_records"

    id = Column(String(36), primary_key=True, default=_uuid)
    review_id = Column(String(36), ForeignKey("review_items.id"), nullable=False)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    question_content = Column(Text, nullable=False)
    final_answer = Column(Text, nullable=False)
    sync_status = Column(
        Enum("pending", "synced", "failed", name="review_sync_status"),
        default="pending",
    )
    sync_note = Column(Text, nullable=True)
    synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    review = relationship("ReviewItem", back_populates="sync_records")
