from alembic import op
import sqlalchemy as sa

revision = 'v1_6_2'
down_revision = 'v1_5_7a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('files', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('files', sa.Column('updated_at', sa.DateTime(), nullable=True))

    op.execute('UPDATE files SET created_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP')

    op.alter_column('files', 'created_at', nullable=False)
    op.alter_column('files', 'updated_at', nullable=False)

    op.create_index('ix_files_created_at', 'files', ['created_at'])
    op.create_index('ix_files_updated_at', 'files', ['updated_at'])


def downgrade():
    op.drop_index('ix_files_created_at', table_name='files')
    op.drop_index('ix_files_updated_at', table_name='files')

    op.drop_column('files', 'created_at')
    op.drop_column('files', 'updated_at')