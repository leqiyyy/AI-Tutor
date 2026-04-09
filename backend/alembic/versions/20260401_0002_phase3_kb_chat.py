"""Phase 3 knowledge base and chat citation tables.

Revision ID: 20260401_0002
Revises: 20260401_0001
Create Date: 2026-04-01 01:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260401_0002"
down_revision = "20260401_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kb_spaces",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("course_id", sa.String(length=36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("class_id", sa.String(length=36), sa.ForeignKey("classes.id"), nullable=True),
        sa.Column("status", sa.Enum("empty", "building", "ready", "failed", name="kb_space_status"), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("last_built_at", sa.DateTime(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "file_parse_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("kb_space_id", sa.String(length=36), sa.ForeignKey("kb_spaces.id"), nullable=False),
        sa.Column("course_id", sa.String(length=36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("class_id", sa.String(length=36), sa.ForeignKey("classes.id"), nullable=True),
        sa.Column("material_id", sa.String(length=36), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("status", sa.Enum("pending", "processing", "completed", "failed", name="file_parse_task_status"), nullable=False),
        sa.Column("parser_name", sa.String(length=100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("chunks", sa.JSON(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "chat_citations",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("message_id", sa.String(length=36), sa.ForeignKey("chat_messages.id"), nullable=False),
        sa.Column("source_name", sa.String(length=300), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("chunk_id", sa.String(length=100), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("chat_citations")
    op.drop_table("file_parse_tasks")
    op.drop_table("kb_spaces")
