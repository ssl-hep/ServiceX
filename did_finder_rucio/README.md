# Rucio ServiceX-DID-finder

![CI/CD](https://github.com/ssl-hep/ServiceX-DID-finder/workflows/CI/CD/badge.svg)
[![codecov](https://codecov.io/gh/ssl-hep/ServiceX_DID_Finder_Rucio/branch/master/graph/badge.svg?token=xLpoqlrdE3)](https://codecov.io/gh/ssl-hep/ServiceX_DID_Finder_Rucio)

For a given RUCIO DID finds optimal access paths.

## Overview

This service is intended to run as part of a [ServiceX](https://github.com/ssl-hep/ServiceX)
deployment. It receives Dataset Lookup requests, asks Rucio to resolve the
dataset and return the files that make it up, selects replicas, and passes the
files back to the ServiceX app for transformation.

It runs in one of two modes, sharing the same lookup code
(`rucio_did_finder.finder.find_files`):

* **Temporal** (`scripts/start_temporal_worker.sh`, `python -m rucio_did_finder.temporal_worker`):
  a `DIDFinderWorker` from the DID finder lib hosts the `lookup_dataset` activity on
  the `did-finder-rucio` task queue, scheduled by the ServiceX orchestrator. The Helm
  chart uses this mode when `orchestrator.enabled` is true.
* **Celery** (`scripts/start_celery_worker.sh`, the image's default entrypoint):
  listens on the `did_finder_rucio` RabbitMQ queue. Kept for one release while
  ServiceX moves to Temporal.

The Temporal worker reads these environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal frontend |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace |
| `TEMPORAL_TASK_QUEUE` | `did-finder-rucio` | Task queue to poll |
| `SERVICEX_INTERNAL_ENDPOINT` | (required) | e.g. `http://servicex-app:8000/servicex/internal/transformation/` |
| `DID_FINDER_MAX_CONCURRENT` | `4` | Lookups run at once (the chart sets `didFinder.rucio.maxConcurrentLookups`) |

Each file carries a `file_key` of its Rucio `scope:name`, which ServiceX uses to
dedupe files when a lookup is retried.

## DID finder library version

`servicex-did-finder-lib` is a git dependency on the library's `temporal` branch
until that work is released. `poetry.lock` pins the commit, so pick up a newer
head of the branch with:

```bash
poetry update servicex-did-finder-lib
```

## Build Image

Build the docker image as:

```bash
% docker build -t  sslhep/servicex-did-finder .
```

The latest image is also available on [dockerhub](https://cloud.docker.com/u/sslhep/repository/docker/sslhep/servicex-did-finder)

## Running

The service requires two volumes to be mounted in order to operate:

1. A valid x509 proxy certificate in `/etc/grid-security-ro`.
There is a script that usually gets run to copy the cert to a correctly permissioned
directory. The location of the cert can be overridden by setting the X509_USER_PROXY
environment variable.

2. Rucio config file in `/opt/rucio/etc/`

## Command Line Arguments

The server accepts the following arguments when it is launched

|Argument       |Description                                                                |Default   |
|---------------|---------------------------------------------------------------------------|----------|
|`--rabbit-uri` | A valid URI to the RabbitMQ Broker                                        | None     |

### Rucio Config

The service requires a custom `rucio.cfg` which contains the CERN account name
associated with the provided Certs. A template .cfg file is provided in this
repo's `config` directory. Ordinarily this would be constructed by the helm chart.

To get an optimal (usually closest) file replica, two environment variables have to be set: RUCIO_LATITUDE and RUCIO_LONGITUDE. This is normally done through helm chart values.

To run a standalone test against for example ATLAS rucio instance do:

```bash
setupATLAS
lsetup rucio
voms-proxy-init
pip install -r requirements.txt
python3 direct_test/test1.py
```
