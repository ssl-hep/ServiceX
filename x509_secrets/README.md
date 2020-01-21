
# X509 Proxy Generator
This image passes a users grid cert and key to the VOMS Proxy server to generate
an X509 proxy which is published into the cluster as a kubernetes secret.

It accepts as runtime parameter the VOMS organization to use for validating
the user. It also can be run inside docker (without a kubernetes cluster) for
testing.

To start docker container: 
```bash
docker run --rm -it \
    -e VOMS=atlas \
    --mount type=bind,source=$HOME/.globus,readonly,target=/etc/grid-certs \
    --mount type=bind,source="$(pwd)"/secrets/secrets.txt,target=/servicex/secrets.txt \
    --mount type=volume,source=x509,target=/etc/grid-security \
    --name=x509-secrets sslhep/x509-secrets:develop
```

The environment var `VOMS` can be set to CMS if you wish to authenticate against 
that experiment.
