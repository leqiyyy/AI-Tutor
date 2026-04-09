from sqlalchemy import Column, DateTime, JSON, String
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
