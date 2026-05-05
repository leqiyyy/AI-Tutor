from sqlalchemy import Column, DateTime, JSON, String, Text
from datetime import datetime, timezone
import uuid

from app.db.base import Base


def _uuid():
    return str(uuid.uuid4())


class AdminSetting(Base):
    __tablename__ = "admin_settings"

    id = Column(String(36), primary_key=True, default=_uuid)
    section = Column(String(100), nullable=False, index=True)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(JSON, nullable=True)
    description = Column(String(300), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AdminAuditEvent(Base):
    __tablename__ = "admin_audit_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    event_type = Column(String(100), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="success", index=True)
    actor_id = Column(String(36), nullable=True, index=True)
    actor_role = Column(String(30), nullable=True, index=True)
    actor_name = Column(String(100), nullable=True)
    target_type = Column(String(50), nullable=True, index=True)
    target_id = Column(String(100), nullable=True, index=True)
    course_id = Column(String(36), nullable=True, index=True)
    class_id = Column(String(36), nullable=True, index=True)
    material_id = Column(String(36), nullable=True, index=True)
    summary = Column(Text, nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
