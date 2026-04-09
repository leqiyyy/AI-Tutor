"""Admin settings persistence.

Revision ID: 20260402_0004
Revises: 20260402_0003
Create Date: 2026-04-02 01:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260402_0004"
down_revision = "20260402_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_settings",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("section", sa.String(length=100), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_admin_settings_section", "admin_settings", ["section"])
    op.create_index("ix_admin_settings_key", "admin_settings", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_admin_settings_key", table_name="admin_settings")
    op.drop_index("ix_admin_settings_section", table_name="admin_settings")
    op.drop_table("admin_settings")
