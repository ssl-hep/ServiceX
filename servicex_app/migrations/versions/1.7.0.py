"""
Revision ID: v1_7_0
Revises: v1_5_7a
Create Date: 2025-05-13

"""
from alembic import op
import sqlalchemy as sa

revision = 'v1_7_0'
down_revision = 'v1_5_7a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('transform_result', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.execute('UPDATE transform_result SET created_at = CURRENT_TIMESTAMP')
    op.alter_column('transform_result', 'created_at', nullable=False)
    op.create_index('ix_transform_result_created_at', 'transform_result', ['created_at'])

    op.add_column('transform_result', sa.Column('s3_object_name', sa.String(length=512), nullable=True))
    op.create_index('ix_transform_result_s3_object_name', 'transform_result', ['s3_object_name'])

    op.create_index('ix_transform_result_request_id', 'transform_result', ['request_id'])


def downgrade():
    op.drop_index('ix_transform_result_created_at', table_name='transform_result')
    op.drop_column('transform_result', 'created_at')

    op.drop_index('ix_transform_result_s3_object_name', table_name='transform_result')
    op.drop_column('transform_result', 's3_object_name')

    op.drop_index('ix_transform_result_request_id', table_name='transform_result')

