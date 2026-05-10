from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Integer, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.db.base import Base


def _uuid():
    return str(uuid.uuid4())


class Course(Base):
    __tablename__ = "courses"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False)
    code = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    cover_color = Column(String(20), default="#3b82f6")
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    classes = relationship("Class", back_populates="course")
    creator = relationship("User", foreign_keys=[created_by])


class Class(Base):
    __tablename__ = "classes"

    id = Column(String(36), primary_key=True, default=_uuid)
    course_id = Column(String(36), ForeignKey("courses.id"), nullable=False)
    teacher_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    name = Column(String(200), nullable=False)
    semester = Column(String(50), nullable=True)
    invite_code = Column(String(20), unique=True, nullable=False)
    announcement = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    course = relationship("Course", back_populates="classes")
    teacher = relationship("User", back_populates="taught_classes", foreign_keys=[teacher_id])
    members = relationship("ClassMember", back_populates="cls")
    materials = relationship("Material", back_populates="cls")
    tasks = relationship("Task", back_populates="cls")
    discussions = relationship("Discussion", back_populates="cls")
    chat_sessions = relationship("ChatSession", back_populates="cls")


class ClassMember(Base):
    __tablename__ = "class_members"

    id = Column(String(36), primary_key=True, default=_uuid)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    role = Column(Enum("student", "teacher", "assistant", name="member_role"), default="student")
    group_no = Column(Integer, nullable=False, default=1)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    cls = relationship("Class", back_populates="members")
    user = relationship("User", back_populates="class_memberships")


class Material(Base):
    __tablename__ = "materials"

    id = Column(String(36), primary_key=True, default=_uuid)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(300), nullable=False)
    file_name = Column(String(300), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    file_type = Column(String(20), nullable=True)  # pdf, docx, ppt, video, etc.
    kb_status = Column(
        Enum("pending", "processing", "indexed", "failed", name="kb_status"),
        default="pending"
    )
    kb_error = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    cls = relationship("Class", back_populates="materials")
    uploader = relationship("User", foreign_keys=[uploaded_by])


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=_uuid)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(Enum("homework", "exam", "quiz", "project", name="task_type"), default="homework")
    due_date = Column(DateTime, nullable=True)
    max_score = Column(Integer, default=100)
    is_published = Column(Boolean, default=False)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    cls = relationship("Class", back_populates="tasks")
    creator = relationship("User", foreign_keys=[created_by])
    submissions = relationship("Submission", back_populates="task")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(String(36), primary_key=True, default=_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    student_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    score = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)
    status = Column(
        Enum("submitted", "graded", "late", "missing", name="submission_status"),
        default="submitted"
    )
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    graded_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="submissions")
    student = relationship("User", foreign_keys=[student_id])


class Discussion(Base):
    __tablename__ = "discussions"

    id = Column(String(36), primary_key=True, default=_uuid)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False)
    author_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(300), nullable=True)
    content = Column(Text, nullable=False)
    parent_id = Column(String(36), ForeignKey("discussions.id"), nullable=True)
    likes = Column(Integer, default=0)
    is_pinned = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    cls = relationship("Class", back_populates="discussions")
    author = relationship("User", foreign_keys=[author_id])
    replies = relationship("Discussion", foreign_keys=[parent_id])
