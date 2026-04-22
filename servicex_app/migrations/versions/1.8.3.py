"""
add index to UserModel.sub

Revision ID: v1_8_3
Revises: v1_7_3
Create Date: 2026-03-04 20:52:15.921295
"""

from alembic import op

revision = "v1_8_3"
down_revision = "v1_7_3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f("ix_users_sub"), "users", ["sub"], unique=True)


def downgrade():
    op.drop_index(op.f("ix_users_sub"), table_name="users")
