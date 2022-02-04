# Introduction to ServiceX Deployment

ServiceX is a multi-tenant service designed to be deployed on a Kubernetes
cluster. At present, each ServiceX instance is dedicated to a particular
experiment and file format (flat root file, ATLAS xAOD, and CMS MiniAOD). There
are centrally managed instances of the service running on
the University of Chicago's [Analysis Facility](https://af.uchicago.edu) at
[xAOD instance](https://xaod.servicex.af.uchicago.edu) and
[uproot/root instance](https://uproot-atlas.servicex.af.uchicago.edu/).

ServiceX is deployed using a [Helm](https://helm.sh/) chart.
The full list of configuration options can be found in the
[reference section](reference.md).

This introduction is aimed at those interested in learning how to deploy
ServiceX with minimal configuration.
For more advanced topics, such as making a
publicly accessible deployment suitable for multiple users,
see the [production deployment guide](production.md).

## Prerequisites

- A Kubernetes cluster running K8s version 1.16 or later.
Your account will need to have permission to:
  - Create a Service Account
  - Peform Rolebindings
- [Helm 3](https://helm.sh/docs/intro/install/) installed.
- Python 3.6+
- A valid set of CERN X509 certificates in the `~/.globus` directory.

If you don't have access to a cluster, you can enable a single node
Kubernetes cluster on your desktop
[using Docker-Desktop](https://www.docker.com/blog/kubernetes-is-now-available-in-docker-desktop-stable-channel/).

## Authenticating to the grid

Each ServiceX instance runs with a service account, authenticated against a
single CERN virtual org (ATLAS or CMS). The credentials for this account are
registered in a Kubernetes namespace as a secret that is mounted into the DID
finder and the transformer pods.

### Install the ServiceX CLI

You can use the ServiceX CLI tool to install your CERN X509 certs onto the
cluster. Install the CLI via

```
pip install servicex-cli
```

### Install your certificates

You can run the CLI to install your certs with the following command:

```
servicex --namespace <default> init --cert-dir ~/.globus 
```

By default, this will look for the certificates in your `~/.globus` directory.
You can pass another directory with the `--cert-dir` argument.
You will be prompted for the passphrase that secures your X509 private key.

The installed secrets can be used by any ServiceX instance deployed into the
given namespace.

You can delete them using the command:

```
servicex clear
```

## Deploying ServiceX

Let's get started with a minimal ServiceX deployment and then in later sections
we add configuration to activate more features.

### Obtain the latest ServiceX Helm chart

First, add the ServiceX Helm chart repo to your local Helm and then download
all of the subcharts:

```
helm repo add ssl-hep https://ssl-hep.github.io/ssl-helm-charts/
helm repo update
```

### Basic configuration

The Helm chart is configured using a `.yaml` file.
You have some initial choices to make:

- Is this deployment for ATLAS or CMS?
- Will it be used for xAOD, MiniAOD, or flat ROOT files?

With this in mind, create `values.yaml` and include:

```yaml
postgres:
  enabled: true
objectStore:
  publicURL: localhost:9000

gridAccount: <your CERN ID>

codeGen:
  # Choose one of the following images to include in your values.yaml:
  # For xAOD
  image: sslhep/servicex_code_gen_atlas_xaod

  # Or for flat ROOT files
  image: sslhep/servicex_code_gen_func_adl_uproot

  # Or for miniAOD
  image: sslhep/servicex_code_gen_config_file

preflight:
  # Choose one of the following images to include in your values.yaml:
  # For xAOD
  image: sslhep/servicex_func_adl_xaod_transformer

  # For miniAOD or flat ROOT files
  image: sslhep/servicex_func_adl_uproot_transformer

didFinder:
  # For ATLAS:
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

### Deploying the Helm chart

Deploy the chart to your cluster with

```
helm install -f values.yaml --version v1.0.0-rc.3 servicex ssl-hep/servicex
```

Initial deployment is typically rapid, with RabbitMQ requiring up to a minute to
complete its initialization. The `servicex` argument is used by helm as the release
name.  It is used to refer to the chart when deploying, insptacting, or deleting
the chart. After this all the pods of the new deployment
should be ready. You can check the status of the pods via

```
kubectl get pods
```

### Testing with port forwarding

In a production ServiceX deployment we will use an ingress controller to expose
the services to the internet. For this simple deployment we will use
`kubectl` commands to forward ports from services to your desktop.

Obtain a listing of the running pods with:

```
kubectl get pods
```

Now in a terminal window, expose the web service ports:

```
kubectl port-forward service/<helm release name>-servicex-app 5000:5000
```

In a separate window, enable access the Minio object store:

```
kubectl port-forward service/<helm release name>-minio 9000:9000
```

To check if the API server is running, you can run:

```bash
curl localhost:5000/servicex
```

This should output some JSON metadata for the deployment.

### Running a simple analysis

Check out the [quick start guide](../user/getting-started.md) for new users,
which contains some examples of basic requests you can make to ServiceX.

Select one which corresponds to the file type you chose for your deployment.
You can skip the sections on choosing an endpoint and obtaining credentials,
and use the following `servicex.yaml` file instead:

```yaml
api_endpoints:
  - endpoint: http://localhost:5000/
    type: <xaod | uproot | miniaod>
```

### Uninstalling the release

To uninstall/delete the `my-release` deployment:

```bash
helm delete my-release
```

The release name is the first position argument provided with the
`helm install` command. In the example above, the release name is `servicex`.

This command removes all the Kubernetes components associated with the chart and
deletes the release.

## Next steps

This demo version of ServiceX is functional, but limited - access requires
port forwarding, and there's no authentication system or HTTPS.

To learn how to deploy a more complete version of ServiceX with all of
these features, check out our [production deployment guide](production.md).
