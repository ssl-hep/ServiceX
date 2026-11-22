# ServiceX Orchestrator

A [Temporal](https://temporal.io) worker that will own the lifecycle of ServiceX
transform requests, replacing Celery/RabbitMQ. See
[the migration plan](../docs/development/temporal-migration-plan.md).

It polls the `servicex-orchestrator` task queue. Right now it registers only
`PingWorkflow`, a smoke test that runs one activity and returns
`pong from <pod>: <message>`.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal frontend `host:port` |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace to poll |
| `TEMPORAL_TASK_QUEUE` | `servicex-orchestrator` | Task queue to poll |
| `LOG_LEVEL` | `INFO` | Python log level |

On startup the worker retries until the frontend is reachable and the namespace
exists, so it can start before the Temporal server is ready.

## Development

```bash
poetry install --with test
poetry run pytest
poetry run flake8
```

To run against a local dev server:

```bash
temporal server start-dev
poetry run servicex-orchestrator
temporal workflow execute --type PingWorkflow --task-queue servicex-orchestrator --input '"hello"'
```

## Docker

```bash
docker build -t sslhep/servicex-orchestrator:develop .
```
