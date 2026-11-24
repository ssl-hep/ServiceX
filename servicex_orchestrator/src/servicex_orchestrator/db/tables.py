"""The orchestrator's view of the ServiceX schema.

The app owns the schema (Flask-SQLAlchemy models and Alembic migrations in
servicex_app). These Core tables declare only the columns the orchestrator reads or
writes, with the types and nullability of the *migrated* database, which is not
always what the app's models say. The schema contract test checks them against a
database built by the app's migrations, and the worker checks them again at startup.

Every column has exactly one writer. Columns the orchestrator writes are marked
`info=WRITES`; a table marked `info=WRITES` is the orchestrator's entirely (it
inserts and updates every column). Everything else is read-only here, and the
orchestrator's Postgres role is refused writes to it. See the README, "Database
access".
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import ENUM

# The oldest app migration this orchestrator works with.
REQUIRED_SCHEMA_REVISION = "v1_10_0"

WRITES = {"writer": "orchestrator"}

metadata = MetaData()

# Names (not values) of servicex_app.models.TransformStatus, which is how SQLAlchemy
# stores them. The contract test fails if the orchestrator knows a label the database
# doesn't.
TRANSFORM_STATUS = ENUM(
    "submitted",
    "pending_lookup",
    "lookup",
    "running",
    "complete",
    "fatal",
    "canceled",
    "bad_dataset",
    name="transformstatus",
    create_type=False,
)

datasets = Table(
    "datasets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(1024), nullable=False),
    Column("did_finder", String(64), nullable=False),
    Column("stale", Boolean, nullable=False),
    # A plain varchar in the database, not an enum: "internal_failure" is the
    # longest value at 16 characters.
    Column("lookup_status", String(16), nullable=False, info=WRITES),
    Column("n_files", Integer, nullable=True, info=WRITES),
    Column("size", BigInteger, nullable=True, info=WRITES),
    Column("events", BigInteger, nullable=True, info=WRITES),
    Column("last_updated", DateTime, nullable=True, info=WRITES),
)

files = Table(
    "files",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("dataset_id", Integer, nullable=False),
    Column("paths", Text, nullable=False),
    Column("file_key", Text, nullable=True),
    Column("adler32", String(48), nullable=True),
    Column("file_size", BigInteger, nullable=True),
    Column("file_events", BigInteger, nullable=True),
)

requests = Table(
    "requests",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("request_id", String(48), nullable=False),
    Column("did_id", Integer, nullable=False),
    # The app sets 0 at submit (and keeps it in Celery mode); in Temporal mode the
    # orchestrator writes the file count once the dataset is known.
    Column("files", Integer, nullable=False, info=WRITES),
    # Nullable in the database although the app's model says otherwise.
    Column("status", TRANSFORM_STATUS, nullable=True, info=WRITES),
    Column("finish_time", DateTime, nullable=True, info=WRITES),
    Column("files_completed", Integer, nullable=False, info=WRITES),
    Column("files_failed", Integer, nullable=False, info=WRITES),
    # Summed over the successful files; NULL until the first one (Celery mode).
    Column("total_events", BigInteger, nullable=True, info=WRITES),
    Column("total_bytes", BigInteger, nullable=True, info=WRITES),
    Column("failure_description", String(10485760), nullable=True, info=WRITES),
    Column("workflow_id", String(255), nullable=True, info=WRITES),
    Column("workflow_run_id", String(64), nullable=True, info=WRITES),
)

transform_result = Table(
    "transform_result",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("file_id", Integer, nullable=True),
    Column("file_path", String(512), nullable=False),
    Column("request_id", String(48), nullable=False),
    Column("transform_status", String(120), nullable=False),
    Column("transform_time", Integer, nullable=True),
    Column("total_events", BigInteger, nullable=True),
    Column("total_bytes", BigInteger, nullable=True),
    Column("avg_rate", Float, nullable=True),
    # No server default: inserts must set it.
    Column("created_at", DateTime, nullable=False),
    Column("s3_object_name", String(512), nullable=True),
    info=WRITES,
)


def writes_table(table: Table) -> bool:
    return table.info.get("writer") == "orchestrator"


def writes_column(column: Column) -> bool:
    return writes_table(column.table) or column.info.get("writer") == "orchestrator"
