# ServiceX
ServiceX, a component of the IRIS-HEP DOMA group's iDDS, will be an
experiment-agnostic service to enable on-demand data delivery along the concepts
originally developed for ATLAS but specifically tailored for nearly-interactive,
high performance, array based and pythonic analyses context. It will provide
uniform backend interfaces to data storage services and  frontend
(client-facing) service endpoints for multiple different data formats and
organizational structures.  

It should be capable of retrieving and delivering
data from data lakes, as those systems and models evolve. It will depend on one
or more data management systems (eg. Rucio) to find and access the data. The
service will be capable of on-the-fly data transformations to enable data
delivery in a variety of different formats, including streams of ROOT data,
small ROOT files, HDF5, and Apache Arrow buffers as examples. In addition,
ServiceX will include pre-processing functionality for event data and
preparation for multiple clustering frameworks (e.g. such as Spark).  It will be
able to automatically unpack compressed formats, potentially including hardware
accelerated techniques, and can prefilter events so that only useful data is
transmitted to the user.

## Installing with Helm
The entire serviceX stack can be installed using the helm chart contained in 
this repo. It currently has not been deployed to a helm repo, so you will need
to checkout this repo and use the chart locally.

### TLDR;
```bash
% helm dependency build
% helm install servicex
```

### Introduction
This will install rabbitMQ, the DID Finder, the preflight check service, and the
flask REST service. 

### Installing the Chart
To install the chart with the release name `my-release`:

```bash
% helm dependency build
% helm install --name my-release servicex
```

The command deploys RabbitMQ on the Kubernetes cluster in the default 
configuration. The [configuration](###configuration) section lists the 
parameters that can be configured during installation.

### Using The Service
You can access the REST service on your desktop with 
```bash
kubectl port-forward <<app pod>> 5000:5000
```

Once you have exposed port 5000 of the REST app, you can use the included 
[postman](https://www.getpostman.com/products) collection to submit a 
transformation request, and check on the status of a running job.


> **Tip**: List all releases using `helm list`

### Uninstalling the Chart

To uninstall/delete the `my-release` deployment:

```bash
$ helm delete my-release
```

The command removes all the Kubernetes components associated with the chart and 
deletes the release.

### Grid Certification
The DID Finder will need to talk to CERN's Rucio service which requires grid
certificates and a passcode to unlock them. If you are a member of the ATLAS
experiment, you can follow these 
[helpful instructions](https://hep.pa.msu.edu/wiki/bin/view/ATLAS_Tier3/GridCert) 
on obtaining proper grid certificates.

The DID Finder service assumes that the certs are available `/etc/grid-certs` 
and that the passcode to unlock them can be found in a file called `secret.txt`
in the `/servicex` directory. 

This helm chart pulls these values out of `values.yaml` and generates a 
ConfigMap for the PEM files and a Secret for the passcode.

This works reliably, but may not be best practice for securing sensitive 
information. Suggestions are welcome.

### Debugging Tips
Microservice architectures can be difficult to test and debug. Here are some 
helpful hints to make this easier.

1. Instead of relying on the DID Finder to locate some particular datafile, you
can mount one of your local directories into the transformer pod and then 
instruct the DID Finder to always offer up the path to that file regardless of
the submitted DID. You can use the `hostMount` value to have a local directory
mounted into each transformer pod under `/data`. You can use the 
`didFinder.staticFile` value to instruct DID Finder to offer up a file from that
directory.
2. You can use port-forwarding to expose port 15672 from the RabbitMQ pod to 
your laptop and log into the Rabbit admin console using the username: `user` and
password `leftfoot1`. From here you can monitor the queues, purge old messages
and inject your own messages

## Configuration

The following table lists the configurable parameters of the ServiceX chart and 
their default values.

| Parameter                            | Description                                      | Default                                                 |
| ------------------------------------ | ------------------------------------------------ | ------------------------------------------------------- |
| `app.image`                          | ServiceX_App image name                          | `sslhep/servicex_app`                                   |
| `app.tag`                            | ServiceX image tag                               | `develop`                                               |
| `app.pullPolicy`                     | ServiceX image pull policy                       | `IfNotPresent`                                          |
| `didFinder.image`                    | DID Finder image name                            | `sslhep/servicex-did-finder`                            |
| `didFinder.tag`                      | DID Finder image tag                             | `rabbitmq`                                              |
| `didFinder.pullPolicy`               | DID Finder image pull policy                     | `IfNotPresent`                                          |
| `didFinder.staticFile`               | For debugging, DID Finder will always return this file for any DID. | - 
| `preflight.image`                    | Preflight image name                             | `sslhep/servicex-transformer`                           |
| `preflight.tag`                      | Preflight image tag                              | `rabbitmq`                                              |
| `preflight.pullPolicy`               | Preflight image pull policy                      | `IfNotPresent`                                          |
| `rbacEnabled`                        | Specify if rbac is enabled in your cluster	      | `true`
| `hostMount`                          | Optional path to mount in transformers as /data  | - 
| `gridPassword`                       | Passcode to unlock your grid PEM file            |  - 
| `usercert`                           | Copy of the contents of your `~/.globus/usercert.pem` file | - 
| `userkey`                            | Copy of the contents of your `~/.globus/userkey.pem` file | -
| `rabbitmq.password`                  | Override the generated RabbitMQ password         | leftfoot1 |
 


* [Documentation](https://ssl-hep.github.io/ServiceX/)
* [Kanban board](https://app.zenhub.com/workspaces/servicex-5caba4288d0ceb76ea94ae1f/board?repos=180217333)
* [Service frontend](https://servicex.slateci.net)