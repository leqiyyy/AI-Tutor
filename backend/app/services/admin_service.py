from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.admin import AdminSetting


MODEL_CONFIG_KEYS = {
    "llm_provider": lambda: settings.LLM_PROVIDER,
    "llm_model": lambda: settings.LLM_MODEL,
    "llm_backend": lambda: settings.LLM_BACKEND,
    "llm_local_api_base": lambda: settings.LLM_LOCAL_API_BASE,
    "embedding_model": lambda: settings.EMBEDDING_MODEL,
    "embedding_backend": lambda: settings.EMBEDDING_BACKEND,
    "embedding_local_api_base": lambda: settings.EMBEDDING_LOCAL_API_BASE,
    "vlm_model": lambda: settings.VLM_MODEL,
    "vlm_backend": lambda: settings.VLM_BACKEND,
    "vlm_local_api_base": lambda: settings.VLM_LOCAL_API_BASE,
    "reranker_provider": lambda: settings.RERANKER_PROVIDER,
    "reranker_model": lambda: settings.RERANKER_MODEL,
    "reranker_local_model": lambda: settings.RERANKER_LOCAL_MODEL,
    "rag_engine": lambda: settings.RAG_ENGINE,
    "storage_backend": lambda: settings.STORAGE_BACKEND,
    "email_dev_mode": lambda: settings.EMAIL_DEV_MODE,
}


def get_model_config(db: Session) -> dict:
    stored = {
        setting.key: setting.value
        for setting in db.query(AdminSetting).filter(AdminSetting.section == "model_config").all()
    }
    return {
        key: stored.get(key, getter())
        for key, getter in MODEL_CONFIG_KEYS.items()
    }


def update_model_config(db: Session, payload: dict) -> dict:
    current = get_model_config(db)
    updates = {key: value for key, value in payload.items() if value is not None}
    current.update(updates)

    for key, value in updates.items():
        setting = db.query(AdminSetting).filter(AdminSetting.key == key).first()
        if not setting:
            setting = AdminSetting(
                section="model_config",
                key=key,
                value=value,
                description=f"Persisted model config value for {key}",
            )
            db.add(setting)
        else:
            setting.value = value

    db.commit()
    return current
