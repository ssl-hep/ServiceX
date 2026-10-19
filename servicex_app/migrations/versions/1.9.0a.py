"""
- add output_path column to TransformRequest
- widen TransformRequest.did to match Dataset.name

Revision ID: v1_9_0a
Revises: v1_9_0
Create Date: 2026-08-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "v1_9_0a"
down_revision = "v1_9_0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "requests",
        sa.Column("output_path", sa.Text(), nullable=True),
    )

    op.execute(
        "UPDATE requests SET output_path = request_id "
        "WHERE output_path IS NULL AND result_destination = 'object-store'"
    )

    op.alter_column(
        "requests",
        "did",
        existing_type=sa.String(length=512),
        type_=sa.String(length=1024),
        existing_nullable=False,
    )


def downgrade():
    op.drop_column("requests", "output_path")

    op.alter_column(
        "requests",
        "did",
        existing_type=sa.String(length=1024),
        type_=sa.String(length=512),
        existing_nullable=False,
    )
