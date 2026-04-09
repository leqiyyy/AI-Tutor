from app.core.celery_app import celery_app


@celery_app.task(name="system.ping")
def ping() -> dict:
    return {"status": "ok"}
