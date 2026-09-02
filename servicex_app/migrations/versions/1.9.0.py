"""
add output_path column to TransformRequest

Revision ID: v1_9_0
Revises: v1_8_4
Create Date: 2026-08-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "v1_9_0"
down_revision = "v1_8_4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "requests",
        sa.Column("output_path", sa.String(length=1024), nullable=True),
    )

    op.execute(
        "UPDATE requests SET output_path = request_id "
        "WHERE output_path IS NULL AND result_destination = 'object-store'"
    )


def downgrade():
    op.drop_column("requests", "output_path")
