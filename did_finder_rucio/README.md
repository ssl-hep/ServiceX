# Rucio ServiceX-DID-finder

![CI/CD](https://github.com/ssl-hep/ServiceX-DID-finder/workflows/CI/CD/badge.svg)
[![codecov](https://codecov.io/gh/ssl-hep/ServiceX-DID-finder/branch/master/graph/badge.svg)](https://codecov.io/gh/ssl-hep/ServiceX-DID-finder)

For a given RUCIO DID and client site finds optimal access paths.

## Overview

This service is intended to run as part of a [ServiceX](https://github.com/ssl-hep/ServiceX)
deployment. In that role it listens for Dataset Lookup requests on the
`rucio_did_requests` RabbitMQ queue. Upon receipt, it asks Rucio to resolve the
dataset and return the files that make it up. These files are bundled up into
1,000 file chunks and sent to Rucio's replica client to find available copies
on the grid. As these responses come back, the server selects a replica and
passes it back to the ServiceX app to request transformation.

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
| `--site`      | Site to pass in to Rucio as a `client_location` property                  | None     |
| `--prefix`    | A string to prepend on resulting file names. Useful to add xCache to URLs | ' '      |
| `--threads`   | Number of threads to launch for retrieving replicas from Rucio            |  10      |

### Rucio Config

The service requires a custom `rucio.cfg` which contains the CERN account name
associated with the provided Certs. A template .cfg file is provided in this
repo's `config` directory. Ordinarily this would be constructed by the helm chart.
