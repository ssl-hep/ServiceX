# ServiceX_DID_finder_ServiceX
Use a ServiceX transformation ID to look up the outputs of that transform.

## Finding files
Provide a ServiceX transform ID. The code will look up URLs for accessing the results of that transformation, assuming they are still available.

## Running

This DID finder runs as a Temporal worker, deployed by the ServiceX Helm chart
(`helm/servicex/templates/did-finder-servicex/deployment.yaml`). The image's entrypoint,
`scripts/start_temporal_worker.sh`, runs `python -m servicex_did_finder_servicex.temporal_worker`: a
`DIDFinderWorker` from the DID finder lib hosts the `lookup_dataset` activity on the
`did-finder-servicex` task queue, scheduled by the ServiceX orchestrator. The lookup
itself is `servicex_did_finder_servicex.finder.find_files`.

The worker reads these environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal frontend |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace |
| `TEMPORAL_TASK_QUEUE` | `did-finder-servicex` | Task queue to poll |
| `SERVICEX_INTERNAL_ENDPOINT` | (required) | e.g. `http://servicex-app:8000/servicex/internal/transformation/` |
| `DID_FINDER_MAX_CONCURRENT` | `4` | Lookups run at once (the chart sets `didFinder.servicex.maxConcurrentLookups`) |
| `SERVICEX_ENDPOINT` | (required) | Base URL of the ServiceX app whose results are looked up, e.g. `http://servicex-app:8000` |

## DID finder library version

`servicex-did-finder-lib` is a git dependency on the library's `temporal` branch
until that work is released. `poetry.lock` pins the commit, so pick up a newer
head of the branch with:

```bash
poetry update servicex-did-finder-lib
```
