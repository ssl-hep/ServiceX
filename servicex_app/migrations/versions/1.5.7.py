"""Add unique constraint to TransformResult on request_id and file_id

Revision ID: 1.5.7
Revises: v1_5_6
Create Date: 2025-01-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'v1_5_7'
down_revision = 'v1_5_6'
branch_labels = None
depends_on = None

def upgrade():
    # Add unique constraint
    op.create_unique_constraint('uix_file_request', 'transform_result', ['file_id', 'request_id'])


def downgrade():
    # Remove unique constraint
    op.drop_constraint('uix_file_request', 'transform_result', type_='unique')
