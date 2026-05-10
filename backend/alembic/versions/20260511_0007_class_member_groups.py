"""Add persisted class member groups.

Revision ID: 20260511_0007
Revises: 20260402_0006
Create Date: 2026-05-11 00:07:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260511_0007"
down_revision = "20260402_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("class_members") as batch_op:
        batch_op.add_column(sa.Column("group_no", sa.Integer(), nullable=False, server_default="1"))

    with op.batch_alter_table("class_members") as batch_op:
        batch_op.alter_column("group_no", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("class_members") as batch_op:
        batch_op.drop_column("group_no")
