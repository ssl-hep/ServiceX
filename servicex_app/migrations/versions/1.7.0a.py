"""
Revision ID: v1_7_0a
Revises: v1_7_0
Create Date: 2025-06-25

Increase title field length from 128 to 512 characters
"""

from alembic import op
import sqlalchemy as sa

revision = "v1_7_0a"
down_revision = "v1_7_0"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "requests",
        "title",
        existing_type=sa.String(length=128),
        type_=sa.String(length=512),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "requests",
        "title",
        existing_type=sa.String(length=512),
        type_=sa.String(length=128),
        nullable=True,
    )
