from collections.abc import Generator

from sqlalchemy import create_engine, text
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
    else:
        engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
        engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW

    return create_engine(
        settings.DATABASE_URL_EFFECTIVE,
        connect_args=connect_args,
        **engine_kwargs,
    )


engine = _build_engine()
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


def check_database_connection() -> tuple[bool, str]:
    """Run a trivial query to confirm database connectivity."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:  # pragma: no cover - defensive health path
        return False, str(exc)
