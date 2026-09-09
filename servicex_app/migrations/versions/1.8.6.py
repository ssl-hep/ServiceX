"""
widen TransformRequest.did to match Dataset.name

Revision ID: v1_8_6
Revises: v1_8_4
Create Date: 2026-09-09 10:12:03.114217
"""

import sqlalchemy as sa
from alembic import op

revision = "v1_8_6"
down_revision = "v1_8_4"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "requests",
        "did",
        existing_type=sa.String(length=512),
        type_=sa.String(length=1024),
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        "requests",
        "did",
        existing_type=sa.String(length=1024),
        type_=sa.String(length=512),
        existing_nullable=False,
    )
