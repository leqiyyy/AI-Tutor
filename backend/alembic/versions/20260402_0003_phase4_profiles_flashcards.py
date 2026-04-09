"""Phase 4 student profiles, flashcard records, and review sync records.

Revision ID: 20260402_0003
Revises: 20260401_0002
Create Date: 2026-04-02 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260402_0003"
down_revision = "20260401_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("preferred_courses", sa.JSON(), nullable=True),
        sa.Column("strong_topics", sa.JSON(), nullable=True),
        sa.Column("weak_topics", sa.JSON(), nullable=True),
        sa.Column("total_questions", sa.Integer(), nullable=True),
        sa.Column("dislike_count", sa.Integer(), nullable=True),
        sa.Column("task_completion_rate", sa.Float(), nullable=True),
        sa.Column("activity_score", sa.Float(), nullable=True),
        sa.Column("last_active_at", sa.DateTime(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "flashcard_records",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("flashcard_id", sa.String(length=36), sa.ForeignKey("flashcards.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("response", sa.String(length=50), nullable=True),
        sa.Column("interval_before", sa.Integer(), nullable=True),
        sa.Column("interval_after", sa.Integer(), nullable=True),
        sa.Column("next_review_at", sa.DateTime(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "review_sync_records",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("review_id", sa.String(length=36), sa.ForeignKey("review_items.id"), nullable=False),
        sa.Column("class_id", sa.String(length=36), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("question_content", sa.Text(), nullable=False),
        sa.Column("final_answer", sa.Text(), nullable=False),
        sa.Column("sync_status", sa.Enum("pending", "synced", "failed", name="review_sync_status"), nullable=False),
        sa.Column("sync_note", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("review_sync_records")
    op.drop_table("flashcard_records")
    op.drop_table("student_profiles")
