"""
Temporal orchestrator: file identity and workflow ids

Revision ID: v1_10_0
Revises: v1_9_0
Create Date: 2026-11-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "v1_10_0"
down_revision = "v1_9_0"
branch_labels = None
depends_on = None

"""
`files.file_key` is a stable identity from the DID finder (Rucio `scope:name`, the
URL for xrootd/opendata, the path for user file lists). UNIQUE(dataset_id, file_key)
lets a retried lookup upsert its files instead of inserting duplicates, and output
object names are derived from it (temporal-migration-plan §6, §6.2).

Files cached before this migration have no key from the DID finder, so it is
backfilled from the first replica in `paths` (stored comma-joined). A dataset that
already holds duplicate rows (a lookup that was retried under Celery) gets the key on
its lowest id only; the duplicates keep NULL, which the constraint allows, so no row
that transform_result points at is deleted. The column stays nullable until every
DID finder sends a key.

`requests.workflow_id` / `workflow_run_id` record the Temporal workflow that owns the
request, for debugging and for linking the UI to the Temporal Web UI. The
orchestrator writes them.
"""


def upgrade():
    op.add_column("files", sa.Column("file_key", sa.Text(), nullable=True))
    op.execute("""
        UPDATE files
           SET file_key = split_part(paths, ',', 1)
         WHERE id IN (
               SELECT min(id)
                 FROM files
                GROUP BY dataset_id, split_part(paths, ',', 1)
         )
        """)
    op.create_unique_constraint(
        "uix_files_dataset_file_key", "files", ["dataset_id", "file_key"]
    )

    op.add_column(
        "requests", sa.Column("workflow_id", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "requests", sa.Column("workflow_run_id", sa.String(length=64), nullable=True)
    )


def downgrade():
    op.drop_column("requests", "workflow_run_id")
    op.drop_column("requests", "workflow_id")
    op.drop_constraint("uix_files_dataset_file_key", "files", type_="unique")
    op.drop_column("files", "file_key")
