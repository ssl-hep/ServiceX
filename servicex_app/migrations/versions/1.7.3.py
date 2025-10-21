"""
Revision ID: v1_7_3
Revises: v1_7_1
Create Date: 2025-10-17

Update transformstatus enum
"""

from alembic import op
from sqlalchemy.dialects import postgresql

revision = "v1_7_3"
down_revision = "v1_7_1"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE transformstatus ADD VALUE 'bad_dataset'")


def downgrade():
    op.execute("UPDATE requests SET status='fatal' WHERE status='bad_dataset'")
    # painful by comparison
    old_status_enum_postgres = postgresql.ENUM(
        "submitted",
        "pending_lookup",
        "lookup",
        "running",
        "complete",
        "fatal",
        "canceled",
        name="transformstatus_",
        create_type=False,
    )
    old_status_enum_postgres.create(op.get_bind(), checkfirst=False)

    op.execute(
        "alter table requests ALTER COLUMN status TYPE transformstatus_ using status::text::transformstatus_"  # noqa;
    )
    op.execute("DROP TYPE transformstatus")
    op.execute("ALTER TYPE transformstatus_ RENAME TO transformstatus")
