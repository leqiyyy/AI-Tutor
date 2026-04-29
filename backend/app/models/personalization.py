from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text

from app.db.base import Base


def _uuid():
    return str(uuid.uuid4())


class StudentConceptMastery(Base):
    """Concept-level mastery snapshot derived from learning evidence."""

    __tablename__ = "student_concept_mastery"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    concept_id = Column(String(36), nullable=True)
    concept_name = Column(String(300), nullable=False)
    mastery_score = Column(Float, nullable=False, default=0.5)
    confidence = Column(Float, nullable=False, default=0.0)
    evidence_count = Column(Integer, nullable=False, default=0)
    last_event_at = Column(DateTime, nullable=True)
    source_breakdown = Column(JSON, nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class StudentLearningPreference(Base):
    """Student preference snapshot for personalization ranking."""

    __tablename__ = "student_learning_preferences"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=True)
    preferred_resource_types = Column(JSON, nullable=True)
    preferred_difficulty = Column(String(50), nullable=True)
    preferred_study_time = Column(String(50), nullable=True)
    interaction_summary = Column(JSON, nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class StudentRiskSignal(Base):
    """Risk signal generated from behavior, assessment, and AI-review evidence."""

    __tablename__ = "student_risk_signals"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    risk_type = Column(String(80), nullable=False)
    risk_level = Column(String(30), nullable=False, default="low")
    reason = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)
    status = Column(String(30), nullable=False, default="open")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class LearningConcept(Base):
    """Teaching-oriented projection of a RAG knowledge entity."""

    __tablename__ = "learning_concepts"

    id = Column(String(36), primary_key=True, default=_uuid)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    source_entity_id = Column(String(36), ForeignKey("knowledge_entities.id"), nullable=True)
    concept_name = Column(String(300), nullable=False)
    concept_type = Column(String(100), nullable=True)
    difficulty = Column(Float, nullable=False, default=0.5)
    importance = Column(Float, nullable=False, default=0.5)
    chapter = Column(String(200), nullable=True)
    confidence = Column(Float, nullable=False, default=0.5)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class LearningConceptRelation(Base):
    """Teaching relationship used for learning path generation."""

    __tablename__ = "learning_concept_relations"

    id = Column(String(36), primary_key=True, default=_uuid)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    source_concept_id = Column(String(36), ForeignKey("learning_concepts.id"), nullable=False)
    target_concept_id = Column(String(36), ForeignKey("learning_concepts.id"), nullable=False)
    relation_type = Column(String(80), nullable=False, default="related_to")
    weight = Column(Float, nullable=False, default=1.0)
    confidence = Column(Float, nullable=False, default=0.5)
    source_relation_id = Column(String(36), ForeignKey("knowledge_relations.id"), nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class LearningResourceLink(Base):
    """Link from teaching concepts to materials, tasks, flashcards, or review answers."""

    __tablename__ = "learning_resource_links"

    id = Column(String(36), primary_key=True, default=_uuid)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    concept_id = Column(String(36), ForeignKey("learning_concepts.id"), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(36), nullable=False)
    title = Column(String(300), nullable=True)
    relevance = Column(Float, nullable=False, default=0.5)
    difficulty = Column(Float, nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class LearningPath(Base):
    """Persisted generated learning path."""

    __tablename__ = "learning_paths"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    title = Column(String(300), nullable=False)
    status = Column(String(30), nullable=False, default="active")
    strategy = Column(String(80), nullable=False, default="topological_rules_v1")
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class LearningPathStep(Base):
    """One step in a generated learning path."""

    __tablename__ = "learning_path_steps"

    id = Column(String(36), primary_key=True, default=_uuid)
    path_id = Column(String(36), ForeignKey("learning_paths.id"), nullable=False)
    step_order = Column(Integer, nullable=False)
    concept_id = Column(String(36), ForeignKey("learning_concepts.id"), nullable=True)
    concept_name = Column(String(300), nullable=False)
    goal = Column(Text, nullable=True)
    recommended_resources = Column(JSON, nullable=True)
    estimated_minutes = Column(Integer, nullable=True)
    reason = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="pending")
    completed_at = Column(DateTime, nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class RecommendationEvent(Base):
    """Recommendation impression/click/completion/dismissal event."""

    __tablename__ = "recommendation_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=True)
    recommendation_type = Column(String(50), nullable=False)
    target_id = Column(String(36), nullable=False)
    event_type = Column(String(50), nullable=False)
    score = Column(Float, nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

