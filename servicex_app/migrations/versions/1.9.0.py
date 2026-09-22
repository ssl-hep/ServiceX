"""Add log_messages table for Vector sidecar log shipping

Revision ID: v1_9_0
Revises: v1_8_4
Create Date: 2026-07-03 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "v1_9_0"
down_revision = "v1_8_4"
branch_labels = None
depends_on = None

"""
Create the log_messages table that the Vector sidecar writes application log
records into. The `id` is a plain string (UUID minted by Vector), not a serial,
so Vector's `INSERT ... SELECT * FROM json_populate_recordset(...)` never has to
supply an auto-generated primary key.

Severity is stored twice on purpose: `level` is the name the UI renders, and
`level_no` is python's numeric levelno, which is what gets compared. The log
grid's filter is a minimum severity, so on the name alone it would have to be an
IN over a hardcoded, ordered list of level names; on the number it is a single
`level_no >= n`. The aggregator's vector config derives the number from the name
for every record, whatever produced it.

Each record is keyed by either `request_id` or `dataset_id` and never both, so
the lookup indexes are partial: a record with a null key column is dead weight
in that column's index.

The request_id index carries `timestamp DESC` as a second column because the
web log grid always reads one transform's records newest-first, a page at a
time. With the timestamp in the index Postgres walks it in the order the page
already wants and stops after the page is full; on a bare request_id index it
would instead have to read every record for the transform and sort them to
answer for page 1. `level_no` is deliberately absent: as a key column it would
break the timestamp ordering, and as an INCLUDE it measurably buys nothing,
since the grid selects whole rows and so visits the heap for each one anyway.
The dataset_id index has no second column either: nothing reads those records in
order, they are only matched and deleted when their dataset is purged.
"""


def upgrade():
    op.create_table(
        "log_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("level", sa.String(length=16), nullable=True),
        sa.Column("level_no", sa.Integer(), nullable=True),
        sa.Column("logger", sa.String(length=255), nullable=True),
        sa.Column("instance", sa.String(length=255), nullable=True),
        sa.Column("component", sa.String(length=64), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=48), nullable=True),
        sa.Column("dataset_id", sa.Integer(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_log_messages_request_id"),
        "log_messages",
        ["request_id", sa.text("timestamp DESC")],
        unique=False,
        postgresql_where=text("request_id IS NOT NULL"),
    )
    op.create_index(
        op.f("ix_log_messages_dataset_id"),
        "log_messages",
        ["dataset_id"],
        unique=False,
        postgresql_where=text("dataset_id IS NOT NULL"),
    )


def downgrade():
    op.drop_index(op.f("ix_log_messages_dataset_id"), table_name="log_messages")
    op.drop_index(op.f("ix_log_messages_request_id"), table_name="log_messages")
    op.drop_table("log_messages")
