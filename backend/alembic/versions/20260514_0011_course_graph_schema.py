"""add course graph schema

Revision ID: 20260514_0011
Revises: 20260511_0010
Create Date: 2026-05-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260514_0011"
down_revision = "20260511_0010"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("courses") as batch_op:
        batch_op.add_column(sa.Column("graph_schema", sa.JSON(), nullable=True))
    with op.batch_alter_table("classes") as batch_op:
        batch_op.add_column(sa.Column("graph_schema", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("classes") as batch_op:
        batch_op.drop_column("graph_schema")
    with op.batch_alter_table("courses") as batch_op:
        batch_op.drop_column("graph_schema")
