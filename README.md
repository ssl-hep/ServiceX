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

### Step 0 - Preparation
ServiceX requires an installation of Kubernetes. If you have access to a 
cluster you can use that. Otherwise, you can enable a
single node kubernetes cluster on your desktop 
[using Docker-Desktop](https://www.docker.com/blog/kubernetes-is-now-available-in-docker-desktop-stable-channel/).

The service is published as a helm chart. You will need a version of helm. The
chart has been tested on Helm3
[installed on your desktop](https://helm.sh/docs/using_helm/).


### Step 1 - Deploy a Demo Version of ServiceX
ServiceX will use your CERN grid certificates to communicate with Rucio. In this
repo we've included a set of demo values that will just use a public xAOD file 
so you can try out ServiceX with minimal fuss.
```bash
% helm repo add ssl-hep https://ssl-hep.github.io/ssl-helm-charts/
% helm repo update
% helm install -g -f demo-values.yaml ssl-hep/servicex 
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
servicex-1579021789-code-gen-7cd998d5b6-nwtgv            1/1     Running   0          49m
servicex-1579021789-did-finder-7c5cbb4575-52wxf          1/1     Running   0          7m53s
servicex-1579021789-minio-78b55bfdf8-mbmmf               1/1     Running   0          49m
servicex-1579021789-preflight-b748b4dfd-qqt89            1/1     Running   4          49m
servicex-1579021789-rabbitmq-0                           1/1     Running   0          49m
servicex-1579021789-servicex-app-98779c79c-cvmqx         1/1     Running   3          49m
servicex-1579021789-x509-secrets-74f4bcc8bb-5kqvb        1/1     Running   0          49m
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
| code-gen | This service generates code from your [qastle](https://github.com/iris-hep/qastle/blob/master/README.md) selects|
| preflight | This service accepts the first ROOT file found by the DID-Finder and does a quick validation of your request to make sure the columns are valid. Only after passing this test do the transformer jobs get started |
| x509-secrets | This service uses your provided grid cert and credentials to obtain an X509 proxy from VOMs. This proxy is stored in the cluster as a secret that the DID finder and Transformers can mount to connect to resources on your behalf |

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
the transformation to complete and downloads the results. The notebook is 
found in the `examples` folder of this repo.

First create a python [virtualenv](https://virtualenv.pypa.io/en/latest/). Note that the notebooks
(and package requirements) are currently configured to work for Python 3.

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

You install the certs into the cluster as a global kubernetes secret. This is
easily done with the ServiceX Command Line Interface (cli).

1. Install the cli with `pip install servicex-cli`
2. When this completes you can copy the certs into the cluster with `servicex init`
By default, the script will pick up your grid certs from the `.globus` directory
in your home directory. You can override this with the `--cert-dir` command line
option. Also, the cli will create the secret in the `default` namespace. If you
are using a different namespace you can override this with the `--namespace` option.

## Optional Kafka Installation
ServiceX can deliver transformed datasets to an object store service (Minio) 
that is optionally installed with this helm chart. An alternative delivery
mechanism is streamed arrow tables using Kafka. Full instructions and sample
config files are in the [kafka](kafka) directory.

## Configuration
The following table lists the configurable parameters of the ServiceX chart and 
their default values. Note that you may wish to change some of the default 
parameters for the dependent [rabbitMQ](https://github.com/helm/charts/tree/master/stable/rabbitmq#configuration)
or [mino](https://github.com/helm/charts/tree/master/stable/minio#configuration)



| Parameter                            | Description                                      | Default                                                 |
| ------------------------------------ | ------------------------------------------------ | ------------------------------------------------------- |
| `app.image`                          | ServiceX_App image name                          | `sslhep/servicex_app`                                   |
| `app.tag`                            | ServiceX image tag                               | `latest`                                                |
| `app.pullPolicy`                     | ServiceX image pull policy                       | `IfNotPresent`                                          |
| `app.rabbitmq.retries`               | Number of times to retry connecting to RabbitMQ on startup | 12                                            |
| `app.rabbitmq.retry_interval`        | Number of seconds to wait between RabbitMQ retries on startup | 10                                         |
| `app.replicas`                       | Number of App pods to start. Experimental!       | 1                                                       |
| `app.auth`                           | Enable JWT Auth or allow unfettered access (Python boolean string) | `false`                             |
| `app.adminEmail`                     | Email for auto created admin user to manage new user workflow   | admin@example.com                        |
| `app.adminPassword`                  | Password for auto created admin user to manage new user workflow   | changeme                                 |
| `app.authTimeout`                    | How many seconds should the generated JWTs be valid for? | 21600 (six hours)                               |
| `app.ingress.enabled`                | Enable install of ingres                         | false                                                   |
| `app.ingress.host`                   | Hostname to associate ingress with               | uc.ssl-hep.org                                          |
| `app.ingress.defaultBackend`         | Name of a service to send requests to internal endpoints to | default-http-backend                         |
| `app.resources`                      | Pass in Kubernetes pod resource spec to deployment to change CPU and memory | { }                          |    
| `app.slackSigningSecret`             | Signing secret for Slack application             | -
| `app.newSignupWebhook`               | Slack webhook URL for new signups                | -
| `app.validateTransformerImage`       | Should docker image name be validated at DockerHub? | `true`                                               | 
| `didFinder.image`                    | DID Finder image name                            | `sslhep/servicex-did-finder`                            |
| `didFinder.tag`                      | DID Finder image tag                             | `latest`                                                |
| `didFinder.pullPolicy`               | DID Finder image pull policy                     | `IfNotPresent`                                          |
| `didFinder.site`                     | Tier 2 site that DID finder should prefer. If blank will just return a random replica from Rucio        |      |
| `didFinder.rucio_host`               | URL for Rucio service to use                     | `https://voatlasrucio-server-prod.cern.ch:443`          |
| `didFinder.auth _host`               | URL to obtain rucio authentication               | `https://voatlasrucio-auth-prod.cern.ch:443`            |
| `didFinder.threads`                  | Number of threads for pull replicas out of Rucio | 5
| `preflight.image`                    | Preflight image name                             | `sslhep/servicex-transformer`                           |
| `preflight.tag`                      | Preflight image tag                              | `latest`                                                |
| `preflight.pullPolicy`               | Preflight image pull policy                      | `IfNotPresent`                                          |
| `codeGen.enabled`                    | Enable deployment of code generator service?     | `true`                                                  |
| `codeGen.image`                      | Code Gen image name                              | `sslhep/servicex_code_gen_funcadl_xaod`                 |
| `codeGen.tag`                        | Code Gen image tag                               | `latest`                                                |
| `codeGen.pullPolicy`                 | Code Gen image pull policy                       | `IfNotPresent`                                          |
| `x509Secrets.image`                  | X509 Secret Service image name                   | `sslhep/x509-secrets`                                   |
| `x509Secrets.tag`                    | X509 Secret Service image tag                    | `latest`                                                |
| `x509Secrets.pullPolicy`             | X509 Secret Service image pull policy            | `IfNotPresent`                                          |
| `x509Secrets.vomsOrg`                | Which VOMS org to contact for proxy?             | `atlas`                                                 |
| `rbacEnabled`                        | Specify if rbac is enabled in your cluster	      | `true`
| `hostMount`                          | Optional path to mount in transformers as /data  | - 
| `gridAccount`                        | CERN User account name to access Rucio           | - 
| `rabbitmq.password`                  | Override the generated RabbitMQ password         | leftfoot1 |
| `objectstore.enabled`                | Deploy a minio object store with Servicex?       | true      |
| `objectstore.publicURL`              | What URL should the client use to download files? If set, this is given whether ingress is enabled or not  | nil |      |
| `postgres.enabled`                   | Deploy a postgres database into cluster? If not, we use a sqllite db | false  |
| `minio.accessKey`                    | Access key to log into minio                     | miniouser |
| `minio.accessKey`                    | Secret key to log into minio                     | leftfoot1 |
| `minio.ingress.enabled`              | Should minio chart deploy an ingress to the service? | false |
| `minio.ingress.hosts`                | List of hosts to associate with ingress controller | nil |
| `transformer.pullPolicy`             | Pull policy for transformer pods (Image name specified in REST Request) | IfNotPresent |
| `transformer.autoscalerEnabled`      | Set to True to enable the pod horizontal autoscaler for transformers |  False          |
| `elasticsearchLogging.enabled`       | Set to True to enable writing of reports to an external ElasticSearch system | False |
| `elasticsearchLogging.host`          | Hostname for external ElasticSearch server | |
| `elasticsearchLogging.port`          | Port for external ElasticSearch Server           | 9200 |
| `elasticsearchLogging.user`          | Username to connect to external ElasticSearch Server | |
| `elasticsearchLogging.password`      | Password to connect to external ElasticSearch Server | |


### Slack Integration

ServiceX can send notifications of new user registrations to the Slack channel of your choice and allow administrators to approve pending users directly from Slack. 
To set this up, complete the following steps before deploying ServiceX:

- Create a secure Slack channel in your workspace (suggested name: `#servicex-signups`), accessible only to developers or administrators of ServiceX. 
- Go to https://api.slack.com/apps and click "Create New App". Fill in ServiceX as the name and choose your workspace.
- Scroll down to the App Credentials section and find your Signing Secret. Copy this value and place it in your `values.yaml` file as `app.slackSigningSecret`.
- Scroll up to the feature list, click on Incoming Webhooks, and click the switch to turn them on.
- Click the Add New Webhook to Workspace button at the bottom, choose your signups channel, and click the Allow button.
- Copy the Webhook URL and store it in `values.yaml` under `app.newSignupWebhook`.
- After completing the rest of the configuration, deploy ServiceX.
- Go back to the [Slack App dashboard](https://api.slack.com/apps) and choose the app you created earlier. In the sidebar, click on Interactivity & Shortcuts under Features.
- Click the switch to turn Interactivity on. In the Request URL field, enter the base URL for the ServiceX API, followed by `/slack`, e.g. `http://rc1-xaod-servicex.uc.ssl-hep.org/slack`. Save your changes.
- You're all set! ServiceX will now send interactive Slack notifications to your signups channel whenever a new user registers.



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


### Production Deployment
We are still experimenting with various configurations for deploying a scaled-up
ServiceX. 

It's certainly helpful to beef up the RabbitMQ deployment:
```yaml
rabbitmq:
  resources:
     requests:
       memory: 256Mi
       cpu: 100m
  replicas: 3
```

> **Tip**: List all releases using `helm list`

### Uninstalling the Chart

To uninstall/delete the `my-release` deployment:

```bash
$ helm delete my-release
```

The command removes all the Kubernetes components associated with the chart and 
deletes the release.


## Contributing to ServiceX
ServiceX is a community effort. The architecture lends itself to orchestrating 
different types of workflows and generating different outputs. Fork us on 
github and make a contribution!

### Issues
Please submit issues for bugs and feature requests to this repo.

We manage project priorities with a [zenhub board](https://app.zenhub.com/workspaces/servicex-5caba4288d0ceb76ea94ae1f/board?repos=180217333,180236972,185614791,182823774,202592339)

### Join us on Slack
We coordinate effort on the [IRIS-HEP slack](http://iris-hep.slack.com).
Come join this intellectual hub.

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


## Acknowledgements
![](https://iris-hep.org/assets/logos/Iris-hep-5-just-graphic.png)
![](https://iris-hep.org/assets/images/nsf-logo-128.png)

This project is supported by National Science Foundation under Cooperative 
Agreement OAC-1836650. Any opinions, findings, conclusions or recommendations 
expressed in this material are those of the authors and do not necessarily 
reflect the views of the National Science Foundation.
