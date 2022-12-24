"""Allow user token to be null.

Revision ID: v1_1_3
Revises: 208309600a27
Create Date: 2022-12-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'v1_1_3'
down_revision = '208309600a27'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('refresh_token',
                              existing_type=sa.Text,
                              nullable=True)


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('refresh_token',
                              existing_type=sa.Text,
                              nullable=False)
