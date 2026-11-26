# ServiceX_DID_finder_CERNOpenData
 Access datasets for ServiceX from CERN Open Data Portal.

## Finding datasets

The [Cern Open Data Portal](http://opendata.cern.ch/) is CERN's portal to all of its open data. As of this writing, that were 1000's of datasets, in all sorts of formats. Some number of the formats are understood by `ServiceX`: flat ROOT files from all experiments and CMS Run 1 AOD files.

Use the search bar to find a dataset - for example this [CMS dataset](http://opendata.cern.ch/record/1507) of simulated Higgs to 4 lepton dataset (H → ZZ → ℓℓℓℓ).

On the web page you can quickly see what type of output supplied by looking at the file list below. You'll have to use some context information to know what kind of ROOT files these are: these are CMS Run 1 AOD files. As such, you'll also have to use the proper ServiceX backend to process these files.

Once you've figured this part out, you can specify the dataset with a DID: `cernopendata://1507`. The finder will translate the `1507` into the list of files that will be fed to ServiceX transformers as long as this DID finder is running inside the transformer.

## Running

This DID finder runs as a Temporal worker, deployed by the ServiceX Helm chart
(`helm/servicex/templates/did-finder-cernopendata/deployment.yaml`). The image's entrypoint,
`scripts/start_temporal_worker.sh`, runs `python -m did_finder_cernopendata.temporal_worker`: a
`DIDFinderWorker` from the DID finder lib hosts the `lookup_dataset` activity on the
`did-finder-cernopendata` task queue, scheduled by the ServiceX orchestrator. The lookup
itself is `did_finder_cernopendata.finder.find_files`.

The worker reads these environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal frontend |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace |
| `TEMPORAL_TASK_QUEUE` | `did-finder-cernopendata` | Task queue to poll |
| `SERVICEX_INTERNAL_ENDPOINT` | (required) | e.g. `http://servicex-app:8000/servicex/internal/transformation/` |
| `DID_FINDER_MAX_CONCURRENT` | `4` | Lookups run at once (the chart sets `didFinder.CERNOpenData.maxConcurrentLookups`) |

## DID finder library version

`servicex-did-finder-lib` is a git dependency on the library's `temporal` branch
until that work is released. `poetry.lock` pins the commit, so pick up a newer
head of the branch with:

```bash
poetry update servicex-did-finder-lib
```
