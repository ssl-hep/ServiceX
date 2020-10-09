# Deploy ServiceX
ServiceX is a multi-tenant service designed to be deployed on a Kubernetes
cluster. At present, each ServiceX instance is dedicated to a particular
experiment and file format (flat root file, ATLAS xAOD, and CMS MiniAOD). There
are centrally managed instances of the service running on 
the University of Chicago's River cluster, 
[xaod.servicex.ssl-hep.org](https://xaod.servicex.ssl-hep.org) and 
[uproot.servicex.ssl-hep.org](https://uproot.servicex.ssl-hep.org). 

If you have access to a Kubernetes cluster and wish to deploy one or more 
instances of ServiceX, this guide is for you.

## Prerequisites
- ServiceX has been tested on Kubernetes version 1.16 and should work on later
versions. 
- Your account will need to have permission to:
    * Create a Service Account
    * Peform Rolebindings 

- You need to have [helm3](https://helm.sh/docs/intro/install/) installed.
- You will need a valid set CERN certificates 


## Authenticating Against CERN Virtual Org
Each ServiceX instance runs with a service account, authenticated against a 
single CERN virtual org (ATLAS or CMS). The credentials for this account are
registered in a Kubernetes namespace as a secret that is mounted into the DID
finder and the transformer pods.

Your CERN X509 certs are installed into the cluster using a command line 
application.

### Prerequisites
- Python 3.6 or higher
- X509 certs for the service account (assumed to be in ~/.globus)
Install the serviceX cli via
```
pip install servicex-cli==1.0.0rc2 
```

### Install Your Certs
Run the serviceX cli
```
servicex init --cert-dir ~/.globus --namespace <<default>>
```
It will prompt you for the passphrase that secures your X509 private key. 

The installed secrets can be used by any serviceX instance deployed into that
namespace.

You can delete the certs by the command:
```
servicex clear
```

## Deploy a Minimal ServiceX
Let's get started with a minimal serviceX deployment and then in later sections
we add configuration to activate more features.

### Obtain the Latest ServiceX Helm Chart
First we add the ServiceX helm chart repo to your local helm and then download
all of the subcharts:
```
helm repo add ssl-hep https://ssl-hep.github.io/ssl-helm-charts/
helm repo update
helm dependency update servicex
``` 

### Edit a Basic Values.yaml
The helm chart is controlled by a yaml file.
You have some initial choices to make:
* Is this deployment for ATLAS or CMS?
* Will it be used for xAOD, MiniAOD, or flat ROOT files?
 
With this in mind, create `values.yaml` and include:
```yaml
postgres:
    enabled: true
objectStore:
  publicURL: localhost:9000

gridAccount: <<your CERN ID>>

codeGen:
  # Choose one of the following images to include in your values.yaml:
  # For xAOD
  image: sslhep/servicex_code_gen_func_adl_xaod

  # Or for flat root files
  image: sslhep/servicex_code_gen_func_adl_uproot

  # Or for miniAOD
  image: sslhep/servicex_code_gen_config_file


preflight:
  # Choose one of the following images to include in your values.yaml:
  # For xAOD
  image: sslhep/servicex_func_adl_xaod_transformer

  # For flat root files or miniAOD
  image: sslhep/servicex_func_adl_uproot_transformer

didFinder:
  # For ATLAS Use these:
  rucio_host: https://voatlasrucio-server-prod.cern.ch:443
  auth_host: https://voatlasrucio-auth-prod.cern.ch:443

  # For CMS:
  rucio_host: http://cmsrucio-int.cern.ch
  auth_host: https://cmsrucio-auth-int.cern.ch

x509Secrets:
  # For ATLAS
  vomsOrg: atlas

  # For CMS:
  vomsOrg: cms
```

### Deploy the Helm Chart
Deploy the chart to your cluster with 
```
helm install -f values.yaml --version v1.0.0-rc.2 servicex ssl-hep/servicex
```

Initial deployment is typically rapid, with RabbitMQ requiring up to a minute to
complete its initialization. After this all the pods of the new deployment 
should be ready. If you check the status of the pods via

```
kubectl get pod
```

### Testing With Port Forwarding
In a production ServiceX deployment we will use an ingress controller to expose
the services to the internet. For this simple deployment we will use
kubectl commands to forward ports from services to your desktop.

Obtain a listing of the running pods with:
```
kubectl get pod
```

Now in a terminal window, expose the web service ports:
```
kubectl port-forward <<servicex app pod name>> 5000:5000
```

We also need to access the minio object store:
```
kubectl port-forward <<servicex minio pod name>> 9000:9000
```

### Run an Example Analysis


## Add External Ingress and Authentication
Having a ServiceX instance with no external access is easy to set up, but of 
limited value. We will now update values.yaml to open up an external ingress
and configure Globus auth.

### Obtain a TLS Certificate
Globus Auth requires your deployment to be served over HTTPS.
To obtain a TLS certificate, complete the following steps:
- Install the [cert-manager](https://cert-manager.io/docs/) Kubernetes add-on.
- Deploy one or more ClusterIssuers.
The Let's Encrypt staging and production ClusterIssuers are recommended.
- In `values.yaml`, set `app.ingress.clusterIssuer` to the name of the
ClusterIssuer you'd like to use. The default value is `letsencrypt-staging`.
Bear in mind that this is subject to
[rate limits](https://letsencrypt.org/docs/rate-limits/),
so it's best to use `letsencrypt-staging` for development).

For more information, see the cert-manager [guide to securing nginx-ingress](https://cert-manager.io/docs/tutorials/acme/ingress).

### Define the Ingress Host
The URL for your deployed ServiceX is a combination of the name of the helm 
deployment (the argument provided with the `helm install` command and the 
`ingress.host` setting in your values.yaml file. For example if your values file
contains:

```yaml
app:
    ingress:
        enabled: true
        host: servicex.ssl-hep.org
        clusterIssuer: letsencrypt-staging
```

And you deployed the helm chart with
```
helm install -f values.yaml --version v1.0.0-rc.2 xaod ssl-hep/servicex
```
Then the instance's URL would be `https://xaod.servicex.ssl-hep.org`

You should also make sure the host has a DNS A record pointing this
(sub)domain at the external IP address of your ingress controller.

### Obtain Globus Auth Credentials
Visit [developers.globus.org](https://developers.globus.org) and select 
_Register your app with Globus_.  Create a project for ServiceX and within 
that project _Add a new App_.

The App name can be whatever you like.

The scopes should include:
```
openid
email
profile
```

Note the Client ID and paste this into your `values.yaml` as
```yaml
app:
  globusClientID: << client Id here>> 
```

Generate a client secret and paste this value into:
```yaml
app:
  globusClientSecret: << client secret here>> 
```

The redirect URL will be your host followed by `/auth-callback`.
In the earlier example, the redirect would be
`https://xaod.servicex.ssl-hep.org/auth-callback`.
If you want to use port-forwarding, also include
`http://localhost:5000/auth-callback`. 

Save the record.

### Set the Minio Ingress
Resulting files are stored in a minio object store which is deployed as a 
subchart. The helm chart for Minio has it's own support for an ingress. We
can activate it. Unlike the ServiceX ingress, the subchart doesn't know the 
name of our deployment, so you need to correctly set the deployment name in 
the minio ingress address. 
```yaml
minio:
  ingress:
    enabled: false
    hosts:
    - "xaod-minio.servicex.ssl-hep.org"
```

TLS can also be enabled for Minio. To do so using cert-manager and the 
Let's Encrypt ClusterIssuer, use the following configuration:
```yaml
minio:
  ingress:
    enabled: true
    annotations:
      kubernetes.io/ingress.class: nginx
      cert-manager.io/cluster-issuer: letsencrypt-prod
      acme.cert-manager.io/http01-edit-in-place: "true"
    hosts:
    - xaod-minio.servicex.ssl-hep.org
    tls:
    - hosts:
      - xaod-minio.servicex.ssl-hep.org
      secretName: xaod-minio-tls
```

### Sneak a Peek
If you wish, you could deploy these values and have a ServiceX instance that
is not secured but is reachable via the public URL.

### Secure the Deployment
You can enable authentication by setting `app.auth` to true. This will require
new users to create accounts with their globus logins. New accounts will be 
marked as pending. An Admin has to approve these new accounts. To bootstrap
the process and get an admin account registered with the system, you must 
set `app.adminEmail` to the email address associated with the admininstrator's
Globus Account.

### Approve new Accounts Via Slack
ServiceX can send notifications of new user registrations to the Slack channel 
of your choice and allow administrators to approve pending users directly from 
Slack. 
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
ServiceX can send email notifications to newly registered users via 
[Mailgun](https://www.mailgun.com/) once their access has been approxed by an 
administrator. To enable this, obtain a Mailgun API key and 
[verified domain](https://documentation.mailgun.com/en/latest/quickstart-sending.html#verify-your-domain) 
and set `app.mailgunApiKey` and `app.mailgunDomain` in your `values.yaml`.
