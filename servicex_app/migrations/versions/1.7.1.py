"""
Revision ID: v1_7_1
Revises: v1_7_0a
Create Date: 2025-07-04

Increase title field length from 512 to 10240 characters
"""

from alembic import op
import sqlalchemy as sa

revision = "v1_7_1"
down_revision = "v1_7_0a"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "requests",
        "title",
        existing_type=sa.String(length=512),
        type_=sa.String(length=10240),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "requests",
        "title",
        existing_type=sa.String(length=10240),
        type_=sa.String(length=512),
        nullable=True,
    )
