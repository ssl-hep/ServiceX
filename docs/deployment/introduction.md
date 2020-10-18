# Introduction

ServiceX is a multi-tenant service designed to be deployed on a Kubernetes
cluster. At present, each ServiceX instance is dedicated to a particular
experiment and file format (flat root file, ATLAS xAOD, and CMS MiniAOD). There
are centrally managed instances of the service running on 
the University of Chicago's River cluster at 
[xaod.servicex.ssl-hep.org](https://xaod.servicex.ssl-hep.org) and 
[uproot.servicex.ssl-hep.org](https://uproot.servicex.ssl-hep.org). 

If you have access to a Kubernetes cluster and wish to deploy one or more 
instances of ServiceX, check out our [guide](basic.md) to making your first deployment.
