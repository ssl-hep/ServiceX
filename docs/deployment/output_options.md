# Columnar Output Options
The transformers can write the columnar data to a deployed [Minio Object
store](https://docs.min.io/docs/minio-quickstart-guide.html), to an xRootD
storage element, or to mounted POSIX volumes.

## Minio
The helm chart has an option to deploy the legacy Minio helm chart as a
dependent chart. This has options to create an ingress so you can access your
objects remotely.

Minio is enabled by default. In transforms, set the `result-destination`
property to `object-store`.

## xRootD Storage Element
Sites that already run grid storage can skip the object store entirely and have
transform results written to an xRootD storage element (EOS, dCache, XCache and
friends). The workflow is unchanged: the science container still writes to the
pod's scratch directory, and the sidecar pushes the finished file to storage.

All outputs live under one top level path, and each transform writes into a
subdirectory of it named after the transform request id. Set:

```yaml
objectStore:
  enabled: false
xrootdStore:
  enabled: true
  rootURL: root://my.storage.org:1094//servicex/outputs
  publicURL: https://my.storage.org:1094/servicex/outputs
```

`objectStore.enabled` and `xrootdStore.enabled` are mutually exclusive, and
helm will refuse to render the chart if both are on.

Transforms are still submitted with `result-destination` set to
`object-store` - only the store behind it changes. Clients get their download
URLs from the server's `file-urls` endpoint, which hands back `publicURL`
based HTTPS links by default, or `rootURL` based `root://` links for clients
that ask for the `xrootd` scheme. Leaving `publicURL` unset limits clients to
`root://` URLs.

Access to the storage server comes from the x509 proxy, so `noCerts` must be
false and the `gridAccount` must be allowed to write under `rootURL`. The
proxy secret is mounted into both the ServiceX app and the transformer
sidecar, which copy it to a private location before use. The storage server's
CA certificates need to be available at `/etc/grid-security/certificates` in
those pods, which on most sites means mounting CVMFS or using images that
carry the grid CAs.

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
