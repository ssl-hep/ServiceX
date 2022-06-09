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

When the pod starts up, the ServiceX container creates a request directory in the shared volume at /servicex/output/{request_id}. It then copies two scripts to /servicex/output/scripts directory for access by the Transformer container: proxy_exporter.sh in the event the transformer needs a proxy, and watch.sh which is the main bash script run by the transformer container. Eventually, these scripts should be moved to a common code generator library.

The ServiceX container receives the request from the DID Finder, and then writes a JSON in the request directory with the transformation request information. The code then watches the request directory for the creation of any files. When a file gets created in the shared directory, it is added to a queue for uploading to ServiceX.

The ServiceX container looks for a *.log file in the request directory. Currently, it uses the on_modified event to look for errors and for event counting.


### Transformer Container

The transformer container needs a code that takes two inputs: the file-path passed from the DID Finder and the shared volume path to write outputs.

The transformer container acutally executes a bash script placed in scripts/watch.sh. This scripts waits for JSON files to be created in the request directory and then submits the transformer given the file-path and shared volume. 

## Repository Dependencies

### [ServiceX_App](https://github.com/ssl-hep/ServiceX_App/tree/sidecar)

Main change is the pod configuration in transform_mngr.py

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




