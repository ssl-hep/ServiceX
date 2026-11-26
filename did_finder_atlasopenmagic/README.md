# ServiceX_DID_finder_ATLASOpenMagic
 Access datasets for ServiceX with `atlasopenmagic`.

## Finding datasets

The ATLAS experiment hosts releases of [ATLAS Open Data](https://opendata.atlas.cern/). The proton-proton simulations and data are ROOT files, which come in two flavors: [education](https://opendata.atlas.cern/docs/category/data-for-education) and [research](https://opendata.atlas.cern/docs/category/data-for-research). The former are flat ROOT files with a limited set of branches, and the latter are in the PHYSLITE format which is also readable via `uproot` although with a more complicated schema (the `coffea` PHYSLITE schema is recommended for analysis). There are additional datasets for heavy ion collisions (also ROOT) and pure event generator output (in HEPMC format).

The [`atlasopenmagic`](https://github.com/atlas-outreach-data-tools/atlasopenmagic) package is provided as an interface to this data. To look up the files for a dataset, you must provide the _release_ for the dataset, as well as the _dataset ID_ (this is either a numeric string, corresponding to the ATLAS Monte Carlo simulation sample ID, or the string "data" for data). Optionally, where supported by the release, a _skim_ can be specifed. The `atlasopenmagic` DID finder accepts a single string encoding all these, which must be of the form `<release>/<dataset_id>` or `<release>/<dataset_id>/<skim>` where the appropriate replacements are made. The assumption is that the user will use `atlasopenmagic` directly in their code to handle the metadata aspects of using the ATLAS Open Data (e.g.\ sample cross sections, initial number of events, etc.) while using ServiceX to apply event selection and column reduction to the files.

## Running

This DID finder runs as a Temporal worker, deployed by the ServiceX Helm chart
(`helm/servicex/templates/did-finder-atlasopenmagic/deployment.yaml`). The image's entrypoint,
`scripts/start_temporal_worker.sh`, runs `python -m did_finder_atlasopenmagic.temporal_worker`: a
`DIDFinderWorker` from the DID finder lib hosts the `lookup_dataset` activity on the
`did-finder-atlasopenmagic` task queue, scheduled by the ServiceX orchestrator. The lookup
itself is `did_finder_atlasopenmagic.finder.find_files`.

The worker reads these environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal frontend |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace |
| `TEMPORAL_TASK_QUEUE` | `did-finder-atlasopenmagic` | Task queue to poll |
| `SERVICEX_INTERNAL_ENDPOINT` | (required) | e.g. `http://servicex-app:8000/servicex/internal/transformation/` |
| `DID_FINDER_MAX_CONCURRENT` | `4` | Lookups run at once (the chart sets `didFinder.atlasopenmagic.maxConcurrentLookups`) |

## DID finder library version

`servicex-did-finder-lib` is a git dependency on the library's `temporal` branch
until that work is released. `poetry.lock` pins the commit, so pick up a newer
head of the branch with:

```bash
poetry update servicex-did-finder-lib
```
