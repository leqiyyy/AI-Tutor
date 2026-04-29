from app.core.celery_app import get_celery_status
from app.core.config import settings
from app.core.database import check_database_connection, check_database_schema
from app.core.redis import ping_redis
from app.integrations.storage import get_storage_backend


def get_liveness_payload() -> dict:
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENV,
    }


def get_readiness_payload() -> dict:
    db_ok, db_detail = check_database_connection()
    schema_ok, schema_detail = check_database_schema()
    redis_ok, redis_detail = ping_redis()
    storage_status = get_storage_backend().healthcheck()

    dependencies = {
        "database": {"ok": db_ok and schema_ok, "detail": db_detail, "schema": schema_detail},
        "redis": {
            "ok": redis_ok,
            "detail": redis_detail,
            "enabled": settings.REDIS_AVAILABLE,
        },
        "storage": storage_status,
        "celery": get_celery_status(),
    }

    ready = db_ok and schema_ok and storage_status.get("ok", False)
    if settings.REDIS_AVAILABLE:
        ready = ready and redis_ok

    return {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "dependencies": dependencies,
    }


def get_system_health_payload() -> dict:
    return {
        **get_liveness_payload(),
        **get_readiness_payload(),
    }
