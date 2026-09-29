# Columnar Output Options
The transformers can write the columnar data either to a deployed [Minio Object
store](https://docs.min.io/docs/minio-quickstart-guide.html) or to mounted
POSIX volumes.

## Minio
The helm chart has an option to deploy the legacy Minio helm chart as a
dependent chart. This has options to create an ingress so you can access your
objects remotely.

Minio is enabled by default. In transforms, set the `result-destination`
property to `object-store`.

## POSIX Mounted Volumes
In some environments there is an existing filesystem, and it makes sense to
write the extracted files there for further processing.

You can retain the Minio deployment if desired, otherwise deactivate it and
prevent helm from deploying Minio by setting:
```yaml
objectStore:
  enabled: false
```

The mounted POSIX volumes assumes that a kubernetes read-write-many persistent
volume claim exists in the deployed namespace. If you need an example on
creating a PVC, take a look in this repo's `scripts/transformer_pvc.yaml` file.

In your helm values file you can provide this PVC name as well as a subdirectory
into the claim where the files will be written. Note that this subdir path
must have a trailing / to be treated as a directory:

```yaml
transformer:
  persistence:
     existingClaim: transformer-pv-claim
     subdir: foo/bar/
```

## WebDAV
If you would rather hand results to a plain HTTP filesystem than an object
store, the chart can deploy a [WebDAV server](https://github.com/vaggeliskls/webdav-server)
backed by a persistent volume. Transformers upload each result with an HTTP
`PUT`, so nothing needs to be mounted into the transformer pods.

Enable it with:
```yaml
webdav:
  enabled: true
  auth:
    username: servicex
    password: <pick something>
```

In transforms, set the `result-destination` property to `webdav`. Results are
written to `<root>/<request id>/<filename>` on the server, where `root`
defaults to `servicex`. The transform status reports the collection for a
request as `webdav-endpoint`, together with the credentials to read it.

By default the server is only reachable from inside the cluster. To let clients
download results directly, add an ingress:
```yaml
webdav:
  enabled: true
  ingress:
    enabled: true
    host: webdav.example.com
    tls:
      enabled: true
      clusterIssuer: letsencrypt-prod
```

The chart creates a 10Gi `ReadWriteOnce` claim for the data. Point it at a
volume you have already provisioned with
`webdav.persistence.existingClaim`, or size the one it creates with
`webdav.persistence.size` and `webdav.persistence.storageClass`.

To use a WebDAV server you already run, turn off the captive deployment and
give ServiceX its URL:
```yaml
webdav:
  enabled: true
  internal: false
  url: https://dav.example.org
  auth:
    username: servicex
    password: <the account's password>
```

Note that the WebDAV and Minio options are not exclusive - leaving
`objectStore.enabled` on lets users pick a destination per transform.
