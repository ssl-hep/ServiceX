"""cleanup file_status.

Revision ID: 208309600a27
Revises: 79d404108ebe
Create Date: 2022-11-07 17:07:37.063768

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '208309600a27'
down_revision = '79d404108ebe'
branch_labels = None
depends_on = None


def upgrade():
    # dropping unused table
    op.drop_table('file_status')

    # adding columns to requests so we don't need to always look up transform results
    op.add_column('requests', sa.Column('files_completed', sa.Integer(), nullable=False))
    op.add_column('requests', sa.Column('files_failed', sa.Integer(), nullable=False))
    op.drop_column('requests', 'files_skipped')

    # speeds up transform result lookups
    op.create_index(op.f('ix_transform_result_request_id'),
                    'transform_result', ['request_id'], unique=False)
    op.create_index(op.f('ix_transform_result_transform_status'),
                    'transform_result', ['transform_status'], unique=False)


def downgrade():

    op.create_table('file_status',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('file_id', sa.Integer(), nullable=False),
                    sa.Column('request_id', sa.String(length=48), nullable=False),
                    sa.Column('status', sa.String(length=128), nullable=False),
                    sa.Column('timestamp', sa.DateTime(), nullable=False),
                    sa.Column('pod_name', sa.String(length=128), nullable=True),
                    sa.Column('info', sa.String(length=10485760), nullable=True),
                    sa.ForeignKeyConstraint(['request_id'], ['requests.request_id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )

    op.drop_column('requests', 'files_completed')
    op.drop_column('requests', 'files_failed')
    op.add_column('requests', sa.Column('files_skipped', sa.Integer(), nullable=True))

    op.drop_index(op.f('ix_transform_result_request_id'), table_name='transform_result')
    op.drop_index(op.f('ix_transform_result_transform_status'), table_name='transform_result')
