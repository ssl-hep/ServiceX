"""
add partial unique index to datasets

Revision ID: v1_8_3a
Revises: v1_8_3
Create Date: 2026-05-11 20:13:17.154362
"""

from alembic import op
from sqlalchemy import text

revision = "v1_8_3a"
down_revision = "v1_8_3"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index(op.f("ix_datasets_name"), table_name="datasets")
    op.create_index(
        op.f("ix_datasets_name"),
        "datasets",
        ["name"],
        unique=True,
        postgresql_where=text("stale IS FALSE"),
    )


def downgrade():
    op.drop_index(
        op.f("ix_datasets_name"),
        table_name="datasets",
        postgresql_where=text("stale IS FALSE"),
    )
    op.create_index(op.f("ix_datasets_name"), "datasets", ["name"], unique=False)
