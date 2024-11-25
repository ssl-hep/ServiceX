"""empty message

Revision ID: 1.5.6
Revises: v1_5_5
Create Date: 2024-11-23 17:30:18.079736

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'v1_5_6'
down_revision = 'v1_5_5'
branch_labels = None
depends_on = None

"""
Clean up indexes and constraints in the database 
"""
def upgrade():
    op.drop_index('ix_dataset_id', table_name='files')
    op.drop_constraint('files_dataset_id_fkey', 'files', type_='foreignkey')
    op.create_foreign_key(None, 'files', 'datasets', ['dataset_id'], ['id'])
    op.alter_column('requests', 'files',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.drop_index('ix_transform_result_request_id', table_name='transform_result')
    op.drop_index('ix_transform_result_transform_status', table_name='transform_result')
    op.create_index(op.f('ix_users_sub'), 'users', ['sub'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_users_sub'), table_name='users')
    op.create_index('ix_transform_result_transform_status', 'transform_result', ['transform_status'], unique=False)
    op.create_index('ix_transform_result_request_id', 'transform_result', ['request_id'], unique=False)
    op.alter_column('requests', 'files',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_constraint(None, 'files', type_='foreignkey')
    op.create_foreign_key('files_dataset_id_fkey', 'files', 'datasets', ['dataset_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_dataset_id', 'files', ['dataset_id'], unique=False)
