"""Support for multiple code generators.

Revision ID: v1_1_4
Revises: v1_1_3
Create Date: 2023-02-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'v1_1_4'
down_revision = 'v1_1_3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('requests', sa.Column("transformer_language", sa.String(256), nullable=True))
    op.add_column('requests', sa.Column("transformer_command", sa.String(256), nullable=True))


def downgrade():
    op.drop_column('requests', 'transformer_language')
    op.drop_column('requests', 'transformer_command')

