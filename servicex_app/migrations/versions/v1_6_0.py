"""
Mark dataset rows as stale

Revision ID: v1_6_0
Revises: v1_5_5
Create Date: 2024-11-14 18:19:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'v1_6_0'
down_revision = 'v1_5_5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('requests', sa.Column('archived',
                                        sa.Boolean(),
                                        nullable=False,
                                        server_default='false'))

def downgrade():
    op.drop_column('requests', 'archived')
