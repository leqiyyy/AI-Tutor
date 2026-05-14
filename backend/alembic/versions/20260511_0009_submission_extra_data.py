"""Add structured submission grading metadata.

Revision ID: 20260511_0009
Revises: 20260511_0008
Create Date: 2026-05-11 00:09:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260511_0009"
down_revision = "20260511_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.add_column(sa.Column("extra_data", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.drop_column("extra_data")
