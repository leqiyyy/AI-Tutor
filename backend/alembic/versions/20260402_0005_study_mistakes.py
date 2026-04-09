"""Study mistakes support.

Revision ID: 20260402_0005
Revises: 20260402_0004
Create Date: 2026-04-02 02:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260402_0005"
down_revision = "20260402_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "study_mistakes",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("class_id", sa.String(length=36), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("chapter", sa.String(length=200), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("my_answer", sa.Text(), nullable=True),
        sa.Column("correct_answer", sa.Text(), nullable=True),
        sa.Column("analysis", sa.Text(), nullable=True),
        sa.Column("wrong_count", sa.Integer(), nullable=True),
        sa.Column("mastered", sa.Integer(), nullable=True),
        sa.Column("last_practice_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("study_mistakes")
