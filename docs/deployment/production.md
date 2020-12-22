# ServiceX in production

This guide is aimed at those interested in making production ServiceX 
deployments that are publicly accessible and require authentication.

For a guide to making a simple deployment of ServiceX with no extra features, 
check out our [basic deployment guide](basic.md).

## Prerequisites
- A Kubernetes cluster running K8s version 1.16 or later. 
- [Helm 3](https://helm.sh/docs/intro/install/) installed.
- You've used the ServiceX CLI to install your grid certificates on 
your cluster (if not, see the basic guide).
- An initial `values.yaml` file for making working ServiceX deployments, 
such as the one in the basic guide.

## External access

It's easy to deploy a ServiceX instance with no external access, but this 
is of limited value. We will now update `values.yaml` to add external ingress.

### Adding an Ingress to the ServiceX app

Configure an Ingress resource for the ServiceX API server by adding the 
following section to your values file:
```yaml
app:
    ingress:
        enabled: true
        host: <domain name for your deployment>
```

The ServiceX API server will be located at a subdomain of the domain name 
given in `app.ingress.host`. 
The name of the subdomain will match the Helm release name 
(the first position argument provided with the `helm install` command),
so the full URL will be `<helm release name>.<app.ingress.host value>`.

For example, if your values file contains:
```yaml
app:
    ingress:
        enabled: true
        host: servicex.ssl-hep.org
```
and you deployed the helm chart with
```
helm install -f values.yaml --version v1.0.0-rc.3 my-release ssl-hep/servicex
```
then the instance's URL would be `my-release.servicex.ssl-hep.org`.

You should also make sure the host has a DNS A record pointing this 
subdomain at the external IP address of your ingress controller.

### Adding an Ingress to Minio
ServiceX stores files in a Minio object store which is deployed as a 
subchart. The Helm chart for Minio has it's own support for an Ingress,
which we can activate like so:

```yaml
minio:
  ingress:
    enabled: true
    hosts:
    - my-release-minio.servicex.ssl-hep.org
```

Unlike the ServiceX Ingress, the subchart doesn't know the name of our 
deployment, so you need to hardcode it in the Minio Ingress host
(this is a current limitation of the Minio chart). 
The value should be `<helm release name>-minio.<app.ingress.host value>`.

### Ingress at CERN k8s cluster
    For ingress to work at CERN, one needs at least two loadbalancers allowed for your project. 
    CERN documentation is [here.](https://clouddocs.web.cern.ch/networking/load_balancing.html#kubernetes-service-type-loadbalancer)
    Start by turning off the charts ingress.
```yaml
app:
  ingress:
    enabled: false
```

Create loadbalancer service like this:
```yaml
apiVersion: v1
kind: ServiceX
metadata:
  name: ServiceX-LB
  namespace: <your-namespace>
  labels:
    app: <appname>-servicex-app
spec:
  ports:
    - port: 80
      targetPort: 8000
      protocol: TCP
  selector:
    app: <appname>-servicex-app
  type: LoadBalancer
```
 Verify that you can access it using just IP, then create a DNS for it:
```
openstack loadbalancer set --description my-domain-name ServiceX-LB
ping my-domain-name.cern.ch
```

Once service is accessible from inside CERN, you may ask for the firewall to be open, process is described [here.](https://clouddocs.web.cern.ch/containers/tutorials/firewall.html#servicetype-loadbalancer)

## Configuring Ingress resources to use TLS
It's a good idea to enable TLS for both of these Ingress resources.
There are two ways to do this: you can either obtain certificates and
install the TLS Secrets manually, or you can use the 
[cert-manager](https://cert-manager.io/docs/) Kubernetes add-on to 
issue certificates and create the Secrets automatically.
Separate guides for both options are provided below.

Either way, the first step is to set `app.ingress.tls.enabled` to `true`.

### Without cert-manager
First, obtain a TLS certificate and private key for each Ingress 
(two pairs in total).
This can be done using a trusted Certificate Authority (CA), such as 
[Let's Encrypt](https://letsencrypt.org/).
Make sure that each certificate Common Name matches the hostname of the 
corresponding Ingress.

Once you have your certs, you can install them to your cluster as [TLS Secrets](https://kubernetes.io/docs/concepts/configuration/secret/#tls-secrets):

`kubectl create secret tls <secret_name> --cert=<cert path> --key=<key path>`

By default, the ServiceX chart looks for a Secret named 
`<helm release name>-app-tls`. You can specify a different name in your values 
using `app.ingress.tls.secretName`.

Your final values should look something like:
```yaml
app:
  ingress:
    enabled: true
    host: servicex.ssl-hep.org
    tls:
      enabled: true
      secretName: my-release-app-tls
```

Adding TLS to the Minio subchart is slightly different.
The configuration is as follows:
```yaml
minio:
  ingress:
    enabled: true
    annotations:
      kubernetes.io/ingress.class: nginx
    hosts:
    - my-release-minio.servicex.ssl-hep.org
    tls:
    - hosts:
      - my-release-minio.servicex.ssl-hep.org
      secretName: my-release-minio-tls
```
Remember to replace `my-release` and `servicex.ssl-hep.org` with your Helm release name and app ingress host, respectively. 
Here, you must specify a secret name; there is no default.

### With cert-manager
Alternately, you can let cert-manager handle the TLS certificates.
To use it, complete the following steps:
- [Install cert-manager](https://cert-manager.io/docs/installation/kubernetes/)
on your cluster if it's not already installed.
- Deploy one or more ClusterIssuers, or check that one is already present. 
The Let's Encrypt staging and production ClusterIssuers are recommended.
- In `values.yaml`, set `app.ingress.tls.clusterIssuer` to the name of the
ClusterIssuer you'd like to use (e.g. `letsencrypt-prod`).
Browsers will trust `letsencrypt-prod` automatically, but bear in mind that 
it's subject to [rate limits](https://letsencrypt.org/docs/rate-limits/),
so it's best to use `letsencrypt-staging` for development.

Your values should now look like:
```yaml
app:
  ingress:
    tls:
      enabled: true
      clusterIssuer: letsencrypt-prod
```

For more information, see the cert-manager [guide to securing nginx-ingress](https://cert-manager.io/docs/tutorials/acme/ingress).

To enable TLS for Minio, use the following configuration:
```yaml
minio:
  ingress:
    enabled: true
    annotations:
      kubernetes.io/ingress.class: nginx
      cert-manager.io/cluster-issuer: letsencrypt-prod
      acme.cert-manager.io/http01-edit-in-place: "true"
    hosts:
    - my-release-minio.servicex.ssl-hep.org
    tls:
    - hosts:
      - my-release-minio.servicex.ssl-hep.org
      secretName: my-release-minio-tls
```
Once again, remember to replace `my-release` and `servicex.ssl-hep.org` with 
your Helm release name and app ingress host, respectively.

## Securing the deployment with authentication
If you wish, you could deploy these values and have a ServiceX instance that
is not secured but is reachable via the public URL.
This is okay for a sneak peek, but not recommended for long-lived deployments, 
since your grid certs will be usable by anyone on the Internet.

To prevent this, ServiceX supports an authentication system which requires 
new users to create accounts with your ServiceX deployment by authenticating 
to Globus with the identity provider of their choice 
(such as CERN or their university).


### Setting up Globus Auth
Globus Auth requires your deployment to be served over HTTPS,
so make sure you have completed the TLS section above.

Visit [developers.globus.org](https://developers.globus.org) 
and select ___Register your app with Globus___. 
Create a project for ServiceX and within that project click on 
___Add new app___. The app name can be whatever you like.

The scopes should include:
```
openid
email
profile
```

The redirect URL will be your host followed by `/auth-callback`.
In the earlier example, the redirect would be
`https://my-release.servicex.ssl-hep.org/auth-callback`.
If you want to use port-forwarding, also include
`http://localhost:5000/auth-callback`.

Save the record.

Copy the Client ID and paste this into your `values.yaml`.
```yaml
app:
  globusClientID: <Client ID here>
```

Generate a Client Secret and paste this value into `values.yaml` as well:
```yaml
app:
  globusClientSecret: <Client Secret here>
```

Finally, you can enable authentication in `values.yaml`:
```yaml
app:
  auth: true
  adminEmail: <your email address>
```

The system works as follows:
- New users will be required to create accounts with their Globus logins. 
- New accounts will be pending, and cannot make requests until approved. 
- Accounts must be approved by a ServiceX admin.
- To bootstrap the initial admin account, you must set `app.adminEmail` 
to the email address associated with the administrator's Globus account.

### Approving new accounts from Slack
ServiceX can send notifications of new user registrations to the Slack channel 
of your choice and allow administrators to approve pending users directly from 
Slack. 
This is strongly recommended for convenience, as currently the only other way 
to approve accounts is to manually send HTTP requests to the API server via 
a tool like Postman or curl.

To set this up, complete the following steps **before deploying** ServiceX:

- Create a secure Slack channel in your workspace (suggested name: `#servicex-signups`), accessible only to developers or administrators of ServiceX. 
- Go to https://api.slack.com/apps and click **Create New App**. 
Fill in ServiceX as the name and choose your workspace. 
If you are going to make multiple ServiceX deployments, 
you may want a more descriptive name, such as "ServiceX xAOD".
- Scroll down to the App Credentials section and find your Signing Secret. 
Copy this value and place it in your values file as `app.slackSigningSecret`.
- Scroll up to the feature list, click on Incoming Webhooks, and click the switch to turn them on.
- Click the **Add New Webhook to Workspace** button at the bottom, choose your signups channel, and click the **Allow** button.
- Copy the Webhook URL and store it in your values under `app.newSignupWebhook`.
- After completing the rest of the configuration, deploy ServiceX.
- Go back to the [Slack App dashboard](https://api.slack.com/apps) and choose the app you created earlier. In the sidebar, click on Interactivity & Shortcuts under Features.
- Click the switch to turn Interactivity on. In the Request URL field, enter the base URL for the ServiceX API, followed by `/slack`, e.g. 
`https://my-release.servicex.ssl-hep.org/slack`. Save your changes.
- You're all set! ServiceX will now send interactive Slack notifications to your signups channel whenever a new user registers.

### Email Notifications
ServiceX can send email notifications to newly registered users via 
[Mailgun](https://www.mailgun.com/) once their access has been approxed by an 
administrator. To enable this, obtain a Mailgun API key and 
[verified domain](https://documentation.mailgun.com/en/latest/quickstart-sending.html#verify-your-domain) 
and set `app.mailgunApiKey` and `app.mailgunDomain` in your values file`.

## Scaling
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

## 
