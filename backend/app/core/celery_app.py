from typing import Any

from app.core.config import settings

try:  # pragma: no cover - optional dependency handling
    from celery import Celery
except ImportError:  # pragma: no cover
    Celery = None


class DummyCeleryApp:
    """Fallback Celery-like object so imports do not fail in dev."""

    conf: dict[str, Any] = {}

    def task(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def autodiscover_tasks(self, *_args, **_kwargs):
        return []


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
    app.autodiscover_tasks(["app.workers.tasks"])
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
