"""Celery task modules."""

from app.workers.tasks.kb_index import index_parse_task  # noqa: F401
from app.workers.tasks.system import ping  # noqa: F401

__all__ = ["index_parse_task", "ping"]
