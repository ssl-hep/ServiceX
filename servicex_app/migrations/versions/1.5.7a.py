"""Switch to index on email not sub

Revision ID: v1_5_7a
Revises: v1_5_7
Create Date: 2025-01-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'v1_5_7a'
down_revision = 'v1_5_7'
branch_labels = None
depends_on = None

def upgrade():
    # Remove unique constraint
    op.drop_index('ix_users_sub', 'users')
    op.create_index('ix_users_email', 'users', [sa.text('lower(email)')], unique=True)

def downgrade():
    # Remove unique constraint
    op.drop_index('ix_users_email', 'users')
    op.create_index('ix_users_sub', 'users', ['sub'], unique=True)
