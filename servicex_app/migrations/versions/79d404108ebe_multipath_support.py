"""multipath support

Revision ID: 79d404108ebe
Revises: 5893086ec440
Create Date: 2022-01-25 10:12:23.947313

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table

# revision identifiers, used by Alembic.
revision = '79d404108ebe'
down_revision = '5893086ec440'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('files', 'file_path')
    op.add_column('files', sa.Column('paths', sa.Text()))
    files_table = table(
        'files',
        sa.Column('file_path', sa.String(length=512)),
        sa.Column('paths', sa.Text())
        # Other columns not needed for the data migration
    )
    op.execute(
        files_table
        .update()
        .values({'paths': 'old'})
    )
    op.alter_column('files', 'paths', nullable=False)


def downgrade():
    op.drop_column('files', 'paths')
    op.add_column('files', sa.Column('file_path', sa.String(length=512), nullable=False))
