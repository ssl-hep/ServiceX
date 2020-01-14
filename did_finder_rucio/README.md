# ServiceX-DID-finder

For a given RUCIO DID and client site finds optimal access paths.

## Build Image
Build the docker image as:
```bash
% docker build -t  sslhep/servicex-did-finder .
```

The latest image is also available on [dockerhub](https://cloud.docker.com/u/sslhep/repository/docker/sslhep/servicex-did-finder
)

## Running
The service and the x509 proxy require several files and folders to be mounted
in the running container:
* `/etc/grid-security-ro/x509up`: File with valid X509 Proxy

### Rucio Config
The service requires a custom `rucio.cfg` which contains the CERN account name
associated with the provided Certs. A template .cfg file is provided in this
repos `config` directory. Copy this file as `config/rucio.cfg` and update the 
`account` property. 

### Docker Command Line
You will need an X509 proxy avaiable as a mountable volume. The X509 Secret
container can do using your credentials and cert:
```bash
docker run --rm \
    --mount type=bind,source=$HOME/.globus,readonly,target=/etc/grid-certs \
    --mount type=bind,source="$(pwd)"/secrets/secrets.txt,target=/servicex/secrets.txt \
    --mount type=volume,source=x509,target=/etc/grid-security \
    --name=x509-secrets sslhep/x509-secrets:latest
```

To start docker container: 
```bash
docker run --rm -it \
    --mount type=volume,source=x509,target=/etc/grid-security-ro \
    --mount type=bind,source="$(pwd)"/config/rucio.cfg,target=/opt/rucio/etc/rucio.cfg \
    --mount type=bind,source="$(pwd)"/,target=/code \
    --name=did-finder sslhep/servicex-did-finder:develop 
```

After the container is started you can attach to it and start using the rucio commands:

```bash
% docker exec -it did-finder rucio ping 
```

### Reactive DID Finder
Included in this image is a command line script for retrieving a list of XCached
root files based on a list of DIDs. This script uses python3 which is not the 
default python environment for the rucio docker image. In order to execute the
script you have to enable the python3 Software Collection

```bash
%  docker exec -it did-finder scl enable rh-python36 bash
```

Inside this shell you can launch the cli did finder
```bash
% env PYTHONPATH=./did_finder python scripts/did_finder.py [list of DIDs]
```

Arguments to this script are:
* `--staticfile` _path to a test file_ - This allows you to use did_finder to 
drive a test process. It will generate output, but will only have a record to 
a single file that you specify. This could be a local ROOT file and allow you 
to avoid needing a grid cert since it never talks to Rucio
* `--site` _XCache Site_ - If provided, this site is used to locate appropriate replicas. 
Defaults to None
