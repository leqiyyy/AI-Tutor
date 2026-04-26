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
    LLM_BACKEND: str = "auto"  # auto | api | local | mock
    LLM_LOCAL_API_BASE: str = ""
    EXTRACT_MODEL: str = ""
    EXTRACT_API_KEY: str = ""
    EXTRACT_API_BASE: str = ""
    EXTRACT_WIRE_API: str = "chat_completions"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536
    EMBEDDING_BACKEND: str = "auto"  # auto | api | local | mock
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_API_BASE: str = ""
    EMBEDDING_LOCAL_API_BASE: str = ""
    VLM_MODEL: str = ""
    VLM_BACKEND: str = "auto"  # auto | api | local | mock
    VLM_API_KEY: str = ""
    VLM_API_BASE: str = ""
    VLM_LOCAL_API_BASE: str = ""
    VLM_WIRE_API: str = "chat_completions"
    RAG_ENGINE: str = "raganything"
    RAGANYTHING_STRICT_MODE: bool = True
    RAGANYTHING_METADATA_FALLBACK_ENABLED: bool = False
    RAGANYTHING_REQUIRE_OFFICIAL_METADATA: bool = True
    LIBREOFFICE_PATH: str = ""
    RAGANYTHING_WORKING_DIR: str = "./rag_storage"
    RAGANYTHING_OUTPUT_DIR: str = "./rag_output"
    RAGANYTHING_PARSER: str = "mineru"
    RAGANYTHING_PARSE_METHOD: str = "auto"
    RAGANYTHING_QUERY_MODE: str = "mix"
    RAGANYTHING_MAX_CONCURRENT_FILES: int = 1
    RAGANYTHING_DEFAULT_LLM_TIMEOUT_SECONDS: int = 180
    RAG_EDUCATION_PROMPTS_ENABLED: bool = True
    RAG_EDUCATION_QUERY_PROMPT_ENABLED: bool = True
    RAG_EDUCATION_ENTITY_TYPES_ENABLED: bool = True
    RAG_EDUCATION_FRAMEWORK_PROMPT_OVERRIDES_ENABLED: bool = True
    RAG_EDUCATION_LANGUAGE: str = "简体中文"
    RAG_EDUCATION_SUBJECT: str = "课程学习"
    RAG_EDUCATION_ENTITY_TYPES_RAW: str = (
        "course_concept,prerequisite,learning_objective,formula,theorem,"
        "algorithm,example,exercise,misconception,experiment_step,tool,dataset,assessment_point"
    )
    RAG_STORAGE_BACKEND: str = "lightrag-default"
    VECTOR_DB_PROVIDER: str = "auto"  # auto | qdrant
    VECTOR_DB_URL: str = ""
    VECTOR_DB_API_KEY: str = ""
    VECTOR_DB_COLLECTION: str = "raganything_chunks"
    GRAPH_DB_PROVIDER: str = "auto"  # auto | neo4j
    GRAPH_DB_URL: str = ""
    GRAPH_DB_DATABASE: str = "neo4j"
    GRAPH_DB_USERNAME: str = ""
    GRAPH_DB_PASSWORD: str = ""
    MULTIMODAL_ALLOW_METADATA_ONLY_INDEX: bool = True
    MULTIMODAL_AUTO_PREPROCESS_ENABLED: bool = False
    MULTIMODAL_PREPROCESS_OUTPUT_DIR: str = "./runtime_tmp/multimodal_preprocess"
    MULTIMODAL_FFMPEG_PATH: str = "ffmpeg"
    MULTIMODAL_FFPROBE_PATH: str = "ffprobe"
    MULTIMODAL_VIDEO_KEYFRAME_INTERVAL_SECONDS: int = 30
    MULTIMODAL_VIDEO_MAX_KEYFRAMES: int = 8
    CHAT_ATTACHMENT_SCOPE_PREFIX: str = "chat-attachments"
    CHAT_ATTACHMENT_PREVIEW_CHARS: int = 1200
    CHAT_ATTACHMENT_TTL_HOURS: int = 24
    ASR_PROVIDER: str = "none"  # none | faster_whisper | api
    ASR_MODEL: str = "base"
    ASR_LANGUAGE: str = ""
    ASR_DEVICE: str = "cpu"
    ASR_COMPUTE_TYPE: str = "int8"
    ASR_API_BASE: str = ""
    ASR_API_KEY: str = ""
    ASR_API_PATH: str = "/audio/transcriptions"
    ASR_API_TIMEOUT_SECONDS: float = 120.0
    ASR_API_AUTH_HEADER: str = "Authorization"
    ASR_API_AUTH_SCHEME: str = "Bearer"
    RAG_RETRIEVAL_STRATEGY: str = "hybrid"  # lexical | hybrid | graph
    RAG_RETRIEVAL_CANDIDATE_K: int = 12
    RAG_ANSWER_TOP_K: int = 3
    RAG_QUERY_REWRITE_ENABLED: bool = False
    RAG_QUERY_REWRITE_MODE: str = "hybrid"  # none | hybrid | compact | keywords; legacy simple maps to hybrid
    RAG_QUERY_REWRITE_MAX_VARIANTS: int = 3
    RERANKER_PROVIDER: str = "mock"  # mock | none | api | local
    RERANKER_MODEL: str = "mock-reranker-v1"
    RERANKER_API_BASE: str = ""
    RERANKER_API_KEY: str = ""
    RERANKER_API_PATH: str = "/rerank"
    RERANKER_API_TIMEOUT_SECONDS: float = 20.0
    RERANKER_LOCAL_MODEL: str = "local-heuristic-v1"
    KB_PARSE_MAX_RETRIES: int = 2
    KB_QUEUE_RETRY_COOLDOWN_SECONDS: int = 30
    KB_QUEUE_AUTO_RETRY_ENABLED: bool = True
    KB_QUEUE_AUTO_RETRY_MAX_ROUNDS: int = 2
    KB_INDEX_BATCH_RETRY_LIMIT: int = 50
    KB_INDEX_ALERT_NOTIFY_ADMIN: bool = True

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
        "KB_QUEUE_AUTO_RETRY_ENABLED",
        "KB_INDEX_ALERT_NOTIFY_ADMIN",
        "RAG_QUERY_REWRITE_ENABLED",
        "RAGANYTHING_STRICT_MODE",
        "RAGANYTHING_METADATA_FALLBACK_ENABLED",
        "RAGANYTHING_REQUIRE_OFFICIAL_METADATA",
        "RAG_EDUCATION_PROMPTS_ENABLED",
        "RAG_EDUCATION_QUERY_PROMPT_ENABLED",
        "RAG_EDUCATION_ENTITY_TYPES_ENABLED",
        "RAG_EDUCATION_FRAMEWORK_PROMPT_OVERRIDES_ENABLED",
        "MULTIMODAL_ALLOW_METADATA_ONLY_INDEX",
        "MULTIMODAL_AUTO_PREPROCESS_ENABLED",
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
    def EFFECTIVE_ASR_API_KEY(self) -> str:
        return self.ASR_API_KEY or self.EFFECTIVE_VLM_API_KEY or self.EFFECTIVE_LLM_API_KEY

    @property
    def EFFECTIVE_ASR_API_BASE(self) -> str:
        return self._normalize_base(self.ASR_API_BASE or self.EFFECTIVE_VLM_API_BASE or self.EFFECTIVE_LLM_API_BASE)

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
