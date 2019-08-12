# Installation

All the tools can be installed in different kubernetes clusters. Here instructions for each tool separately.
Kubectl commands listed should be executed from subdirectory _kube_.

# Frontend (ATM both web and REST API)
* Label the node

* create namespace

    kubectl create -f namespace.yaml

* create secrets with site tls cert

    kubectl create secret -n servicex generic cert-secret --from-file=tls.key=secrets/https-certs/servicex.key.pem --from-file=tls.crt=secrets/https-certs/servicex.cert.crt

* create secret with configuration

    kubectl create secret -n servicex generic config --from-file=conf=../config/config.json

* create secret for Elasticsearch access

    kubectl create secret -n servicex generic es-secret --from-file=es_conf=secrets/elasticsearch/elasticsearch.json

* create secret for Globus authentication

    kubectl create secret -n servicex generic globus-secret --from-file=gconf=secrets/globus-conf/globus-config.json

* create service account (optional)

    kubectl create -f service_account.yaml

* deploy service and ingress

    kubectl create -f service.yaml

* deploy the frontend

    kubectl create -f frontend.yaml

# did-finder, validator and transformer

* while all three tools can be on different clusters they all require servicex namespace and a secret needed to access ATLAS data:

    kubectl create secret -n servicex generic x509-secret --from-file=userkey=secrets/xcache.key.pem --from-file=usercert=secrets/xcache.crt.pem

* deploy the did-finder

    kubectl create -f did-finder.yaml

* deploy the validator

    kubectl create -f validator.yaml

* deploy the transformer

    kubectl create -f did-finder.yaml

# redis

Should be done from _servicex.redis/kube/standalone_.
* create redis namespace

    kubectl create ns redis

* create redis monitor (optional)

    kubectl create kafka_monitor.yaml

* create master configuration secret

    kubectl create secret -n redis generic redis-master-conf --from-file=conf=../config/redis.conf

* deploy master. The default configuration requires a node with 200GB of RAM.

    kubectl create -f redis.yaml

* create slave configuration secret

    kubectl create secret -n redis generic redis-slave-conf --from-file=conf=../config/redis-slave.conf

* deploy slave (optional)

    kubectl create -f redis-slave.yaml
    
# kafka



