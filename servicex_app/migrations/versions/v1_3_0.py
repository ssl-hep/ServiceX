"""create dataset table

Revision ID: v1_3_0
Revises: v1_1_4
Create Date: 2023-05-08 10:22:44.126667

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'v1_3_0'
down_revision = 'v1_1_4'
branch_labels = None
depends_on = None


def upgrade():

    # clean records from tables
    op.execute("DELETE from files;")
    op.execute("DELETE from requests;")
    op.execute("DELETE from transform_result;")

    # Drop Files table
    op.drop_constraint('transform_result_file_id_fkey', 'transform_result')
    op.drop_constraint('files_request_id_fkey', 'files')
    op.drop_table('files')

    # drop messages (just a cleanup)
    op.drop_column('transform_result', 'messages')

    # add datasets table
    op.create_table('datasets',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(length=1024), nullable=False),
                    sa.Column('last_used', sa.DateTime(), nullable=False),
                    sa.Column('last_updated', sa.DateTime(), nullable=True),
                    sa.Column('did_finder', sa.String(length=64), nullable=False),
                    sa.Column('n_files', sa.Integer(), nullable=True),
                    sa.Column('size', sa.BigInteger(), nullable=True),
                    sa.Column('events', sa.BigInteger(), nullable=True),
                    sa.Column('lookup_status', sa.String(16), nullable=False),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('name')
                    )
    op.create_index(op.f('ix_datasets_name'),
                    'datasets', ['name'], unique=False)

    #   Create files table
    op.create_table('files',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('dataset_id', sa.Integer(), nullable=False),
                    sa.Column('adler32', sa.String(length=48), nullable=True),
                    sa.Column('file_size', sa.BigInteger(), nullable=True),
                    sa.Column('file_events', sa.BigInteger(), nullable=True),
                    sa.Column('paths', sa.Text(), nullable=False),
                    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='cascade'),
                    sa.PrimaryKeyConstraint('id')
                    )

    # this should have worked...
    # sa.Column('dataset_id', sa.Integer(), key=sa.ForeignKey(
    # "datasets.id", ondelete='cascade'), nullable=False),

    op.create_index(op.f('ix_datasets_id'),
                    'files', ['dataset_id'], unique=False)

    #   Change requests table
    op.add_column('requests', sa.Column('did_id', sa.Integer(), nullable=False))
    op.create_foreign_key(
        'datasets_requests_fkey',
        source_table='requests',
        referent_table='datasets',
        local_cols=['did_id'],
        remote_cols=['id']
    )
    op.create_foreign_key(
        'transform_result_file_id_fkey',
        source_table='transform_result',
        referent_table='files',
        local_cols=['file_id'],
        remote_cols=['id']
    )


def downgrade():

    op.execute("DELETE from files;")
    op.execute("DELETE from requests;")
    op.execute("DELETE from transform_result;")

    op.drop_table('datasets')
    op.drop_index(op.f('ix_datasets_name'), table_name='datasets')
    op.drop_constraint('datasets_requests_fkey', 'datasets')

    op.drop_column('requests', 'did_id')

    # Drop modern files table
    op.drop_constraint('transform_result_file_id_fkey', 'transform_result')
    op.drop_constraint('files_request_id_fkey', 'files')
    op.drop_table('files')

    op.create_table('files',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('request_id', sa.String(length=48), nullable=False),
                    sa.Column('adler32', sa.String(length=48), nullable=True),
                    sa.Column('file_size', sa.BigInteger(), nullable=True),
                    sa.Column('file_events', sa.BigInteger(), nullable=True),
                    sa.Column('paths', sa.Text(), nullable=False),
                    sa.ForeignKeyConstraint(['request_id'], ['requests.request_id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )

    op.create_foreign_key(
        'files_request_id_fkey', 'files', 'requests', ['request_id'], ['request_id']
    )

    op.create_foreign_key(
        'transform_result_file_id_fkey', 'transform_result', 'files', ['id'], ['file_id']
    )

    op.add_column('transform_result', sa.Column('messages', sa.Integer(), nullable=True))
