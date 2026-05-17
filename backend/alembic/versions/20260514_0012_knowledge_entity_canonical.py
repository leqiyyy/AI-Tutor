"""Add canonical entity fields for knowledge graph projection.

Revision ID: 20260514_0012
Revises: 20260514_0011
Create Date: 2026-05-14 18:50:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260514_0012"
down_revision = "20260514_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_entities", sa.Column("canonical_name", sa.String(length=300), nullable=True))
    op.add_column("knowledge_entities", sa.Column("aliases", sa.JSON(), nullable=True))
    op.execute("UPDATE knowledge_entities SET canonical_name = name WHERE canonical_name IS NULL")


def downgrade() -> None:
    op.drop_column("knowledge_entities", "aliases")
    op.drop_column("knowledge_entities", "canonical_name")
