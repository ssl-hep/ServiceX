# ServiceX Deployment Guide

ServiceX consists of a number of microservices. The entire ServiceX stack can be installed on a Kubernetes cluster using the Helm chart contained in 
this repository, which is published to the [ssl-hep helm repo](https://ssl-hep.github.io/ssl-helm-charts/).
The default values for the chart have been set up so you can run the service with a public xAOD file without any grid credentials. 

There is also an included Jupyter notebook for driving the system and getting
some simple plots back.

### Step 0 - Prerequisites
ServiceX requires an installation of Kubernetes. If you have access to a 
cluster, you can use that. 
Otherwise, you can enable a single node kubernetes cluster on your desktop 
[using Docker-Desktop](https://www.docker.com/blog/kubernetes-is-now-available-in-docker-desktop-stable-channel/).

The service is published as a Helm chart, so you may need to [install Helm](https://helm.sh/docs/intro/install/). Refer to the Helm documentation for instructions on [using Helm](https://helm.sh/docs/intro/using_helm/).

### Step 1 - Deploy a Demo Version of ServiceX
ServiceX will use your CERN grid certificates to communicate with Rucio. In this
repo we've included a set of demo values that will just use a public xAOD file 
so you can try out ServiceX with minimal fuss.
```bash
% helm repo add ssl-hep https://ssl-hep.github.io/ssl-helm-charts/
% helm repo update
% helm dependency update servicex
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
| `app.auth`                           | Enable authentication or allow unfettered access (Python boolean string) | `false`                         |
| `app.globusClientID`                 | Globus application Client ID                     | -                                                       |
| `app.globusClientSecret`             | Globus application Client Secret                 | -                                                       |
| `app.adminEmail`                     | Email address for initial admin user             | admin@example.com                                       |
| `app.tokenExpires`                   | Seconds until the ServiceX API tokens (JWT refresh tokens) expire | False (never)                          |
| `app.authExpires`                    | Seconds until the JWT access tokens expire       | 21600 (six hours)                                       |
| `app.ingress.enabled`                | Enable install of ingress                        | false                                                   |
| `app.ingress.host`                   | Hostname to associate ingress with               | servicex.ssl-hep.org                                    |
| `app.ingress.defaultBackend`         | Name of a service to send requests to internal endpoints to | default-http-backend                         |
| `app.ingress.tls.enabled`            | Enable TLS for ServiceX API Ingress resource     | false                                                   |
| `app.ingress.tls.secretName`         | Name of TLS Secret used for ServiceX API server  | `{{.Release.Name}}-app-tls`                             |
| `app.ingress.tls.clusterIssuer`      | Specify a ClusterIssuer if using cert-manager    | -                                                       |
| `app.resources`                      | Pass in Kubernetes pod resource spec to deployment to change CPU and memory | { }                          |    
| `app.slackSigningSecret`             | Signing secret for Slack application             | -
| `app.newSignupWebhook`               | Slack webhook URL for new signups                | -
| `app.mailgunApiKey`                  | API key to send Mailgun emails to newly approved users | -
| `app.mailgunDomain`                  | Sender domain for emails (should be verified through Mailgun) | -
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
| `transformer.autoscalerEnabled`      | Set to True to enable the pod horizontal autoscaler for transformers |  True        |
| `transformer.cpuLimit`               | Set CPU resource limit for pod in number of cores | 1 |
| `transformer.cpuScaleThreshold`      | Set CPU percentage threshold for pod scaling | 30 |
| `transformer.defaultTransformerImage` | Default image for the transformers - must match the codeGen | 'sslhep/servicex_func_adl_xaod_transformer:1.0.0-RC.3' | 
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
- Click the switch to turn Interactivity on. In the Request URL field, enter the base URL for the ServiceX API, followed by `/slack`, e.g. `https://xaod.servicex.ssl-hep.org/slack`. Save your changes.
- You're all set! ServiceX will now send interactive Slack notifications to your signups channel whenever a new user registers.


### Email Notifications

ServiceX can send email notifications to newly registered users via [Mailgun](https://www.mailgun.com/) once their access has been approxed by an administrator. To enable this, obtain a Mailgun API key and [verified domain](https://documentation.mailgun.com/en/latest/quickstart-sending.html#verify-your-domain) and set `app.mailgunApiKey` and `app.mailgunDomain` in your `values.yaml`.


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
