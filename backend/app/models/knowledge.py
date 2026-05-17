from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Integer, Float, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.db.base import Base


def _uuid():
    return str(uuid.uuid4())


class KnowledgeEntity(Base):
    """Knowledge graph entity extracted from course materials."""
    __tablename__ = "knowledge_entities"

    id = Column(String(36), primary_key=True, default=_uuid)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    name = Column(String(300), nullable=False)
    canonical_name = Column(String(300), nullable=True)
    aliases = Column(JSON, nullable=True)
    entity_type = Column(String(100), nullable=True)  # concept, person, formula, etc.
    description = Column(Text, nullable=True)
    source_material_id = Column(String(36), ForeignKey("materials.id"), nullable=True)
    confidence = Column(Float, default=0.6)
    source_span = Column(JSON, nullable=True)
    provenance = Column(JSON, nullable=True)
    status = Column(
        Enum("pending", "approved", "rejected", name="entity_status"),
        default="pending"
    )
    reviewed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class KnowledgeRelation(Base):
    """Relationships between knowledge entities."""
    __tablename__ = "knowledge_relations"

    id = Column(String(36), primary_key=True, default=_uuid)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    source_id = Column(String(36), ForeignKey("knowledge_entities.id"), nullable=False)
    target_id = Column(String(36), ForeignKey("knowledge_entities.id"), nullable=False)
    relation_type = Column(String(100), nullable=True)  # prerequisite, related, etc.
    weight = Column(Float, default=1.0)
    confidence = Column(Float, default=0.55)
    source_span = Column(JSON, nullable=True)
    provenance = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(String(36), primary_key=True, default=_uuid)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    source_material_id = Column(String(36), ForeignKey("materials.id"), nullable=True)
    tags = Column(JSON, nullable=True)  # list of strings
    # Spaced repetition fields
    ease_factor = Column(Float, default=2.5)
    interval_days = Column(Integer, default=1)
    next_review_at = Column(DateTime, nullable=True)
    review_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", foreign_keys=[user_id])
    review_records = relationship("FlashcardRecord", back_populates="flashcard", order_by="FlashcardRecord.reviewed_at")


class FlashcardRecord(Base):
    __tablename__ = "flashcard_records"

    id = Column(String(36), primary_key=True, default=_uuid)
    flashcard_id = Column(String(36), ForeignKey("flashcards.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5 spaced repetition quality
    response = Column(String(50), nullable=True)  # again | hard | good | easy
    interval_before = Column(Integer, nullable=True)
    interval_after = Column(Integer, nullable=True)
    next_review_at = Column(DateTime, nullable=True)
    extra_data = Column(JSON, nullable=True)
    reviewed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    flashcard = relationship("Flashcard", back_populates="review_records")
    user = relationship("User", foreign_keys=[user_id])


class KBSpace(Base):
    __tablename__ = "kb_spaces"

    id = Column(String(36), primary_key=True, default=_uuid)
    course_id = Column(String(36), ForeignKey("courses.id"), nullable=False)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=True)
    status = Column(
        Enum("empty", "building", "ready", "failed", name="kb_space_status"),
        default="empty",
    )
    document_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    last_built_at = Column(DateTime, nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class FileParseTask(Base):
    __tablename__ = "file_parse_tasks"

    id = Column(String(36), primary_key=True, default=_uuid)
    kb_space_id = Column(String(36), ForeignKey("kb_spaces.id"), nullable=False)
    course_id = Column(String(36), ForeignKey("courses.id"), nullable=False)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=True)
    material_id = Column(String(36), ForeignKey("materials.id"), nullable=False)
    status = Column(
        Enum("pending", "processing", "completed", "failed", name="file_parse_task_status"),
        default="pending",
    )
    parser_name = Column(String(100), nullable=True)
    summary = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
    chunks = Column(JSON, nullable=True)
    extra_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
