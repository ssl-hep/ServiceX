"""
add index to DatasetFile.dataset_id

Revision ID: f1c2a9d47b3e
Revises: v1_8_4
Create Date: 2026-09-09 10:12:41.183422
"""

from alembic import op

revision = "f1c2a9d47b3e"
down_revision = "v1_8_4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f("ix_files_dataset_id"), "files", ["dataset_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_files_dataset_id"), table_name="files")
