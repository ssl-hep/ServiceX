"""Add log_messages table for Vector sidecar log shipping

Revision ID: v1_8_4
Revises: v1_8_3a
Create Date: 2026-07-03 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "v1_8_4"
down_revision = "v1_8_3a"
branch_labels = None
depends_on = None

"""
Create the log_messages table that the Vector sidecar writes application log
records into. The `id` is a plain string (UUID minted by Vector), not a serial,
so Vector's `INSERT ... SELECT * FROM json_populate_recordset(...)` never has to
supply an auto-generated primary key.
"""


def upgrade():
    op.create_table(
        "log_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("level", sa.String(length=16), nullable=True),
        sa.Column("logger", sa.String(length=255), nullable=True),
        sa.Column("instance", sa.String(length=255), nullable=True),
        sa.Column("component", sa.String(length=64), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("log_messages")
