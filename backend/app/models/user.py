from sqlalchemy import Column, String, Boolean, DateTime, Text, Enum, Integer
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.db.base import Base


def _uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    real_name = Column(String(100), nullable=False)
    role = Column(Enum("student", "teacher", "admin", name="user_role"), nullable=False)
    is_active = Column(Boolean, default=True)
    avatar_url = Column(String(500), nullable=True)
    failed_login_count = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)

    # Common profile fields
    phone = Column(String(20), nullable=True)
    school = Column(String(200), nullable=True)
    bio = Column(Text, nullable=True)

    # Student-specific
    student_id = Column(String(50), unique=True, nullable=True)  # 学号
    college = Column(String(200), nullable=True)
    major = Column(String(200), nullable=True)
    grade = Column(String(50), nullable=True)
    class_no = Column(String(50), nullable=True)

    # Teacher-specific
    teacher_id = Column(String(50), unique=True, nullable=True)  # 工号
    department = Column(String(200), nullable=True)
    title = Column(String(100), nullable=True)  # 职称

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    taught_classes = relationship("Class", back_populates="teacher", foreign_keys="Class.teacher_id")
    class_memberships = relationship("ClassMember", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
