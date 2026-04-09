from app.core.database import Base, SessionLocal, check_database_connection, engine, get_db, initialize_database


def init_db():
    """Backward-compatible alias for database bootstrap."""
    initialize_database()


__all__ = [
    "Base",
    "SessionLocal",
    "engine",
    "get_db",
    "init_db",
    "initialize_database",
    "check_database_connection",
]
