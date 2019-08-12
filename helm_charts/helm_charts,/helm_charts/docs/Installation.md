# Installation

All the tools can be installed in different kubernetes clusters. Here instructions for each tool separately.
Secrets are all known to Ilija Vukotic.

## Frontend (ATM both web and REST API)
Kubectl commands listed should be executed from subdirectory _kube_. 

__label the node to be used for the frontend__  
```kubectl label nodes <node name> es=capable```

__ask Lincoln/Ilija/Judith to open ES firewall for that nodes IP. To get that IP look for external IP in output of :__  
``` kubectl describe node <node name>```

__in AWS Route53 change A record for **servicex.slateci.net** to that IP__

__create namespace__  
``` kubectl create -f namespace.yaml ```

__create secrets with site tls cert__  
```kubectl create secret -n servicex generic cert-secret --from-file=tls.key=secrets/https-certs/servicex.key.pem --from-file=tls.crt=secrets/https-certs/servicex.cert.crt```

__create secret with configuration__  
```kubectl create secret -n servicex generic config --from-file=conf=../config/config.json```

__create secret for Elasticsearch access__  
```kubectl create secret -n servicex generic es-secret --from-file=es_conf=secrets/elasticsearch/elasticsearch.json```

__create secret for Globus authentication__  
```kubectl create secret -n servicex generic globus-secret --from-file=gconf=secrets/globus-conf/globus-config.json```

__create service account__  
```kubectl create -f service_account.yaml```

__deploy service and ingress__  
```kubectl create -f service.yaml```

__deploy the frontend__  
```kubectl create -f frontend.yaml```

## did-finder, validator and transformer

While all three tools can be on different clusters they all require servicex namespace and a secret needed to access ATLAS data:  
```kubectl create secret -n servicex generic x509-secret --from-file=userkey=secrets/xcache.key.pem --from-file=usercert=secrets/xcache.crt.pem```

__deploy the did-finder__  
```kubectl create -f did-finder.yaml```

__deploy the validator__  
```kubectl create -f validator.yaml```

__deploy the transformer__  
```kubectl create -f did-finder.yaml```

## redis

Should be done from _servicex.redis/kube/standalone_.

__create redis namespace__  
```kubectl create ns redis```

__create redis monitor (optional)__  
```kubectl create kafka_monitor.yaml```

__create master configuration secret__  
```kubectl create secret -n redis generic redis-master-conf --from-file=conf=../config/redis.conf```

__deploy master. The default configuration requires a node with 200GB of RAM.__  
```kubectl create -f redis.yaml```

__get master node IP. In AWS Route53 change A record for **redis.slateci.net** to that IP__

__create slave configuration secret__  
```kubectl create secret -n redis generic redis-slave-conf --from-file=conf=../config/redis-slave.conf```

__deploy slave (optional)__  
```kubectl create -f redis-slave.yaml```
    
## kafka



