"""
add index to TransformRequest.submit_time

Revision ID: v1_8_4
Revises: v1_8_3a
Create Date: 2026-07-30 20:52:15.921295
"""

from alembic import op

revision = "v1_8_4"
down_revision = "v1_8_3a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        op.f("ix_requests_submit_time"),
        "requests",
        ["submit_time"],
        unique=False
    )


def downgrade():
    op.drop_index(
        op.f("ix_requests_submit_time"),
        table_name="requests"
    )
