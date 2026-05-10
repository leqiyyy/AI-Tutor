"""Add authentication security fields and indexes.

Revision ID: 20260402_0006
Revises: 20260402_0005
Create Date: 2026-04-02 00:06:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260402_0006"
down_revision = "20260402_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("locked_until", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_login_at", sa.DateTime(), nullable=True))
        batch_op.create_unique_constraint("uq_users_student_id", ["student_id"])
        batch_op.create_unique_constraint("uq_users_teacher_id", ["teacher_id"])

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("failed_login_count", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_teacher_id", type_="unique")
        batch_op.drop_constraint("uq_users_student_id", type_="unique")
        batch_op.drop_column("last_login_at")
        batch_op.drop_column("locked_until")
        batch_op.drop_column("failed_login_count")
