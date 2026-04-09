from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.admin import AdminSetting


MODEL_CONFIG_KEYS = {
    "llm_provider": lambda: settings.LLM_PROVIDER,
    "llm_model": lambda: settings.LLM_MODEL,
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
