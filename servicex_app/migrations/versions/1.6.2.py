"""
Revision ID: v1_6_2
Revises: v1_5_7a
Create Date: 2025-05-13

"""
from alembic import op
import sqlalchemy as sa

revision = 'v1_6_2'
down_revision = 'v1_5_7a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('transform_result', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.execute('UPDATE transform_result SET created_at = CURRENT_TIMESTAMP')
    op.alter_column('transform_result', 'created_at', nullable=False)

    op.create_index('ix_transform_result_created_at', 'transform_result', ['created_at'])


def downgrade():
    op.drop_index('ix_transform_result_created_at', table_name='transform_result')

    op.drop_column('transform_result', 'created_at')
