from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Shared SQLAlchemy declarative base."""


def _build_engine() -> Engine:
    connect_args: dict = {}
    engine_kwargs: dict = {
        "echo": settings.DEBUG,
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
    }

    if settings.DATABASE_IS_SQLITE:
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30
    else:
        engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
        engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW

    return create_engine(
        settings.DATABASE_URL_EFFECTIVE,
        connect_args=connect_args,
        **engine_kwargs,
    )


engine = _build_engine()


if settings.DATABASE_IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialize_database() -> None:
    """Create all database tables for development bootstrap."""
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_runtime_schema_compatibility()


def _ensure_runtime_schema_compatibility() -> None:
    """Best-effort additive schema upgrades for local SQLite development."""
    if not settings.DATABASE_IS_SQLITE:
        return

    alter_plan = {
        "knowledge_entities": {
            "confidence": "ALTER TABLE knowledge_entities ADD COLUMN confidence FLOAT",
            "source_span": "ALTER TABLE knowledge_entities ADD COLUMN source_span JSON",
            "provenance": "ALTER TABLE knowledge_entities ADD COLUMN provenance JSON",
            "updated_at": "ALTER TABLE knowledge_entities ADD COLUMN updated_at DATETIME",
        },
        "knowledge_relations": {
            "confidence": "ALTER TABLE knowledge_relations ADD COLUMN confidence FLOAT",
            "source_span": "ALTER TABLE knowledge_relations ADD COLUMN source_span JSON",
            "provenance": "ALTER TABLE knowledge_relations ADD COLUMN provenance JSON",
            "updated_at": "ALTER TABLE knowledge_relations ADD COLUMN updated_at DATETIME",
        },
    }

    with engine.begin() as connection:
        for table_name, columns in alter_plan.items():
            existing_columns = _sqlite_columns(connection, table_name)
            for column_name, ddl in columns.items():
                if column_name in existing_columns:
                    continue
                connection.execute(text(ddl))

        connection.execute(text(
            "UPDATE knowledge_entities "
            "SET confidence = COALESCE(confidence, 0.6), "
            "updated_at = COALESCE(updated_at, created_at)"
        ))
        connection.execute(text(
            "UPDATE knowledge_relations "
            "SET confidence = COALESCE(confidence, 0.55), "
            "updated_at = COALESCE(updated_at, created_at)"
        ))


def _sqlite_columns(connection, table_name: str) -> set[str]:
    result = connection.execute(text(f"PRAGMA table_info({table_name})"))
    return {row[1] for row in result.fetchall()}


def check_database_connection() -> tuple[bool, str]:
    """Run a trivial query to confirm database connectivity."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:  # pragma: no cover - defensive health path
        return False, str(exc)
