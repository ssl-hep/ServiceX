"""SUpport unzip transformer.

Revision ID: v1_1_5
Revises: v1_1_4
Create Date: 2023-04-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'v1_1_5'
down_revision = 'v1_1_4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('requests', sa.Column("codegen_type", sa.String(256), nullable=True))


def downgrade():
    op.drop_column('requests', 'codegen_type')

