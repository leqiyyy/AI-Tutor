from pathlib import Path
from urllib.parse import urlparse
from typing import List

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "AI Tutor Backend"
    APP_VERSION: str = "0.1.0"
    ENV: str = Field(
        default="development",
        validation_alias=AliasChoices("ENV", "APP_ENV"),
    )
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    AUTO_CREATE_TABLES: bool = True

    SECRET_KEY: str = "dev-secret-key-change-in-production-32ch"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080

    DATABASE_URL: str = "sqlite:///./ai_tutor.db"
    DB_POOL_PRE_PING: bool = True
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_AVAILABLE: bool = False

    STORAGE_BACKEND: str = "local"  # local | minio
    LOCAL_STORAGE_PATH: str = "./uploads"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "ai-tutor"
    MINIO_SECURE: bool = False

    CORS_ORIGINS_RAW: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        validation_alias=AliasChoices("CORS_ORIGINS_STR", "CORS_ORIGINS"),
    )

    LLM_PROVIDER: str = "mock"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = ""
    LLM_MODEL: str = "claude-opus-4-6"
    LLM_API_KEY: str = ""
    LLM_API_BASE: str = ""
    LLM_WIRE_API: str = "responses"
    EXTRACT_MODEL: str = ""
    EXTRACT_API_KEY: str = ""
    EXTRACT_API_BASE: str = ""
    EXTRACT_WIRE_API: str = "chat_completions"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_API_BASE: str = ""
    VLM_MODEL: str = ""
    VLM_API_KEY: str = ""
    VLM_API_BASE: str = ""
    VLM_WIRE_API: str = "chat_completions"
    RAG_ENGINE: str = "mock"
    LIBREOFFICE_PATH: str = ""
    RAGANYTHING_WORKING_DIR: str = "./rag_storage"
    RAGANYTHING_OUTPUT_DIR: str = "./rag_output"
    RAGANYTHING_PARSER: str = "mineru"
    RAGANYTHING_PARSE_METHOD: str = "auto"
    RAGANYTHING_QUERY_MODE: str = "mix"
    RAGANYTHING_MAX_CONCURRENT_FILES: int = 1

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@ai-tutor.com"
    EMAIL_DEV_MODE: bool = True

    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    HEALTHCHECK_TIMEOUT_SECONDS: float = 1.5

    @field_validator(
        "DEBUG",
        "AUTO_CREATE_TABLES",
        "REDIS_AVAILABLE",
        "MINIO_SECURE",
        "EMAIL_DEV_MODE",
        mode="before",
    )
    @classmethod
    def parse_bools(cls, value):
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes", "on"}
        return value

    @property
    def CORS_ORIGINS(self) -> List[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS_RAW.split(",")
            if origin.strip()
        ]

    @property
    def DATABASE_IS_SQLITE(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def DATABASE_URL_EFFECTIVE(self) -> str:
        if self.DATABASE_URL.startswith("sqlite:///./"):
            relative = self.DATABASE_URL.removeprefix("sqlite:///./")
            return f"sqlite:///{(BASE_DIR / relative).resolve().as_posix()}"
        return self.DATABASE_URL

    @property
    def EFFECTIVE_LLM_API_KEY(self) -> str:
        return self.LLM_API_KEY or self.OPENAI_API_KEY

    @property
    def EFFECTIVE_LLM_API_BASE(self) -> str:
        return self._normalize_base(self.LLM_API_BASE or self.OPENAI_API_BASE)

    @property
    def EFFECTIVE_EMBEDDING_API_KEY(self) -> str:
        return self.EMBEDDING_API_KEY or self.OPENAI_API_KEY

    @property
    def EFFECTIVE_EMBEDDING_API_BASE(self) -> str:
        return self._normalize_openai_base(
            self.EMBEDDING_API_BASE or self.OPENAI_API_BASE or self.EFFECTIVE_LLM_API_BASE
        )

    @property
    def EFFECTIVE_VLM_API_KEY(self) -> str:
        return self.VLM_API_KEY or self.EFFECTIVE_LLM_API_KEY

    @property
    def EFFECTIVE_VLM_API_BASE(self) -> str:
        return self._normalize_openai_base(self.VLM_API_BASE or self.EFFECTIVE_LLM_API_BASE)

    @property
    def EFFECTIVE_VLM_MODEL(self) -> str:
        return self.VLM_MODEL or self.LLM_MODEL

    @property
    def EFFECTIVE_EXTRACT_API_KEY(self) -> str:
        return self.EXTRACT_API_KEY or self.EFFECTIVE_LLM_API_KEY

    @property
    def EFFECTIVE_EXTRACT_API_BASE(self) -> str:
        return self._normalize_openai_base(self.EXTRACT_API_BASE or self.EFFECTIVE_LLM_API_BASE)

    @property
    def EFFECTIVE_EXTRACT_MODEL(self) -> str:
        return self.EXTRACT_MODEL or self.LLM_MODEL

    @property
    def LOCAL_STORAGE_ROOT(self) -> Path:
        return (BASE_DIR / self.LOCAL_STORAGE_PATH).resolve() if self.LOCAL_STORAGE_PATH.startswith(".") else Path(self.LOCAL_STORAGE_PATH)

    def _normalize_base(self, base: str) -> str:
        if not base:
            return ""
        return base.rstrip("/")

    def _normalize_openai_base(self, base: str) -> str:
        normalized = self._normalize_base(base)
        if not normalized:
            return normalized
        parsed = urlparse(normalized)
        if parsed.scheme and parsed.netloc and parsed.path in {"", "/"}:
            return normalized + "/v1"
        return normalized


settings = Settings()
