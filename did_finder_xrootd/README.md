# ServiceX_DID_finder_XRootD
Find datasets by performing glob wildcarding via xrootd.

## Finding datasets

XRootD is a standard for remotely accessing HEP files, supported by many storage backends (EOS, dCache, etc.) This "DID finder" allows you to specify a glob wildcard pattern, such as
```
root://eospublic.cern.ch//eos/opendata/atlas/OutreachDatasets/2020-01-22/4lep/MC/*
```
to look up all the files matching this pattern and use those as input for a ServiceX transformation. In particular, files from CERN EOS are available via the gateways `eospublic.cern.ch`, `eosatlas.cern.ch`, `eoscms.cern.ch`, etc.

When accessing files from EOS, note that you must have the double slash `//` between the server name and the first element of the path!

## Running

This DID finder runs as a Temporal worker, deployed by the ServiceX Helm chart
(`helm/servicex/templates/did-finder-xrootd/deployment.yaml`). The image's entrypoint,
`scripts/start_temporal_worker.sh`, runs `python -m servicex_did_finder_xrootd.temporal_worker`: a
`DIDFinderWorker` from the DID finder lib hosts the `lookup_dataset` activity on the
`did-finder-xrootd` task queue, scheduled by the ServiceX orchestrator. The lookup
itself is `servicex_did_finder_xrootd.finder.find_files`.

The worker reads these environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal frontend |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace |
| `TEMPORAL_TASK_QUEUE` | `did-finder-xrootd` | Task queue to poll |
| `SERVICEX_INTERNAL_ENDPOINT` | (required) | e.g. `http://servicex-app:8000/servicex/internal/transformation/` |
| `DID_FINDER_MAX_CONCURRENT` | `4` | Lookups run at once (the chart sets `didFinder.xrootd.maxConcurrentLookups`) |

## DID finder library version

`servicex-did-finder-lib` is a git dependency on the library's `temporal` branch
until that work is released. `poetry.lock` pins the commit, so pick up a newer
head of the branch with:

```bash
poetry update servicex-did-finder-lib
```
