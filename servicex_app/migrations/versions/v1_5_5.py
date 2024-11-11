"""
Mark dataset rows as stale

Revision ID: v1_5_5
Revises: v1_3_0
Create Date: 2024-11-11 16:06:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'v1_5_5'
down_revision = 'v1_3_0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('datasets', sa.Column('stale',
                                        sa.Boolean(),
                                        nullable=False,
                                        server_default='false'))
    # This was never used, so a fine time to delete it
    op.drop_column('transform_result', 'did')


def downgrade():
    op.drop_column('datasets', 'stale')
    # No need to add the transform_result.did column back in
