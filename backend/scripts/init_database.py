"""Initialize the production database before starting app services.

This script handles two valid states:
- empty database: run Alembic migrations to head;
- legacy database created by SQLAlchemy create_all: verify all model tables exist,
  then stamp Alembic to head so future migrations work normally.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import app.models  # noqa: E402,F401
from app.core.config import settings  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
from app.db.seed import seed_data  # noqa: E402

ALEMBIC_INI = BASE_DIR / "alembic.ini"


def _alembic_config() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL_EFFECTIVE)
    return cfg


def _has_alembic_version(existing_tables: set[str]) -> bool:
    if "alembic_version" not in existing_tables:
        return False

    with engine.connect() as connection:
        result = connection.execute(text("SELECT version_num FROM alembic_version"))
        return result.first() is not None


def _stamp_legacy_create_all_database(cfg: Config, existing_tables: set[str]) -> bool:
    expected_tables = set(Base.metadata.tables)
    app_tables = expected_tables & existing_tables
    if not app_tables:
        return False

    missing_tables = sorted(expected_tables - existing_tables)
    if missing_tables:
        missing = ", ".join(missing_tables)
        raise RuntimeError(
            "Database already contains app tables but is missing model tables: "
            f"{missing}. Refusing to stamp Alembic; repair or recreate the database first."
        )

    command.stamp(cfg, "head")
    return True


def initialize() -> None:
    cfg = _alembic_config()
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    if _has_alembic_version(existing_tables):
        command.upgrade(cfg, "head")
    elif _stamp_legacy_create_all_database(cfg, existing_tables):
        print("Stamped legacy create_all database to Alembic head.")
    else:
        command.upgrade(cfg, "head")

    if settings.SEED_DEMO_DATA:
        seed_data()
        print("Seeded demo data.")


if __name__ == "__main__":
    os.chdir(BASE_DIR)
    initialize()
