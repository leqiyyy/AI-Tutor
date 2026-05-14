from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer, Float, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.db.base import Base


def _uuid():
    return str(uuid.uuid4())


class LearningRecord(Base):
    """Tracks student learning activity."""
    __tablename__ = "learning_records"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    activity_type = Column(String(50), nullable=False)  # view_material, submit_task, ask_question, etc.
    ref_id = Column(String(36), nullable=True)  # FK to material/task/message
    extra_data = Column(JSON, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class QuestionAnalytics(Base):
    """Aggregated question frequency per topic."""
    __tablename__ = "question_analytics"

    id = Column(String(36), primary_key=True, default=_uuid)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    topic = Column(String(300), nullable=False)
    question_count = Column(Integer, default=1)
    last_asked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class StudentProfile(Base):
    """Student learning profile snapshot for analytics and personalization."""
    __tablename__ = "student_profiles"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    preferred_courses = Column(JSON, nullable=True)
    strong_topics = Column(JSON, nullable=True)
    weak_topics = Column(JSON, nullable=True)
    total_questions = Column(Integer, default=0)
    dislike_count = Column(Integer, default=0)
    task_completion_rate = Column(Float, default=0.0)
    activity_score = Column(Float, default=0.0)
    last_active_at = Column(DateTime, nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class StudyMistake(Base):
    """Student mistake-book record."""
    __tablename__ = "study_mistakes"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    chapter = Column(String(200), nullable=True)
    question = Column(Text, nullable=False)
    my_answer = Column(Text, nullable=True)
    correct_answer = Column(Text, nullable=True)
    analysis = Column(Text, nullable=True)
    wrong_count = Column(Integer, default=1)
    mastered = Column(Integer, default=0)
    extra_data = Column(JSON, nullable=True)
    last_practice_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class RAGQueryEvent(Base):
    """Per-query observability record for the RAG pipeline."""
    __tablename__ = "rag_query_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    role = Column(String(20), nullable=True)
    engine = Column(String(50), nullable=False, default="unknown")
    query_mode = Column(String(30), nullable=True)
    query_method = Column(String(50), nullable=True)
    used_multimodal = Column(Integer, nullable=False, default=0)
    used_fallback = Column(Integer, nullable=False, default=0)
    fallback_reason = Column(String(80), nullable=True)
    success = Column(Integer, nullable=False, default=1)
    latency_ms = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    source_count = Column(Integer, nullable=False, default=0)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
