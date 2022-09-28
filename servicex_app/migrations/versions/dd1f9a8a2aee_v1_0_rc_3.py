"""V1.0-RC.3

Revision ID: dd1f9a8a2aee
Revises: 99e97a63d1bd
Create Date: 2020-08-11 16:59:41.311733

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dd1f9a8a2aee'
down_revision = '99e97a63d1bd'
branch_labels = None
depends_on = None


def upgrade():
    # RC2 and RC3 users are incompatible, so we must drop/recreate user table.
    op.drop_table('users')
    op.create_table('users',
    sa.Column('admin', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('experiment', sa.String(length=120), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('institution', sa.String(length=120), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('pending', sa.Boolean(), nullable=True),
    sa.Column('refresh_token', sa.Text(), nullable=False),
    sa.Column('sub', sa.String(length=120), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('refresh_token')
    )

    # Add submitted_by to requests table (not present in RC2)
    op.add_column('requests', sa.Column('submitted_by', sa.Integer()))
    op.create_foreign_key('requests_submitted_by_fkey', 'requests', 'users', ['submitted_by'], ['id'])

    op.add_column('requests', sa.Column('app_version', sa.String(length=64), nullable=True))
    op.add_column('requests', sa.Column('code_gen_image', sa.String(length=256), nullable=True))

def downgrade():
    op.drop_constraint('requests_submitted_by_fkey', 'requests', type_='foreignkey')
    op.drop_column('requests', 'submitted_by')

    # RC2 and RC3 users are incompatible, so we must drop/recreate user table.
    op.drop_table('users')
    op.create_table('users',
    sa.Column('admin', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('institution', sa.String(length=120), nullable=True),
    sa.Column('key', sa.String(length=120), nullable=False),
    sa.Column('pending', sa.Boolean(), nullable=True),
    sa.Column('experiment', sa.String(length=120), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )

    op.drop_column('requests', 'app_version')
    op.drop_column('requests', 'code_gen_image')
