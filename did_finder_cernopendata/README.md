# ServiceX_DID_finder_CERNOpenData
 Access datasets for ServiceX from CERN Open Data Portal.

## Finding datasets

The [Cern Open Data Portal](http://opendata.cern.ch/) is CERN's portal to all of its open data. As of this writing, that were 1000's of datasets, in all sorts of formats. Some number of the formats are understood by `ServiceX`: flat ROOT files from all experiments and CMS Run 1 AOD files.

Use the search bar to find a dataset - for example this [CMS dataset](http://opendata.cern.ch/record/1507) of simulated Higgs to 4 lepton dataset (H → ZZ → ℓℓℓℓ).

On the web page you can quickly see what type of output supplied by looking at the file list below. You'll have to use some context information to know what kind of ROOT files these are: these are CMS Run 1 AOD files. As such, you'll also have to use the proper ServiceX backend to process these files.

Once you've figured this part out, you can specify the dataset with a DID: `cernopendata://1507`. The finder will translate the `1507` into the list of files that will be fed to ServiceX transformers as long as this DID finder is running inside the transformer.

## Deploying the DID Finder

You'll need to create a k8 deployment file in order to run this DID finder. Here is a (tested) sample, built to be part of the `ServiceX` distribution:

```yaml
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-did-finder-cernopendata
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {{ .Release.Name }}-did-finder-cernopendata
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}-did-finder-cernopendata
    spec:
      containers:
      - name: {{ .Release.Name }}-did-finder-cernopendata
        image: {{ .Values.didFinderCERNOpenData.image }}:{{ .Values.didFinderCERNOpenData.tag }}
        imagePullPolicy: {{ .Values.didFinderCERNOpenData.pullPolicy }}
        env:
          - name: INSTANCE_NAME
            value: {{ .Release.Name }}
        args:
          - --rabbit-uri
          - amqp://user:{{ .Values.rabbitmq.auth.password }}@{{ .Release.Name }}-rabbitmq:5672
```

The last argument to `--rabbit-uri` is perhaps the most crucial - it defines the rabbit queue this DID finder listens on.
