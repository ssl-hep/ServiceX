# ServiceX Orchestrator

A [Temporal](https://temporal.io) worker that will own the lifecycle of ServiceX
transform requests, replacing Celery/RabbitMQ. See
[the migration plan](../docs/development/temporal-migration-plan.md).

It polls the `servicex-orchestrator` task queue and hosts:

| Workflow | Id | Role |
|---|---|---|
| `TransformRequestWorkflow` | `transform-<request_id>` | One per request: dataset cache check, joins the lookup, dispatches files by cursor in batches, finalizes and cleans up |
| `DatasetLookupWorkflow` | `dataset-<sha256(scheme://did)>` | One DID-finder lookup shared by every request for the dataset; forwards progress to its subscribers |
| `FileBatchWorkflow` | `transform-<request_id>-batch-<n>` | Transforms one batch of files and records each result |
| `PoolManagerWorkflow` | `pool-<request_id>` | Tops up transformer pilots to `min(backlog, max_workers)` |
| `PingWorkflow` | any | Smoke test: returns `pong from <pod>: <message>` |

The ServiceX app starts `TransformRequestWorkflow` on submit when its config has
`ORCHESTRATOR = 'temporal'`. It sends a plain JSON object whose keys must match
`models.TransformRequestInput`.

**The activities are stubs for now** (`activities/stubs.py`). Each one logs what
it would do (`STUB launch_pilots: would create Jobs [...]`) and returns fake
data: every DID lookup "finds" `STUB_DATASET_FILES` files, and every transform
succeeds. The exception is `start_dataset_lookup`, which really starts or joins
the lookup workflow. The transform activities run on the orchestrator's own queue
until transformer pilots poll `transform-<request_id>`.

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

On startup the worker retries until the frontend is reachable and the namespace
exists, so it can start before the Temporal server is ready.

## Logs

Every record logged through `workflow.logger` / `activity.logger` gets a
`request_id`, derived from the Temporal context the SDK puts on the record: the
workflow id `transform-<id>`, `transform-<id>-batch-<n>` or `pool-<id>`. An activity
uses the id of the workflow that scheduled it. That is what makes them show
up in a request's log grid. The shared `dataset-<hash>` lookup has no single
request, so its records carry `dataset_id` instead, like the DID finders' logs.
Records from the SDK's own internals (e.g. `temporalio.worker.*`) carry neither.

## Development

```bash
poetry install --with test
poetry run pytest
poetry run flake8
```

To run against a local dev server:

```bash
temporal server start-dev
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

`tests/test_workflows.py` runs most scenarios on the time-skipping test server.
Signal-with-start and cancel-during-timer tests use a real dev server
(`WorkflowEnvironment.start_local`), because the test server mishandles both.

## Docker

```bash
docker build -t sslhep/servicex-orchestrator:develop .
```
