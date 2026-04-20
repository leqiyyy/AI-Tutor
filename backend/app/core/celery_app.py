from typing import Any
from uuid import uuid4

from app.core.config import settings

try:  # pragma: no cover - optional dependency handling
    from celery import Celery
except ImportError:  # pragma: no cover
    Celery = None


class DummyCeleryApp:
    """Fallback Celery-like object so imports do not fail in dev."""

    conf: dict[str, Any] = {}
    enabled: bool = False

    def task(self, *args, **kwargs):
        def decorator(func):
            task_name = kwargs.get("name", getattr(func, "__name__", "dummy_task"))

            def _enqueue(*_args, **_kwargs):
                _ = (_args, _kwargs, task_name)
                return DummyAsyncResult(uuid4().hex)

            func.delay = _enqueue
            func.apply_async = lambda args=None, kwargs=None, **opts: _enqueue(*(args or ()), **(kwargs or {}))
            return func

        return decorator

    def autodiscover_tasks(self, *_args, **_kwargs):
        return []


class DummyAsyncResult:
    def __init__(self, task_id: str):
        self.id = task_id
        self.status = "PENDING"

    def get(self, timeout: float | None = None):  # pragma: no cover - convenience for parity
        _ = timeout
        return None


def _create_celery_app():
    if Celery is None:
        return DummyCeleryApp()

    app = Celery("ai_tutor")
    app.conf.update(
        broker_url=settings.CELERY_BROKER_URL,
        result_backend=settings.CELERY_RESULT_BACKEND,
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
    )
    app.enabled = True
    app.autodiscover_tasks(["app.workers"])
    return app


celery_app = _create_celery_app()


def get_celery_status() -> dict[str, Any]:
    if Celery is None:
        return {
            "enabled": False,
            "status": "not_installed",
            "broker_url": settings.CELERY_BROKER_URL,
        }

    return {
        "enabled": True,
        "status": "configured",
        "broker_url": settings.CELERY_BROKER_URL,
        "result_backend": settings.CELERY_RESULT_BACKEND,
    }
