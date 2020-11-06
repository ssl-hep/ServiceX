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
following section to your `values.yaml`:
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
helm install -f values.yaml --version v1.0.0-rc.3 xaod ssl-hep/servicex
```
then the instance's URL would be `xaod.servicex.ssl-hep.org`.

You should also make sure the host has a DNS A record pointing this 
subdomain at the external IP address of your ingress controller.

### Adding an Ingress to Minio
ServiceX stores files in a Minio object store which is deployed as a 
subchart. The helm chart for Minio has it's own support for an Ingress,
which we can activate like so:

```yaml
minio:
  ingress:
    enabled: true
    hosts:
    - xaod-minio.servicex.ssl-hep.org
```

Unlike the ServiceX Ingress, the subchart doesn't know the 
name of our deployment, so you need to correctly set the deployment name in 
the Minio Ingress address. It should be set to 
`<helm release name>-minio.<app.ingress.host value>`.

## Securing the deployment
If you wish, you could deploy these values and have a ServiceX instance that
is not secured but is reachable via the public URL.
This is okay for a sneak peek, but not recommended for long-lived deployments, 
since your grid certs will be usable by anyone on the Internet.

To prevent this, ServiceX supports an authentication system which requires 
new users to create accounts with your ServiceX deployment by authenticating 
to Globus with the identity provider of their choice 
(such as CERN or their university).

### Obtain a TLS Certificate
Globus Auth requires your deployment to be served over HTTPS.
To obtain a TLS certificate, complete the following steps:

- Install the [cert-manager](https://cert-manager.io/docs/) Kubernetes add-on.
- Deploy one or more ClusterIssuers.
The Let's Encrypt staging and production ClusterIssuers are recommended.
- In `values.yaml`, set `app.ingress.clusterIssuer` to the name of the
ClusterIssuer you'd like to use. The default value is `letsencrypt-prod`.
Bear in mind that this is subject to
[rate limits](https://letsencrypt.org/docs/rate-limits/),
so it's best to use `letsencrypt-staging` for development.

For more information, see the cert-manager [guide to securing nginx-ingress](https://cert-manager.io/docs/tutorials/acme/ingress).

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
Remember to replace `xaod` and `servicex.ssl-hep.org` with your Helm release 
name and app ingress host, respectively.

### Setting up Globus Auth
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
`https://xaod.servicex.ssl-hep.org/auth-callback`.
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
- Go to https://api.slack.com/apps and click **Create New App**. Fill in ServiceX as the name and choose your workspace. If you are going to make multiple ServiceX deployments, 
you may want a more descriptive name, such as "ServiceX xAOD".
- Scroll down to the App Credentials section and find your Signing Secret. Copy this value and place it in your `values.yaml` file as `app.slackSigningSecret`.
- Scroll up to the feature list, click on Incoming Webhooks, and click the switch to turn them on.
- Click the **Add New Webhook to Workspace** button at the bottom, choose your signups channel, and click the **Allow** button.
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