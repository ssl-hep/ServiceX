# ServiceX Lite

This service runs a simple code that listens for the transformation request created in the "master" servicex and deploys transforms that will do the same job as the ones in the master.

Prerequisits:

* Kube configs of both slave and master k8s clusters.
* Deployment of a loadbalancer in front of the master servicex RMQ
* Master servicex configmap value ADVERTISED_HOSTNAME is set to the externally accessible servicex URL.
* Master servicex ingress routes internal paths the same way as external.

## TODO

* add options to configure xcache, resource request, etc.
* add creation of a HPA
* if needed - an automatic patching of master's configmap and ingress routes.
