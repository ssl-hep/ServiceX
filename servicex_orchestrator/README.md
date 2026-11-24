# ServiceX Orchestrator

A [Temporal](https://temporal.io) worker that will own the lifecycle of ServiceX
transform requests, replacing Celery/RabbitMQ. See
[the migration plan](../docs/development/temporal-migration-plan.md).

It polls the `servicex-orchestrator` task queue and hosts:

| Workflow | Id | Role |
|---|---|---|
| `TransformRequestWorkflow` | `transform-<request_id>` | One per request: dataset cache check, joins the lookup, dispatches files by cursor in batches, finalizes and cleans up |
| `DatasetLookupWorkflow` | `dataset-<dataset_id>` | One DID-finder lookup shared by every request for the dataset row; forwards progress to its subscribers |
| `FileBatchWorkflow` | `transform-<request_id>-batch-<n>` | Transforms one batch of files and records each result |
| `PoolManagerWorkflow` | `pool-<request_id>` | Tops up transformer pilots to `min(backlog, max_workers)` |
| `PingWorkflow` | any | Smoke test: returns `pong from <pod>: <message>` |

The ServiceX app starts `TransformRequestWorkflow` on submit when its config has
`ORCHESTRATOR = 'temporal'`. It sends a plain JSON object whose keys must match
`models.TransformRequestInput`.

**The dataset activities are real**, on the ServiceX Postgres:
`activities/datasets.py` (`get_or_create_dataset`, `read_dataset`,
`mark_dataset_looking`, `mark_dataset_complete`, `mark_dataset_failed`) and
`activities/request_status.py` (`record_request_workflow`, `mark_request_running`).
A complete dataset row is a cache hit: the request starts no lookup.
`mark_dataset_complete` counts `n_files`, `size` and `events` from the dataset's
`files` rows, which is what the request transforms, rather than trusting the DID
finder's summary of its last attempt. A failed lookup's message goes to the dataset's
log records (shown on the dataset page); the app has no column for it.

**The rest are stubs for now** (`activities/stubs.py`). Each one logs what it would
do (`STUB launch_pilots: would create Jobs [...]`) and returns fake data: the stub DID
lookup "finds" `STUB_DATASET_FILES` files (it writes no `files` rows, so its dataset
ends `complete` with 0 files), `claim_file_batch` makes up files by id, and every
transform succeeds. `start_dataset_lookup` is real: it starts or joins the lookup
workflow. The transform activities run on the orchestrator's own queue until
transformer pilots poll `transform-<request_id>`.

`DatasetLookupWorkflow` schedules `lookup_dataset` on `did-finder-<scheme>`
(`did-finder-rucio`, ...), where the DID finder for that scheme polls. Where no
real DID finder runs for a scheme, list it in `STUB_DID_FINDER_SCHEMES`: the
worker then also polls `did-finder-<scheme>` with the stub lookup. Without
either, a lookup times out after 15 minutes waiting to be picked up.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal frontend `host:port` |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace to poll |
| `TEMPORAL_TASK_QUEUE` | `servicex-orchestrator` | Task queue to poll |
| `LOG_LEVEL` | `INFO` | Python log level |
| `VECTOR_HOST`, `VECTOR_PORT` | unset | The release's Vector aggregator. When set, logs are also shipped there as `log_messages` rows (`component` = `servicex_orchestrator`). The chart sets them when `logging.vector.enabled` |
| `INSTANCE_NAME` | `Unknown` | Release name, written to each log row's `instance` |
| `STUB_DATASET_FILES` | `25` | Files every stub DID lookup "finds" |
| `STUB_ACTIVITY_DELAY_SECONDS` | `0.5` | How long each stub lookup chunk and stub transform takes |
| `STUB_DID_FINDER_SCHEMES` | empty | Comma-separated DID schemes (e.g. `rucio,cernopendata`) whose `did-finder-<scheme>` queue this worker serves with the stub lookup. Leave a scheme out once its real DID finder runs. The chart sets it from `orchestrator.stubDidFinderSchemes` |
| `DATABASE_URL` | required | The ServiceX Postgres, as the orchestrator's own role (`postgresql://` or `postgresql+asyncpg://`). The worker exits if it is unset. The chart builds it from `orchestrator.database` |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | `5`, `5` | Connection pool per replica |

On startup the worker first checks the database and exits with a clear error if it can't connect, or if the schema or the role's grants
fall short of what `db/tables.py` declares. It then retries until the Temporal
frontend is reachable and the namespace exists, so it can start before the Temporal
server is ready.

## Logs

Every record logged through `workflow.logger` / `activity.logger` gets a
`request_id`, derived from the Temporal context the SDK puts on the record: the
workflow id `transform-<id>`, `transform-<id>-batch-<n>` or `pool-<id>`. An activity
uses the id of the workflow that scheduled it. That is what makes them show
up in a request's log grid. The shared `dataset-<dataset_id>` lookup has no single
request, so its records carry `dataset_id` instead, like the DID finders' logs.
Records from the SDK's own internals (e.g. `temporalio.worker.*`) carry neither.

## Database access

The orchestrator reads and writes the ServiceX Postgres directly, not through the
app's HTTP API. The app still owns the schema: its models and Alembic migrations
define every table, and its migrations are the only thing that changes them. The
orchestrator needs `postgres.enabled=true`; the chart refuses to render it on SQLite.

### One writer per column

| | App writes | Orchestrator writes | Orchestrator reads |
|---|---|---|---|
| `datasets` | creates rows, `name`, `did_finder`, `last_used`, `stale` | `lookup_status`, `n_files`, `size`, `events`, `last_updated` | all |
| `files` | all inserts, as an upsert on `(dataset_id, file_key)` (DID finders PUT them to the app) | nothing | all |
| `requests` | creates rows, every user-facing field (`status` and `files` at submit; in Celery mode it keeps writing them) | `status`, `files` (Temporal mode, once the dataset's file count is known), `finish_time`, `files_completed`, `files_failed`, `workflow_id`, `workflow_run_id` | those, plus `id`, `request_id`, `did_id` |
| `transform_result` | nothing | all inserts and updates | all |

Nothing else (users, log records, ...) is visible to the orchestrator.

### The role

The orchestrator connects as its own role, `servicex_orchestrator` by default, never as
the `postgres` superuser. Its grants are written down once, in
`servicex_app/servicex_app/orchestrator_db_role.py`, and applied by
`flask orchestrator-db-role`. The app's `boot.sh` runs that after every
`flask db upgrade` when `ORCHESTRATOR_DB_PASSWORD` is set. In one transaction it
creates the role if needed, sets its password, revokes everything it holds, and grants:

- `SELECT` on `datasets`, `files`, `alembic_version`, and the `requests` columns above;
- column-level `UPDATE` on the orchestrator-owned columns of `datasets` and `requests`;
- `SELECT`, `INSERT`, `UPDATE` on `transform_result`, and its id sequence.

There is no `DELETE` and no DDL. `CREATE` on schema `public` is revoked from
`PUBLIC`, since Postgres 14 grants it to every role.

Because the grants are re-applied after every migration, a later migration needs no
grant bookkeeping. A column it adds to a table the orchestrator only reads is readable
(table-level `SELECT`), but never writable unless it is listed. If a listed column is
renamed or dropped, the `GRANT` fails and the app's boot stops, instead of the
grants drifting. The chart passes the password to both the app and the orchestrator
from a Secret: `secrets` under `orchestrator-db-password`, or else
`<release>-orchestrator-db` from `orchestrator.database.password`.

### The orchestrator's view of the schema

`src/servicex_orchestrator/db/tables.py` declares SQLAlchemy Core tables with only
the columns the orchestrator uses. The types and nullability are those of the
*migrated* database, which is not always what the app's models say (for example,
`datasets.lookup_status` is a `varchar(16)`, and `requests.status` is nullable).
Columns it writes are marked `info=WRITES`. It never imports the app's models.

To give the orchestrator a new column:

1. Add it in an app migration and in `models.py`.
2. List it in `orchestrator_db_role.py`.
3. Declare it in `db/tables.py`, and bump `REQUIRED_SCHEMA_REVISION` if it is new.
4. Run the contract test.

### Schema contract and DB tests

`scripts/schema-contract-test.sh` needs docker and both poetry envs. It:

1. starts a throwaway `postgres:14` (`scripts/throwaway-postgres.sh`);
2. runs the app's migrations up, down one revision and up again, checking the
   `file_key` backfill;
3. creates the role twice;
4. runs `pytest -m "contract or db"`: the contract tests and `tests/db`, which run
   the dataset and request activities as the role, and requests with their lookup
   on the time-skipping server (complete, does-not-exist, a retried lookup leaving
   no duplicate files, and a cache hit starting no lookup).

The tests check that every orchestrator column exists with a compatible type,
nullability and enum labels, and that the role holds the privileges it needs. They
also run the orchestrator's kinds of statements as the role, and check that it is
refused UPDATE on app-owned columns, DELETE, TRUNCATE, writes to `files`, other
tables, and DDL. Renaming a column on either side fails it. CI runs it in the
`schema-contract` job against a service container. Without
`CONTRACT_ADMIN_URL`/`CONTRACT_ORCHESTRATOR_URL`, a plain `pytest` skips them.

### Lookup e2e test

`scripts/lookup-e2e-test.sh` runs lookups end to end on a throwaway Postgres: the
real app in Temporal mode (`flask run`), the orchestrator worker, and the real
`DIDFinderWorker` from a ServiceX_DID_Finder_lib checkout (`DID_FINDER_LIB_DIR`,
default `../ServiceX_DID_Finder_lib`) over a fake catalog (`tests/e2e/fake_finder.py`),
on a local Temporal dev server. It runs a lookup twice on one dataset, then a request
that must hit the cache, and a lookup that fails halfway and is retried. It checks
that there are no duplicate `files` rows and that the dataset and requests are right.
It needs docker and all three poetry envs, so CI doesn't run it.

### Rules for DB activities

- **One idempotent statement per activity.** Activities are retried, and a zombie
  attempt can finish late. Write upserts (`INSERT ... ON CONFLICT DO UPDATE`) and
  absolute values (`SET files_completed = :n`), never increments
  (`SET files_completed = files_completed + 1`). Then running it twice is the same as
  running it once.
- **Decisions stay in the workflow.** An activity does not read state, decide, and
  write. The workflow holds the counters and the status, decides, and passes the
  result to the activity to record. The database is the record, not the source of the
  decision.
- **Write only the columns the table above gives the orchestrator.** The role enforces
  it, and the contract test proves it.

## Development

```bash
poetry install --with test
poetry run pytest
poetry run flake8
scripts/schema-contract-test.sh   # needs docker and servicex_app's poetry env
scripts/lookup-e2e-test.sh        # also needs the DID finder lib's poetry env
```

To run against a local dev server:

```bash
temporal server start-dev
DATABASE_URL=postgresql://servicex_orchestrator:<password>@localhost:5432/servicex \
  STUB_DID_FINDER_SCHEMES=rucio poetry run servicex-orchestrator
temporal workflow execute --type PingWorkflow --task-queue servicex-orchestrator --input '"hello"'
```

And a stubbed transform request (watch the worker's log and the UI at
http://localhost:8233):

```bash
temporal workflow execute --type TransformRequestWorkflow --task-queue servicex-orchestrator \
  --workflow-id transform-test-1 \
  --input '{"request_id": "test-1", "did": "mc23:some.dataset", "did_scheme": "rucio",
            "dataset_id": 1, "image": "sslhep/servicex_func_adl_xaod_transformer:develop",
            "generated_code_cm": "cm", "transformer_language": "python",
            "transformer_command": "transform_single_file.py",
            "result_destination": "object-store", "result_format": "parquet",
            "max_workers": 5}'
```

`tests/test_workflows.py` runs most scenarios on the time-skipping test server, with
the DB activities replaced by an in-memory fake (`tests/fakes.py`).
Signal-with-start and cancel-during-timer tests use a real dev server
(`WorkflowEnvironment.start_local`), because the test server mishandles both.

## Docker

```bash
docker build -t sslhep/servicex-orchestrator:develop .
```
