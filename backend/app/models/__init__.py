# Import all models so SQLAlchemy registers them with Base.metadata
from app.models.user import User
from app.models.course import Course, Class, ClassMember, Material, Task, Submission, Discussion
from app.models.chat import ChatCitation, ChatSession, ChatMessage, ReviewItem, ReviewSyncRecord
from app.models.knowledge import FileParseTask, KBSpace, KnowledgeEntity, KnowledgeRelation, Flashcard, FlashcardRecord
from app.models.notification import Notification, VerifyCode
from app.models.analytics import LearningRecord, QuestionAnalytics, StudentProfile, StudyMistake, RAGQueryEvent
from app.models.personalization import (
    LearningConcept,
    LearningConceptRelation,
    LearningPath,
    LearningPathStep,
    LearningResourceLink,
    RecommendationEvent,
    StudentConceptMastery,
    StudentLearningPreference,
    StudentRiskSignal,
)
from app.models.admin import AdminSetting

__all__ = [
    "User",
    "Course", "Class", "ClassMember", "Material", "Task", "Submission", "Discussion",
    "ChatSession", "ChatMessage", "ReviewItem", "ChatCitation", "ReviewSyncRecord",
    "KnowledgeEntity", "KnowledgeRelation", "Flashcard", "FlashcardRecord", "KBSpace", "FileParseTask",
    "Notification", "VerifyCode",
    "LearningRecord", "QuestionAnalytics", "StudentProfile", "StudyMistake", "RAGQueryEvent",
    "StudentConceptMastery", "StudentLearningPreference", "StudentRiskSignal",
    "LearningConcept", "LearningConceptRelation", "LearningResourceLink",
    "LearningPath", "LearningPathStep", "RecommendationEvent",
    "AdminSetting",
]
