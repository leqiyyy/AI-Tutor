from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class CreateCourseRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    cover_color: Optional[str] = Field(default="#3b82f6", validation_alias=AliasChoices("cover_color", "coverColor"))
    graph_schema: Optional[dict[str, Any]] = Field(default=None, validation_alias=AliasChoices("graph_schema", "graphSchema"))


class CreateClassRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    course_id: Optional[str] = Field(default=None, validation_alias=AliasChoices("course_id", "courseId"))
    code: Optional[str] = None
    semester: Optional[str] = None
    description: Optional[str] = None
    cover_color: Optional[str] = Field(default="#3b82f6", validation_alias=AliasChoices("cover_color", "coverColor"))
    graph_schema: Optional[dict[str, Any]] = Field(default=None, validation_alias=AliasChoices("graph_schema", "graphSchema"))


class CourseOut(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    cover_color: str
    graph_schema: Optional[dict[str, Any]] = None
    created_by: str
    created_at: datetime
    model_config = {"from_attributes": True}


class CourseCardOut(BaseModel):
    id: str
    class_id: Optional[str] = None
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    cover_color: Optional[str] = None
    semester: Optional[str] = None
    teacher_id: Optional[str] = None
    teacher_name: Optional[str] = None
    student_count: Optional[int] = None
    invite_code: Optional[str] = None
    unread: int = 0
    graph_schema: Optional[dict[str, Any]] = None


class ClassOut(BaseModel):
    id: str
    course_id: str
    teacher_id: str
    name: str
    semester: Optional[str] = None
    invite_code: str
    announcement: Optional[str] = None
    is_active: bool
    created_at: datetime
    student_count: Optional[int] = None
    teacher_name: Optional[str] = None
    course_name: Optional[str] = None
    graph_schema: Optional[dict[str, Any]] = None
    model_config = {"from_attributes": True}


class UpdateClassRequest(BaseModel):
    name: Optional[str] = None
    semester: Optional[str] = None
    announcement: Optional[str] = None


class JoinClassRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    invite_code: str = Field(validation_alias=AliasChoices("invite_code", "inviteCode"))


class MaterialOut(BaseModel):
    id: str
    class_id: str
    title: str
    file_name: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    file_type: Optional[str] = None
    kb_status: str
    description: Optional[str] = None
    created_at: datetime
    uploader_name: Optional[str] = None
    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: str
    class_id: str
    title: str
    description: Optional[str] = None
    task_type: str
    due_date: Optional[datetime] = None
    max_score: int
    is_published: bool
    created_at: datetime
    submission_count: Optional[int] = None
    model_config = {"from_attributes": True}


class CreateTaskRequest(BaseModel):
    title: str
    description: Optional[str] = None
    task_type: str = "homework"
    due_date: Optional[datetime] = None
    max_score: int = 100
    is_published: bool = False


class CreateTaskGlobalRequest(CreateTaskRequest):
    class_id: str


class DiscussionOut(BaseModel):
    id: str
    class_id: str
    author_id: str
    author_name: Optional[str] = None
    title: Optional[str] = None
    content: str
    parent_id: Optional[str] = None
    likes: int
    is_pinned: bool
    created_at: datetime
    reply_count: Optional[int] = None
    model_config = {"from_attributes": True}


class CreateDiscussionRequest(BaseModel):
    title: Optional[str] = None
    content: str
    parent_id: Optional[str] = None
