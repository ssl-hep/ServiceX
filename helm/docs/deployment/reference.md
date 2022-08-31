# ServiceX Helm Chart Reference

The following table lists the configurable parameters of the ServiceX chart and
their default values. Note that you may also wish to change some of the default
parameters for the [rabbitMQ](https://github.com/bitnami/charts/tree/master/bitnami/rabbitmq) or [minio](https://github.com/minio/charts) subcharts.

| Parameter                            | Description                                      | Default                                                 |
| ------------------------------------ | ------------------------------------------------ | ------------------------------------------------------- |
| `secrets`                            | Name of a secret deployed into the cluster. Must follow example_secrets.yaml | -        |
| `app.image`                          | ServiceX_App image name                          | `sslhep/servicex_app`                                   |
| `app.tag`                            | ServiceX image tag                               | `latest`                                                |
| `app.logLevel`                       | Logging level for ServiceX web app (uses standard unix levels)               | `WARNING`                                                |
| `app.pullPolicy`                     | ServiceX image pull policy                       | `Always`                                          |
| `app.checksImage`                    | ServiceX init container image for checks         | `ncsa/checks:latest`                                    |
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
| `app.ingress.class`                  | Class to be set in `kubernetes.io/ingress.class` annotation | nginx                                        |
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
| `app.defaultDIDFinderScheme`         | DID Finder scheme if none provided in request. If left blank, template will attempt to guess.    | -                                                 |
| `app.validateTransformerImage`       | Should docker image name be validated at DockerHub? | `true`                                               |
| `didFinder.rucio.enabled`            | Should we deploy the Rucio DID Finder?           | `true`                                              |
| `didFinder.rucio.image`              | Rucio DID Finder image name                            | `sslhep/servicex-did-finder`                            |
| `didFinder.rucio.tag`                | Rucio DID Finder image tag                             | `latest`                                                |
| `didFinder.rucio.pullPolicy`         | Rucio DID Finder image pull policy                     | `Always`                                          |
| `didFinder.rucio.servicex_latitude`        | Latitude of the computing center where ServiceX runs. Will be used by Rucio to return the closest input data replica.        | 41.78 |
| `didFinder.rucio.servicex_longitude`        | Longitude of the computing center where ServiceX runs. Will be used by Rucio to return the closest input data replica.        | -87.7 |
| `didFinder.rucio.cachePrefix`        | Prefix string to stick in front of file paths. Useful for XCache | |
| `didFinder.rucio.reportLogicalFiles` | For CMS xCache sites, we don't want the replicas, only logical names. Set to true to get this behavior | false |
| `didFinder.rucio.rucio_host`         | URL for Rucio service to use                     | `https://voatlasrucio-server-prod.cern.ch:443`          |
| `didFinder.rucio.auth _host`         | URL to obtain Rucio authentication               | `https://voatlasrucio-auth-prod.cern.ch:443`            |
|  `didFinder.rucio.memcache.enabled` | Should use memcache to store results returned by the DID lookup? | true |
|  `didFinder.rucio.memcache.image` | Docker image for memcache | memcached |
|  `didFinder.rucio.memcache.tag` | Tag of the memcache image | alpine |
|  `didFinder.rucio.memcache.ttl` | How long should memcache results be considered valid (in seconds) | 86400 |
| `didFinder.CERNOpenData.enabled`     | Should we deploy the CERN OpenData DID Finder?           | `true`                                              |
| `didFinder.CERNOpenData.image`       | CERN OpenData DID Finder image name                            | `sslhep/servicex-did-finder`                            |
| `didFinder.CERNOpenData.tag`         | CERN OpenData DID Finder image tag                             | `latest`                                                |
| `didFinder.CERNOpenData.pullPolicy`  | CERN OpenData DID Finder image pull policy                     | `Always`                                          |
| `didFinder.rucio.cachePrefix`        | Prefix string to stick in front of file paths. Useful for XCache | |
| `codeGen.enabled`                    | Enable deployment of code generator service?     | `true`                                                  |
| `codeGen.image`                      | Code Gen image name                              | `sslhep/servicex_code_gen_funcadl_xaod`                 |
| `codeGen.tag`                        | Code Gen image tag                               | `latest`                                                |
| `codeGen.pullPolicy`                 | Code Gen image pull policy                       | `Always`                                          |
| `x509Secrets.image`                  | X509 Secret Service image name                   | `sslhep/x509-secrets`                                   |
| `x509Secrets.tag`                    | X509 Secret Service image tag                    | `latest`                                                |
| `x509Secrets.pullPolicy`             | X509 Secret Service image pull policy            | `Always`                                          |
| `x509Secrets.vomsOrg`                | Which VOMS org to contact for proxy?             | `atlas`                                                 |
| `x509Secrets.initImage`              | X509 Secret Service init container image         | `alpine:3.6`                                            |
| `rbacEnabled`                        | Specify if rbac is enabled in your cluster       | `true`
| `hostMount`                          | Optional path to mount in transformers as /data  | -
| `gridAccount`                        | CERN User account name to access Rucio           | -
| `noCerts`                            | Set to true to disable x509 certs and only use open data | false                                            |
| `rabbitmq.password`                  | Override the generated RabbitMQ password         | leftfoot1 |
| `objectstore.enabled`                | Deploy a minio object store with Servicex?       | true      |
| `objectstore.internal`               | Deploy a captive minio instance with this chart? | true      |
| `objectstore.publicURL`              | What URL should the client use to download files? If set, this is given whether ingress is enabled or not  | nil |      |
| `postgres.enabled`                   | Deploy a postgres database into cluster? If not, we use a sqllite db | false  |
| `minio.auth.rootUser`                | Username to log into minio                       | miniouser |
| `minio.auth.rootPassword`            | Password key to log into minio                   | leftfoot1 |
| `minio.apiIngress.enabled`              | Should minio chart deploy an ingress to the service? | false |
| `minio.apiIngress.hostname`             | Hostname  associate with ingress controller      | nil |
| `transformer.autoscaler.enabled`     | Enable/disable horizontal pod autoscaler for transformers |  True |
| `transformer.autoscaler.cpuScaleThreshold` | CPU percentage threshold for pod scaling   | 30 |
| `transformer.autoscaler.minReplicas` | Minimum number of transformer pods per request   | 1 |
| `transformer.autoscaler.maxReplicas` | Maximum number of transformer pods per request   | 20 |
| `transformer.pullPolicy`             | Pull policy for transformer pods (Image name specified in REST Request) | Always |
| `transformer.priorityClassName`      | priorityClassName for transformer pods (Not setting it means getting global default) | Not Set |
| `transformer.cpuLimit`               | Set CPU resource limit for pod in number of cores | 1 |
| `transformer.defaultTransformerImage` | Default image for the transformers | 'sslhep/servicex_func_adl_xaod_transformer' |
| `transformer.defaultTransformerTag` | Default image for the transformers - must match the codeGen | '1.0.0-RC.3' |
| `transformer.persistence.existingClaim` | Existing persistent volume claim | nil |
| `transformer.subdir` | Subdirectory of the mount to write transformer results to (should end with trailing /) | nil |

## Logging chart

The following table lists the configurable parameters of the Logging chart and their default values.

| Parameter                            | Description                                      | Default                                                 |
| ------------------------------------ | ------------------------------------------------ | ------------------------------------------------------- |
| `servicex.namespace` | namespace where you have servicex deployed | default |
| `elasticsearch.host` | Elasticsearch host | atlas-kibana.mwt2.org |
| `elasticsearch.port` | Elasticsearch port | 9200 |
| `elasticsearch.user` | Elasticsearch user with appropriate roles | river-dev-logs  |
| `elasticsearch.pass` | Elasticsearch pass | river-dev-logs  |
| `elasticsearch.protocol` | SSL support | https  |
| `kibana.host` | address of the Kibana endpoint | <https://atlas-kibana.mwt2.org:5601> |
| `kibana.dashboards.enabled` | If not there dashboards will be created. | false |
| `kibana.dashboards.index` | Kibana system index | .kibana-dev  |