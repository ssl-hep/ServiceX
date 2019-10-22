# ServiceX
ServiceX, a component of the IRIS-HEP DOMA group's iDDS, is an
experiment-agnostic service to enable on-demand data delivery along the concepts
originally developed for ATLAS but specifically tailored for nearly-interactive,
high performance, array based and pythonic analyses context. It provides
uniform backend interfaces to data storage services and  frontend
(client-facing) service endpoints for multiple different data formats and
organizational structures.  

It is capable of retrieving and delivering data from data lakes, as those 
systems and models evolve. It depends on Rucio to find and access the data. The
service is capable of on-the-fly data transformations to enable data
delivery in a variety of different formats, including streams of ROOT data,
small ROOT files, HDF5, and Apache Arrow buffers as examples. In addition,
ServiceX includes pre-processing functionality for event data and
preparation for multiple clustering frameworks (e.g. such as Spark). 
Eventually, it will be able to automatically unpack compressed formats, 
potentially including hardware accelerated techniques, and can prefilter events 
so that only useful data is transmitted to the user.

## Try out ServiceX
The entire serviceX stack can be installed using the helm chart contained in 
this repo. The chart has been deployed to the ssl-hep helm repo. The default
values for the chart have been set up so you can run the service with a 
public xAOD file without any grid credentials. 

There is also an included Jupyter notebook for driving the system and getting
some simple plots back.

### Step 0 - Preperation
ServiceX requires an installation of Kubernetes. If you have access to a 
cluster you can use that. Otherwise, you can enable a
single node kubernetes cluster on your desktop 
[using Docker-Desktop](https://www.docker.com/blog/kubernetes-is-now-available-in-docker-desktop-stable-channel/).

The service is published as a helm chart. You will need a version of helm 
[installed on your desktop](https://helm.sh/docs/using_helm/).

Once installed you will need to initilize the connection between helm and your
cluster. 
```bash
% helm init --history-max 200
``` 


### Step 1 - Deploy a Demo Version of ServiceX
ServiceX will use your CERN grid certificates to communicate with Rucio. We've
set up a simplified deployment that will just use a public xAOD file so you 
try out ServiceX with minimal fuss.
```bash
% helm repo add ssl-hep https://ssl-hep.github.io/ssl-helm-charts/
% helm repo update
% helm install ssl-hep/servicex 
```

The notes at the end give you some helpful tips on interacting with the pods in 
your deployment. It takes about one minute for RabbitMQ to complete its 
initialization and all of the other pods are able to register and start up.
Note that it is normal for some pods to enter a "Crash Loop Backoff" during
this time.

You can check on the status of the deployment with the command
```bash
% kubectl get pod
```

Eventually your setup should resemble this:
```
NAME                                             READY   STATUS    RESTARTS   AGE
exegetical-mouse-did-finder-868484f5b5-8pwdk     1/1     Running   3          2m24s
exegetical-mouse-minio-57cbd595b5-77426          1/1     Running   0          2m24s
exegetical-mouse-preflight-64c5b6b647-5ctlb      1/1     Running   4          2m24s
exegetical-mouse-rabbitmq-0                      1/1     Running   0          2m23s
exegetical-mouse-servicex-app-6fdd5bf7b6-dcwwd   1/1     Running   3          2m24s
```

The name of your release will be different.


#### What are these Services?
The default values for the ServiceX helm chart deploy the following services:

|Service|Purpose|
|-------|-------|
| servicex-app | This is the REST service that receives your requests and manages interactions with the other services. It also uses the kubernetes API to launch transformer jobs |
| rabbitmq | This is a [popular queue messaging system](https://www.rabbitmq.com) it provides a transaction mechanism for distributing work to the asynchronous components of the service |
| minio | An [opensource implementation](https://min.io) of Amazon's S3 object store. It is not required for ServiceX, but makes it easy to deliver results from smaller transformations as downloadable files. |
| did-finder | This service accepts DIDs and consults Rucio to find replicas of the constituaent ROOT files. It sends these files back to the REST server so the transformers can access them |
| preflight | This service accepts the first ROOT file found by the DID-Finder and does a quick validation of your request to make sure the columns are valid. Only after passing this test do the transformer jobs get started |

### Step 2 - Forward Ports to Your Desktop
Kubernetes offers some sophisticated ways to expose deployed services for 
external connections. For this demo, we will just use the simplest possible way
expose the services to your desktop: port forwarding. 

We will need to expose port 5000 of the REST server so transform requests can be
submitted. We will also expose port 9000 of the Minio server so we can browse 
and download generated files.

The notes at the end of helm deployment provide some nice generic commands to do 
this. You can also look at the list of pods and then issue commands like this
to tell kubernetes to forward their ports. Here are examples based on the 
pod names shown above. Your pod names will be different:

```bash
% kubectl port-forward exegetical-mouse-servicex-app-6fdd5bf7b6-dcwwd 5000:5000
% kubectl port-forward exegetical-mouse-minio-57cbd595b5-77426 9000:9000
```

*Note* the port-forward command doesn't return when you run it. It blocks in 
the terminal so long as the port is being forwarded. You can stop it at any time
with ^C. You will need to enter each of these commands in different terminals 
since port forwarding will be needed during the demo.

### Step 3 Run the Jupyter Notebook
We have a notebook that submits a sample request to your serviceX, waits for 
the transformation to complete and downloads the results.

First create a python [virtualenv](https://virtualenv.pypa.io/en/latest/)

```bash
% virtualenv ~/.virtualenvs/servicex_demo
% source ~/.virtualenvs/servicex_demo/bin/activate
```

Now install the dependent python packages

```bash
% pip install -r examples/requirements.txt
```

Then you can start Jupyter server

```bash
% jupyter notebook
```

Once that launches it should open up a browser window for you. Vist the 
`examples` folder of this repo and open up the `ServiceXDemo` notebook.


## Next Steps
Now that you have tried out the demo, you will certainly want to take the 
training wheels off and run ServiceX against a real dataset.

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

## Configuration
The following table lists the configurable parameters of the ServiceX chart and 
their default values. Note that you may wish to change some of the default 
parameters for the dependent [rabbitMQ](https://github.com/helm/charts/tree/master/stable/rabbitmq#configuration)
or [mino](https://github.com/helm/charts/tree/master/stable/minio#configuration)



| Parameter                            | Description                                      | Default                                                 |
| ------------------------------------ | ------------------------------------------------ | ------------------------------------------------------- |
| `app.image`                          | ServiceX_App image name                          | `sslhep/servicex_app`                                   |
| `app.tag`                            | ServiceX image tag                               | `0.1`                                               |
| `app.pullPolicy`                     | ServiceX image pull policy                       | `IfNotPresent`                                          |
| `didFinder.image`                    | DID Finder image name                            | `sslhep/servicex-did-finder`                            |
| `didFinder.tag`                      | DID Finder image tag                             | `0.1`                                              |
| `didFinder.pullPolicy`               | DID Finder image pull policy                     | `IfNotPresent`                                          |
| `didFinder.staticFile`               | For debugging, DID Finder will always return this file for any DID. | - 
| `preflight.image`                    | Preflight image name                             | `sslhep/servicex-transformer`                           |
| `preflight.tag`                      | Preflight image tag                              | `0.1`                                              |
| `preflight.pullPolicy`               | Preflight image pull policy                      | `IfNotPresent`                                          |
| `rbacEnabled`                        | Specify if rbac is enabled in your cluster	      | `true`
| `hostMount`                          | Optional path to mount in transformers as /data  | - 
| `gridPassword`                       | Passcode to unlock your grid PEM file            |  - 
| `usercert`                           | Copy of the contents of your `~/.globus/usercert.pem` file | - 
| `userkey`                            | Copy of the contents of your `~/.globus/userkey.pem` file | -
| `rabbitmq.password`                  | Override the generated RabbitMQ password         | leftfoot1 |
| `objectstore.enabled`                | Deploy a minio object store with Servicex?       | true      |
| `minio.accessKey`                    | Access key to log into minio                     | miniouser |
| `minio.accessKey`                    | Secret key to log into minio                     | leftfoot1 |
| `transformer.pullPolicy`             | Pull policy for transformer pods (Image name specified in REST Request) | IfNotPresent |


### Installing the Chart
To install the chart with the release name `my-release` and your custom 
parameters in `my-values.yaml`:

```bash
% helm repo add ssl-hep https://ssl-hep.github.io/ssl-helm-charts/
% helm repo update
% helm install -f my-values.yaml --name my-release ssl-hep/servicex 
```

The command deploys RabbitMQ on the Kubernetes cluster in the default 
configuration. The [configuration](###configuration) section lists the 
parameters that can be configured during installation.

### Using The Service
You can access the REST service on your desktop with 
```bash
% kubectl port-forward <<app pod>> 5000:5000
```

You can access a minio browser with:
```bash
% kubectl port-forward <minio pod> 9000:9000
```
Log in to this as `miniouser`, password is `leftfoot1`

Once you have exposed port 5000 of the REST app, you can use the included 
[postman](https://www.getpostman.com/products) collection to submit a 
transformation request, and check on the status of a running job. You can 
import the collection from the [ServiceX REST App](https://raw.githubusercontent.com/ssl-hep/ServiceX_App/develop/ServiceXTest.postman_collection.json) repo


> **Tip**: List all releases using `helm list`

### Uninstalling the Chart

To uninstall/delete the `my-release` deployment:

```bash
$ helm delete my-release
```

The command removes all the Kubernetes components associated with the chart and 
deletes the release.


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



* [Documentation](https://ssl-hep.github.io/ServiceX/)
* [Kanban board](https://app.zenhub.com/workspaces/servicex-5caba4288d0ceb76ea94ae1f/board?repos=180217333)
* [Service frontend](https://servicex.slateci.net)