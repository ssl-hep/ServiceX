"""removing Kafka column

Revision ID: 5893086ec440
Revises: a33a96f0f035
Create Date: 2021-11-15 11:33:20.740149

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5893086ec440'
down_revision = 'a33a96f0f035'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('requests', 'kafka_broker')
    op.drop_column('requests', 'chunk_size')


def downgrade():
    op.add_column('requests', sa.Column('kafka_broker', sa.String(length=128), nullable=True))
    op.add_column('requests', sa.Column('chunk_size', sa.Integer(), nullable=True))
