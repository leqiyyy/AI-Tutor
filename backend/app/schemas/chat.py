from datetime import datetime
from typing import List, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class AttachedFile(BaseModel):
    id: str
    name: str
    size: int
    mime_type: str
    file_type: str


class KnowledgeSource(BaseModel):
    name: str
    page: Optional[int] = None
    type: Optional[str] = None
    score: Optional[float] = None
    chunk_id: Optional[str] = None


class ChatMessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    attachments: Optional[List[dict]] = None
    sources: Optional[List[dict]] = None
    suggestions: Optional[List[str]] = None
    confidence: Optional[float] = None
    feedback: Optional[str] = None
    needs_review: bool = False
    created_at: datetime
    model_config = {"from_attributes": True}


class ChatSessionOut(BaseModel):
    id: str
    class_id: str
    user_id: str
    title: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_message: Optional[str] = None
    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    class_id: str
    content: str
    session_id: Optional[str] = None
    attachments: Optional[List[dict]] = None


class ChatQueryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    course_id: Optional[str] = None
    class_id: Optional[str] = None
    session_id: Optional[str] = Field(default=None, validation_alias=AliasChoices("session_id", "conversation_id"))
    message: str = Field(validation_alias=AliasChoices("message", "content"))
    attachments: Optional[List[dict]] = None


class FeedbackRequest(BaseModel):
    feedback: Literal["like", "dislike"]
    reason: Optional[str] = None


class ReviewItemOut(BaseModel):
    id: str
    message_id: str
    class_id: str
    student_id: str
    student_name: Optional[str] = None
    trigger: str
    question_content: str
    ai_answer: str
    teacher_answer: Optional[str] = None
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


class ResolveReviewRequest(BaseModel):
    teacher_answer: str
    add_to_kb: bool = True
