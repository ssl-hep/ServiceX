# Deploying Kafka For ServiceX
This directory contains instructions and resources for deploying a kafka
cluster to support ServiceX.

This helm deployment is described 
[here.](https://github.com/helm/charts/tree/master/incubator/kafka). 

By following this recipe you can deploy a kafka cluster inside Kubernetes. These
instructions do not include making Kafka accessable outside of the cluster since
this brings in a number of authentication issues. See 
[ServiceX Issue 72](https://github.com/ssl-hep/ServiceX/issues/72) for full 
details and updates on this.

We will assume that you have [Helm3](https://helm.sh) installed.
   
## Deployment  

Add helm repository:

    helm repo add incubator http://storage.googleapis.com/kubernetes-charts-incubator

Optionally, create a namespace for the cluster:
    
    kubectl create ns kafka-inc

Install kafka:

    helm install kafka-inc incubator/kafka -n kafka-inc -f servicex-values.yaml


## Uninstall
    
Delete deployment:

    helm delete kafka-inc

Delete persistent volume claims:

    kubectl delete pvc datadir-kafka-inc-0,1,2...


## Accessing kafka

The Kafka brokers and Zookeeper can be referenced inside the cluster using 
their service name. If you wish to access them from a pod in a different 
namespace you can use a fully qualified cluster DNS name such as 
`kafka-inc.kafka-inc.svc.cluster.local:9092`


Here a list of services that are accessible from any namespace in the cluster

    export ZOO=kafka-inc-zookeeper.kafka-inc.svc.cluster.local:2181
    export KBOOTSTR=kafka-inc-headless.kafka-inc.svc.cluster.local:9092
    export KBROKERS=kafka-inc.kafka-inc.svc.cluster.local:9092

## Install An In-Cluster CLI
You can use the popular [kafkacat](https://github.com/edenhill/kafkacat) inside
the cluster. 

    kubectl create -f kafkacat.yaml
    
After the pod is running

    kubectl exec -it kafkacat bash
    kafkacat -L -b $KBROKERS
    
You can list the partitions of a topic and monitor thier offsets with:
    
    kafkacat -t <<topic>> -b $KBROKERS -f 'Partition %p, offset: %o, Size: %S\n'
    

## Install Web-Based GUI
There is an excellent web client called [CMAK](https://github.com/yahoo/CMAK).
You can install it into your cluster using the helm chart from Google Stable
repo:

    helm repo add stable https://kubernetes-charts.storage.googleapis.com
    
You will need to edit the zookeeper settings in the `kafka-manager-values.yaml`
file found in this directory. It will need to match the name of the kafka 
deployment. Once you've updated this file you can install the manager:

    helm install kafkaman stable/kafka-manager
    
You can use port forwarding to access this dashboard

    kubectl port-forward <kafka-manager pod> 9000:9000

And log in with username: admin, password: leftfoot1


    
    
 