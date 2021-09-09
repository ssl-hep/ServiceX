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
