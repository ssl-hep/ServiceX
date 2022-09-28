# ServiceX Sidecar Transformer

## Motivation

The ServiceX sidecar transformer is designed to separate the python dependency of the ServiceX code from the transformer code. 

## Overview

The transformer now runs as two containers:
- the ServiceX container
- the transformer container

The containers share a common volume with which they interact (by default: /servicex/output).

### ServiceX Container
 
The ServiceX container utilizes the python module, [watchdog](https://pypi.org/project/watchdog/), and the ServiceX python library.

When the pod starts up, the ServiceX container creates a request directory in the shared volume at `/servicex/output/{request_id}`. It then copies two scripts to `/servicex/output/scripts` directory for access by the Transformer container: proxy_exporter.sh in the event the transformer needs a proxy, and watch.sh which is the main bash script run by the transformer container. These scripts can be found in the scripts directory within this repository. 

The ServiceX container receives the request from the DID Finder, and then writes a JSON in the request directory with the transformation request information. The code then watches the request directory for the creation of any files within the request directory. When a file gets created in the shared directory, it is added to a python FIFO queue for uploading to ServiceX.

The ServiceX container also looks for a *.log file in the request directory. Currently, it uses the on_modified event to look for errors and for event counting.


### Transformer Container

The transformer container needs a code that takes two inputs: the file-path passed from the DID Finder and the shared volume path to write outputs.

The transformer container executes a bash script found in scripts/watch.sh. This scripts waits for JSON files to be created in the request directory and then submits the transformer given the file-path and shared volume. The executable the script passes is currently stored as variables in the ServiceX [configmap](https://github.com/ssl-hep/ServiceX/blob/feb6af0d4a0f592bc52d598ae9bca1ab0e62cf10/servicex/templates/app/configmap.yaml#L101). Also, see below.

## Repository Dependencies

### [ServiceX_App](https://github.com/ssl-hep/ServiceX_App/tree/sidecar)

Within the Servicex_App, changes were made within transform_mngr.py to the [create_job_object](https://github.com/ssl-hep/ServiceX_App/blob/d41080a99c7b1559ed34194cde83224a27af95d5/servicex/transformer_manager.py#L57) function. An additional volume was added to the transformer container and the executables were updated for when each container runs.

### [ServiceX](https://github.com/ssl-hep/ServiceX/tree/sidecar)

This branch commits additional variables in templates/app/configmap.yaml to be used. Here is an example of the values.yaml for a deployment of the [yt/girder transformer](https://github.com/pondd-project/ServiceX_yt_Transformer/tree/sidecar):


```
transformer:
...
  defaultTransformerImage: sslhep/servicex_sidecar_transformer
  defaultTransformerTag: main
  scienceImage: pondd/servicex_yt_transformer:sidecar
  language: python
  exec: transform_data.py
  outputDir: /servicex/output
```




