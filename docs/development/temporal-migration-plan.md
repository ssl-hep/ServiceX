# Plan: Replacing Celery/RabbitMQ with Temporal

Status: **draft for discussion** — nothing implemented yet.

### Decisions so far

| Topic | Decision |
|---|---|
| Temporal hosting | Self-hosted, deployed through the ServiceX Helm chart |
| Completion reporting | Workers report only through Temporal (the activity's return value). Workers make no HTTP calls to the app |
| Pool scope | One worker pool per transform request |
| Max workers | A cap set in the cluster's Helm values. The user's `workers` argument is no longer used to size the pool |
| Worker lifecycle | Workers run as Kubernetes Jobs: pilots that exit when idle, not a Deployment |
| Output object names | Change them as needed. Names are derived from the input file's identity, not the replica |

## 1. Goals

- One durable Temporal workflow per transform request, owning its whole lifecycle:
  dataset cache lookup → DID resolution (if needed) → worker pool → per-file transforms →
  completion/cancellation/cleanup.
- Every file in the dataset is **attempted at least once** and ends in a recorded
  terminal state (`success` or `failure`). No file silently disappears, the way it can
  today if a Celery message is lost or a pod dies holding an unacked task.
- Rely on Temporal's retries, timeouts and heartbeats instead of the hand-written retry
  loops we have now (`reliable_requests.py`, `file_complete_ops_retry`, the retry loops in
  `servicex_did_finder_lib.ServiceXAdapter`, dead-letter queues).
- Duplicate executions are expected and harmless: every side effect is idempotent.
- The worker backend is pluggable: Kubernetes now, HTCondor later, with no workflow changes.
- Remove RabbitMQ, Celery, kombu and the per-request HPA when the migration is done.

## 2. What exists today

| Concern | Current implementation |
|---|---|
| Submit | `resources/transformation/submit.py`: codegen, image validation, bucket create, `DatasetManager`, Celery `send_task` to the DID finder, `TransformerManager.start_transformers` |
| Dataset cache | `datasets` / `files` tables. `Dataset.name` = full DID, unique among non-stale rows (`ix_datasets_name`). `DatasetStatus`: `created/looking/complete/does_not_exist/...` |
| Concurrent lookups | Second request for a dataset that is still `looking` gets `pending_lookup`; `add_file_to_dataset` / `fileset_complete` fan files out to those requests |
| DID finders | Celery workers (`DIDFinderApp(Celery)` in the external `servicex_did_finder_lib`), queue `<scheme>.lookup_dataset`. They stream replicas back by HTTP `PUT /servicex/internal/transformation/<dataset_id>/files` in chunks of 300, then `/complete` or `/error` |
| Fan-out | `celery/server_tasks.add_files_to_processing_queue` builds a Celery `group` of `transformer_sidecar.transform_file` tasks, routed to `transformer-<request_id>` (non-durable, auto-delete) |
| Workers | `Deployment` `transformer-<request_id>` + `autoscaling/v1` HPA on CPU. Sidecar = Celery worker, `--concurrency 1`, talks to the science container over a localhost socket; generated code mounted from a ConfigMap |
| Completion | Sidecar `PUT .../file-complete`; `record_file_complete` already corrects counters on a re-report, and `transform_result` has `UNIQUE(file_id, request_id)` |
| Shutdown | App deletes Deployment/HPA and calls `celery_app.control.cancel_consumer` |

Idempotency we already have, and will lean on:
- `transform_result` `UNIQUE(file_id, request_id)` and the counter correction in
  `record_file_complete` make a duplicate completion report safe.
- Output object names are a deterministic hash (`hash_path`), and an S3 PUT replaces the
  whole object, so re-uploading the same output is safe.

Gaps that break idempotency and must be fixed (§6):
- **`files` has no uniqueness on file identity.** A retried DID lookup would insert
  every file twice.
- **The output object name comes from the *replica path*, not the file.** If a retry
  succeeds on a different replica, one input file ends up with two output objects, and
  the client downloads both.

## 3. Target architecture

```mermaid
flowchart LR
  App[Flask app<br/>submit / cancel / status] -- start / cancel / query --> T[(Temporal)]
  subgraph Orchestrator worker  (task queue: servicex-orchestrator)
    TRW[TransformRequestWorkflow<br/>id = transform-&lt;request_id&gt;]
    DLW[DatasetLookupWorkflow<br/>id = dataset-&lt;did_hash&gt;]
    BW[FileBatchWorkflow children]
    PMW[PoolManagerWorkflow<br/>id = pool-&lt;request_id&gt;]
    DBA[DB / k8s / object-store activities]
  end
  subgraph DID finders  (task queue: did-finder-&lt;scheme&gt;)
    LA[lookup_dataset activity]
  end
  subgraph Transform workers  (task queue: transform-&lt;request_id&gt;)
    TF[transform_file activity<br/>sidecar + science container]
  end
  T --- TRW & DLW & BW & PMW
  DLW --> LA -- upsert file batches --> DB[(Postgres<br/>dataset cache)]
  BW --> TF -- write output --> S3[(MinIO / volume)]
  PMW -- WorkerBackend: K8s now, HTCondor later --> TF
```

New deployable: **`servicex-orchestrator`**. It is a Temporal worker that imports
`servicex_app` (models, DB session, object-store and k8s helpers) and hosts all workflows
plus the activities that touch Postgres, Kubernetes and MinIO. The Flask app only starts,
cancels, signals and queries workflows; it no longer drives any work itself.

> Implemented so far: `servicex_orchestrator/` is its own Poetry project (it doesn't import
> `servicex_app`) with all four workflows below. Every side-effect activity is a logging
> stub. The app starts `TransformRequestWorkflow` by name with a JSON input when
> `ORCHESTRATOR = 'temporal'` (`servicex_app/temporal_adaptor.py`).

### Task queues

| Queue | Pollers | Concurrency |
|---|---|---|
| `servicex-orchestrator` | orchestrator deployment | workflows + DB/k8s activities |
| `did-finder-<scheme>` (`rucio`, `cernopendata`, `xrootd`, `atlasopenmagic`, `servicex`) | that DID finder's deployment | small, e.g. 4 |
| `transform-<request_id>` | that request's transform workers | `max_concurrent_activities=1` per worker (science container is not thread-safe) |

Per-request transform queues keep today's isolation: each request has its own image and
generated code, so no worker can pick up another request's file.

## 4. Workflows

### 4.1 `TransformRequestWorkflow` (one per request; id `transform-<request_id>`)

Input: `request_id`, the parsed DID (or file list), image, generated-code reference,
result destination/format, the user's `workers` hint.

1. **Hash the DID.** Pure, deterministic code inside the workflow:
   `did_hash = sha256(f"{scheme}://{normalized_did}")`. For a file list, use the existing
   `DatasetManager.file_list_hash`.
2. **Check the dataset cache** (activity `get_or_create_dataset(did_hash, did, scheme)`).
   It returns `{dataset_id, lookup_status, n_files_known}` and links the request
   (`requests.did_id`).
3. **Make sure a lookup is running if one is needed.** If the status is not `complete`,
   an activity starts `DatasetLookupWorkflow` with id `dataset-<did_hash>` and
   `WorkflowIdConflictPolicy.USE_EXISTING`. Temporal's workflow-ID uniqueness replaces the
   `pending_lookup` bookkeeping: N concurrent requests for one DID start exactly one
   lookup. The request then subscribes to that lookup by signal:
   `subscribe(request_workflow_id)`.
4. **Start the pool manager** as a child workflow (`pool-<request_id>`) once the first files
   are known. That way we don't launch pods for a dataset that turns out not to exist.
5. **Consume files by cursor, not by payload.** The workflow keeps `cursor = last
   files.id dispatched`. Each time it is woken (a `files_available(high_water_mark)` signal
   from the lookup, or straight away when the dataset is already complete), it runs
   `dispatch` until it catches up:
   - activity `claim_file_batch(dataset_id, after=cursor, limit=BATCH)` returns the file
     ids and replica lists;
   - it starts a `FileBatchWorkflow` child for that batch, with at most
     `MAX_CONCURRENT_BATCHES` running at once.

   Signals carry only a number, so a lost, duplicated or out-of-order signal does no harm:
   the cursor is authoritative and the DB holds the data.
6. **Finish.** Once the lookup is `complete` and every batch child has returned, an
   activity `finalize_request` sets the status to `complete` (or `fatal` / `bad_dataset`),
   then the workflow cancels the pool manager, which scales to zero, and runs the
   `cleanup_request` activity (ConfigMap, any leftover transformer Jobs, temp secrets).
7. **History hygiene.** After every K batch children, or when
   `workflow.info().is_continue_as_new_suggested()` says so, `continue_as_new` with
   `{cursor, counters, lookup_done, pool_handle}`.

Signals, queries and updates:
- `cancel`: the app calls `handle.cancel()`. The workflow catches `CancelledError`, cancels
  its children, and runs cleanup activities so they finish despite the cancellation.
  Activities see the cancel through their heartbeats.
- `files_available(hwm)` and `lookup_finished(status)`: sent by the lookup workflow.
- `status` query: cursor, batches in flight, counts. The DB stays the source of truth
  for the UI and REST API; the query is for debugging.

### 4.2 `DatasetLookupWorkflow` (one per dataset; id `dataset-<did_hash>`)

1. Activity `mark_dataset_looking(dataset_id)`.
2. Activity `lookup_dataset(did, dataset_id)` on the `did-finder-<scheme>` queue (§5.1).
   It is long-running and heartbeats `{files_written, last_file_key}`. Each time it
   commits a batch to the DB it also signals the dataset workflow
   `progress(hwm)`. The workflow forwards `files_available(hwm)` to every subscriber, and
   any subscriber that arrives late gets the current hwm on `subscribe`.
3. On success: activity `mark_dataset_complete(summary)` (n_files, size, events), then
   `lookup_finished("complete")` to the subscribers.
4. On a non-retryable `DatasetNotFound` or `BadDID` error: mark the dataset
   `does_not_exist` / `bad_name` and notify subscribers, which then end as `bad_dataset`.
   On exhausted retries: mark it `internal_failure`.
5. The dataset row is the cache, so the workflow ends when the lookup ends. A new request
   for a `complete` dataset never starts one. A `stale` dataset gets a new row and
   therefore a new lookup.

> Why not have the request workflow call the DID finder directly? Lookups are shared across
> requests, a child workflow can have only one parent, and one long activity can't stream
> results to several workflows. Making the lookup its own workflow with a deterministic ID
> gives us dedupe and fan-out for free.

### 4.3 `FileBatchWorkflow` (child; id `transform-<request_id>-batch-<n>`)

Runs one `transform_file` activity per file in the batch, all at once (the batch size
caps how many are pending). After each activity returns, either success or terminal
failure, it runs `record_file_result` on the orchestrator queue. It returns batch counts
to the parent.

Batching keeps us inside Temporal's limits: about 2,000 pending activities per workflow,
and history warnings around 10k events / 10 MB, with a hard cap of 50k events / 50 MB. A
100k-file dataset is about 200 batch children of 500 files each.

### 4.4 `PoolManagerWorkflow` (child; id `pool-<request_id>`)

Workers are **pilots**. Each one is a single-pod Kubernetes Job. It polls
`transform-<request_id>`, processes files one at a time, and exits 0 once the queue has
been idle for `WORKER_IDLE_TIMEOUT` (e.g. 2 min). The pool manager only ever *adds*
pilots. The pool shrinks by itself as pilots go idle and exit, so no pod is killed in the
middle of a file. HTCondor uses the same model, which is why we chose it.

A reconcile loop runs on a workflow timer (every `POOL_RECONCILE_SECONDS`, e.g. 30 s):

```
outstanding = files dispatched but not finished      (kept in the parent; sent by signal)
live        = await activity count_live_pilots(request_id)   # pending + running
desired     = min(outstanding, TRANSFORMER_MAX_WORKERS)
if live < desired:
    await activity launch_pilots(request_id, spec, desired - live, generation)
```

- `outstanding` arrives from the parent through a `backlog(n)` signal whenever a batch
  starts or ends. It replaces the CPU HPA, which was always a poor proxy for queue depth.
- `TRANSFORMER_MAX_WORKERS` is a Helm value (`transformer.maxWorkers`) and the only limit
  on pool size. The `workers` field on submit is still accepted but ignored; log a
  deprecation warning.
- `launch_pilots` is idempotent. Each Job is named
  `transformer-<request_id>-<generation>-<i>`, where `generation` is a counter the
  workflow advances on each reconcile. If the activity retries, it gets `AlreadyExists`
  and treats that as success. That way a retry never launches extra pilots.
- `count_live_pilots` counts Jobs with label `servicex/request-id=<id>` that are neither
  `Complete` nor `Failed`. Pods stuck `Pending` because the cluster is full still count as
  live, so we don't keep piling on more Jobs.
- Job settings: `backoffLimit: 0` (Temporal retries the file, so Kubernetes must not
  restart the pod), `restartPolicy: Never`, `ttlSecondsAfterFinished: 300`, and
  `activeDeadlineSeconds` as a backstop. The pod template (science container, sidecar,
  Vector, volumes, x509 secret, generated-code ConfigMap) is what
  `TransformerManager.create_job_object` builds today, moved from a Deployment to a Job.
- If a pilot crashes (OOM, eviction), its in-flight file times out on heartbeat and is
  retried on another pilot. The next reconcile replaces the pilot if work remains.
- A pilot can also exit after `WORKER_MAX_FILES` or `WORKER_MAX_LIFETIME` (optional),
  which limits memory leaks in science images.
- `launch_pilots`, `count_live_pilots` and `delete_pool` go through a **`WorkerBackend`**
  interface:
  - `KubernetesJobBackend`: now.
  - `HTCondorBackend` (later): `condor_submit` / `condor_q` / `condor_rm` of pilots that
    run the same worker image under Apptainer. The workflow doesn't change.
- When cancelled (the request is done or the user cancelled), `delete_pool` deletes all
  of the request's Jobs (propagation `Background`). Pods get SIGTERM and exit within their
  grace period. After a cancel, any file still in flight belongs to a request that is
  already over.

## 5. Activities

### 5.1 DID finder: `lookup_dataset`

- `servicex_did_finder_lib` gains a `DIDFinderWorker` alongside `DIDFinderApp` (Celery).
  It hosts a Temporal activity that wraps the user's `find_files` generator, the same
  interface finders implement today, so the five finders change only their entrypoint.
- It writes files through the **existing internal endpoint** (`PUT .../files`) or a new
  orchestrator activity endpoint. That endpoint becomes an *upsert* keyed on
  `(dataset_id, file_key)` (§6.1), so a retried lookup that replays files from the
  start creates no duplicates.
- Retry policy: initial 10 s, backoff 2.0, max interval 10 min, max attempts ~10.
  Non-retryable types: `DatasetNotFound`, `BadDID`, `AuthFailed` (a bad x509 should not
  hammer Rucio).
- Timeouts: `heartbeat_timeout` 2 min, `start_to_close` 6 h, `schedule_to_start` 15 min
  so that a dead DID-finder deployment surfaces quickly as an error instead of a hang.
- On retry it may resume from the heartbeat details (`last_file_key`) when the finder
  can (Rucio list order is stable). Otherwise it starts over and the upsert absorbs
  the duplicates.

### 5.2 Worker: `transform_file`

The sidecar's Celery task becomes a Temporal activity with the same body (replica
prioritization, science-container socket handshake, stats parsing, format conversion,
upload). The changes:

- **Heartbeat** from a background thread every ~30 s while the science container runs.
  `heartbeat_timeout` ≈ 3 min. A pod that is OOM-killed, evicted or preempted (or an
  HTCondor slot that vanishes) is detected within minutes and the file goes to another
  worker. That is the at-least-once guarantee.
- **The result goes back as the activity's return value**:
  `{status, object_name, replica_used, events, bytes, timings, stats}`. The
  orchestrator's `record_file_result` writes it to the DB. Workers make no HTTP calls to
  the app at all. They need only Temporal and the object store, which is what HTCondor
  workers will be able to reach. The internal `file-complete` endpoint is deleted along
  with Celery.
- Failed transforms report through Temporal too: the `ApplicationError` details carry the
  stats (`error_info`, `log_body`), and the batch workflow records them.
- Error classification:
  | Situation | Raise | Effect |
  |---|---|---|
  | Replica unreachable, xrootd timeout, MinIO 5xx, socket hiccup | retryable `ApplicationError("TransientIO")` | Temporal retries with backoff, possibly on another worker |
  | Every replica tried and the science container reports a data error | non-retryable `ApplicationError("FileFailed", details=stats)` | file recorded as `failure`, no retry |
  | Science container reports a code/compile error | non-retryable `ApplicationError("TransformCodeError")` | file `failure`; the parent may fail fast (§7) |
  | Worker dies | (heartbeat timeout) | retried |
- Retry policy: initial 15 s, backoff 2.0, max interval 5 min, **max attempts 5**
  (configurable). If retries run out on a retryable error, the batch workflow catches
  `ActivityError` and records the file as `failure`. The file is still accounted for.
- Timeouts: `start_to_close` = `TRANSFORM_FILE_TIMEOUT` (e.g. 4 h). No
  `schedule_to_start`, because files wait legitimately while the pool scales up.
  `schedule_to_close` = 24 h as a backstop.
- Pilot lifecycle: the worker's main loop tracks the time since its last activity ended,
  and once it passes `WORKER_IDLE_TIMEOUT` it calls `worker.shutdown()` and exits 0. On
  SIGTERM it stops polling and lets the current activity finish if it can
  (`graceful_shutdown_timeout` ≤ pod `terminationGracePeriodSeconds`). A Job completes
  only when every regular container has exited:
  - **Science container**: the sidecar sends `stop.` over the socket. `watch.sh` already
    exits its loop on `stop.` or on a closed socket.
  - **Vector**: it runs forever, so it becomes a native sidecar (an init container with
    `restartPolicy: Always`, GA in K8s 1.29). Kubernetes stops it after the main
    containers exit, so Vector still flushes the last science log chunk. This needs
    K8s ≥ 1.29 at every site (see the open questions).

### 5.3 Orchestrator activities (DB / k8s / object store)

`get_or_create_dataset`, `mark_dataset_*`, `claim_file_batch`, `record_file_result`,
`finalize_request`, `describe_pool`, `scale_pool`, `delete_pool`, `cleanup_request`,
`create_bucket`. Every one is idempotent (upserts, `ON CONFLICT`, "delete if exists").
They use a short retry policy with unlimited attempts and capped backoff, so a Postgres
or API-server blip stalls the request rather than failing it.

## 6. Idempotency and duplicate handling

| Side effect | Why it is safe to repeat |
|---|---|
| Starting the dataset lookup | Workflow ID `dataset-<did_hash>` + `USE_EXISTING` |
| Starting the request workflow | Workflow ID `transform-<request_id>`; the app retries the start freely |
| Inserting dataset files | **New** `UNIQUE(dataset_id, file_key)`, insert `ON CONFLICT DO UPDATE` (refresh replicas) |
| Writing an output object | **New** name derived from `file_id` (or `file_key`), not the replica, so any attempt on any replica overwrites the same key. S3 PUT/multipart-complete is atomic |
| Recording a file result | Existing `UNIQUE(file_id, request_id)` + counter correction in `record_file_complete`. Moved into an activity |
| A zombie worker finishing after its attempt timed out | Temporal rejects the stale completion; its upload overwrites the identical object key |
| Scaling the pool | `scale_pool(n)` sets an absolute replica count; it never adds to the current one |

### 6.1 Schema changes (Alembic)
- `datasets.did_hash` (CHAR(64)), indexed and unique where `stale = false`. This becomes
  the cache key in place of the 1024-char `name`.
- `files.file_key`: a stable identity from the DID finder (Rucio `scope:name`, the URL
  for xrootd/opendata, the path for user lists), plus `UNIQUE(dataset_id, file_key)`.
- `requests.workflow_id` and `requests.workflow_run_id`, for debugging and the UI's link
  to the Temporal Web UI.

### 6.2 Output naming change (approved)
`hash_path(replica)` becomes `hash(file_key) + suffix`. Clients that list the bucket are
unaffected. Anything that maps output names back to inputs uses the `file-urls` endpoint.
Datasets cached before the migration have no `file_key`. The migration backfills it from
`paths` (the first replica), which keeps names stable for files that never move between
replicas.

## 7. Request-level failure policy

- **Fail fast.** If the first N files (e.g. 3) all fail with `TransformCodeError`, or the
  failure ratio passes a threshold, the request workflow cancels outstanding batches and
  ends `fatal`. This replaces burning hours of compute on a bad query.
- **Partial success.** Otherwise the request ends `complete` with `files_failed > 0`, as
  today.
- Dataset errors make the request `bad_dataset`. Infrastructure failure past every retry
  makes it `fatal`, with the cause stored on the request.

## 8. Infrastructure

- **Temporal server** is self-hosted as a dependency of the ServiceX chart
  (`temporalio/temporal` subchart, gated by `temporal.enabled`), with `temporal.address`
  as an override for sites that already run one. Persistence is Postgres; whether it
  shares the ServiceX instance is still open. Elasticsearch is not needed: SQL
  visibility is enough at our scale. The chart's schema-setup Jobs run as Helm hooks
  before the orchestrator starts.
- Transformer RBAC: the orchestrator's ServiceAccount needs `create/list/delete` on
  `batch/jobs` and `list` on pods in the transformer namespace. It no longer needs
  Deployments or HPAs.
- Namespace `servicex-<release>`, retention 7 days.
- Helm values: `temporal.enabled`, `temporal.address`, `temporal.namespace`, TLS certs;
  `transformer.maxWorkers`, `transformer.idleTimeout`. Remove the `rabbitmq` subchart and
  the `transformer.autoscaler` HPA block at the end.
- Expose the Temporal Web UI behind the same auth as the app, or admin-only.
- CronJobs that just POST to internal endpoints (data lifecycle, k8s cleanup) can stay as
  they are, or move to Temporal Schedules later (out of scope).
- Local dev: `temporal server start-dev` in the `Procfile`/overmind setup in place of
  RabbitMQ.

## 9. Code changes by component

| Component | Change |
|---|---|
| `servicex_app` | `submit.py` keeps its synchronous validation and codegen (fast user errors), creates the bucket and request row, then `client.start_workflow(...)`. Cancel calls `handle.cancel()`. Delete `celery/`, `celery_task_router.py`, `rabbit_adaptor.py`, `lookup_result_processor.py`, the Celery wiring in `app.py`. `fileset_complete`/`fileset_error`/`add_file_to_dataset` collapse into the upsert path, or stay as thin endpoints used by the DID finder activity |
| new `servicex_app/orchestrator/` | workflows, orchestrator activities, the `WorkerBackend` interface + `KubernetesJobBackend` (pod template extracted from `transformer_manager.py`), worker entrypoint |
| `transformer_sidecar` | Replace Celery with a `temporalio` worker that runs as a pilot (idle-exit, `stop.` to the science container); split `transform_file` so the core is plain Python and the activity wrapper adds heartbeating and error classification; new object naming; remove `ServiceXAdapter` calls to the app; drop the upload *process* (it existed only to coexist with Celery's prefork) |
| `servicex_did_finder_lib` (external) | Add the `DIDFinderWorker` Temporal entrypoint; keep the Celery entrypoint for one release for the cutover. **Ben cuts the release; the finders pin the RC he names.** |
| `did_finder_*` | Switch the entrypoint; emit `file_key` |
| `helm/` | Temporal subchart, orchestrator Deployment + RBAC (it now creates the transformer Jobs in place of the app), drop RabbitMQ/HPA, add `transformer.maxWorkers` / `idleTimeout` |
| `kubernetes_resource_cleanup` | Sweep orphaned transformer *Jobs* (label `servicex/request-id` of a finished request) in place of Deployments/HPAs |
| Docs | Rewrite the RabbitMQ / Celery / Transformers sections of `docs/development/architecture.md` |

## 10. Phased delivery

1. **Foundations.** Temporal in Helm and local dev; orchestrator skeleton; Alembic
   migration (`did_hash`, `file_key` + unique, `workflow_id`); output naming by
   `file_key` (this can ship on its own under Celery).
2. **Lookup path.** `DatasetLookupWorkflow` + `DIDFinderWorker` in the lib (RC); Rucio
   finder first, then the other four.
3. **Transform path.** `TransformRequestWorkflow`, `FileBatchWorkflow`, the sidecar as a
   Temporal pilot worker, `PoolManagerWorkflow` + `KubernetesJobBackend`, Vector as a
   native sidecar.
4. **Cutover behind a flag.** `ORCHESTRATOR=celery|temporal` in the app config, so we can
   run both on a dev instance (UC AF / FAB) and compare file counts and output for the
   same requests.
5. **Remove Celery/RabbitMQ.** Delete the code paths, subchart, HPA and kombu deps; update
   the docs.
6. **(Future) HTCondor backend.**

## 11. Testing

- Unit-test workflows with `temporalio.testing.WorkflowEnvironment.start_time_skipping()`
  and mocked activities. Scenarios: an already-cached dataset; two concurrent requests
  for the same DID (exactly one lookup); a lookup that fails halfway and retries (no
  duplicate files); the pool manager under a full cluster (pending pilots counted, no
  Job pile-up); `launch_pilots` retried (no extra Jobs); a worker killed mid-file
  (heartbeat timeout → retry → one output object, one result row); every replica bad (file `failure`, request still completes);
  fail-fast; cancel during lookup and during transforms (cleanup runs); continue-as-new
  boundaries.
- Replay tests against recorded histories in CI, to catch non-determinism before deploys.
  Use `workflow.patched()` / worker versioning for changes to running workflows.
- Integration: kind cluster with `temporal server start-dev`, a CERN Open Data request
  end to end; chaos with `kubectl delete pod` on transformers and DID finders.

## 12. Open questions

Resolved: hosting, completion reporting, pool scope, max workers, pod lifecycle and
output naming (see *Decisions so far* at the top).

1. **Max-workers cap scope.** Is `transformer.maxWorkers` a cap *per request* (each pool
   gets up to N pilots) or a *cluster-wide total* shared by every running request? This
   plan assumes per request. A cluster-wide total needs one coordinator, for example a
   singleton `WorkerBudgetWorkflow` that pool managers ask for slots, and a fairness rule.
2. **Temporal's Postgres.** Should Temporal's databases (`temporal` and
   `temporal_visibility`) live on the existing ServiceX Postgres instance, or get their own
   instance? Today's chart runs Postgres without persistence by default. Temporal must keep
   its state across restarts, or in-flight requests are lost.
3. **Kubernetes version.** Treating Vector as a native sidecar needs K8s ≥ 1.29 at every
   deployment site. Is that true, or do we need a fallback (the sidecar sends Vector a
   shutdown via its API)?
4. **Codegen placement.** I propose keeping codegen and image validation synchronous in
   `POST /submit`, so syntax errors come back as an immediate 400. Agree?
5. **HTCondor preconditions.** Off-cluster pilots need (a) the Temporal frontend exposed
   with mTLS, (b) the generated code delivered without a ConfigMap (object store or in the
   activity input), (c) the x509 proxy and object-store credentials. Should we do (b) now
   so the K8s Job path already matches?
6. **Retry budget and fail-fast.** Max attempts per file (I suggest 5)? Fail-fast
   thresholds (the first N files all hit code errors, or failure ratio > X%)?
7. **`file_key` for each finder.** Rucio `scope:name` is clear. What is the stable
   identity for CERN Open Data, xrootd glob and atlasopenmagic results?
8. **Pilot tuning.** Defaults for `WORKER_IDLE_TIMEOUT` (2 min?) and whether to cap
   files or lifetime per pilot. Idle-exit trades a few minutes of idle pods against
   cold starts when a lookup is still streaming files slowly.
9. **Stale datasets.** If a dataset is marked stale while a request is still consuming
   it, should that request finish on the old file set (my assumption) or switch?
10. **Cutover.** Run both orchestrators side by side behind a flag for a release, or a
    single cutover release? Can in-flight Celery requests be drained at deploy time?
11. **Volume (posix) destination.** Is it still in use? Its output names need the same
    `file_key` change, and partial writes to a shared filesystem aren't atomic the way S3
    PUTs are, so we would write to a temp name and rename.
