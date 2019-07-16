gcloud container clusters create redis-cluster --num-nodes 6 --machine-type n1-standard-1 --image-type COS --disk-type pd-standard --disk-size 100 --enable-ip-alias --create-subnetwork name=redis-subnet --zone us-central1-a

kubectl create -f configmaps/

# Deploy Redis pods.
kubectl create -f redis-cache.yaml

# Prepare a list of Redis cache nodes.
kubectl get pods -l app=redis,redis-type=cache -o wide | tail -n +2 | awk '{printf "%s:%s ",$6,"6379"}' > redis-nodes.txt
kubectl create configmap redis-nodes --from-file=redis-nodes.txt

# Submits a job to configure cluster
kubectl create -f redis-create-cluster.yaml

# test
kubectl run -it redis-cli --image=redis --restart=Never /bin/bash
redis-benchmark -q -h 34.66.208.246 -p 6379 -c 100 -n 1000000

PING_INLINE: 46869.14 requests per second
PING_BULK: 47975.44 requests per second
SET: 42274.36 requests per second
GET: 43715.85 requests per second
INCR: 43166.71 requests per second
LPUSH: 37223.15 requests per second
RPUSH: 38534.16 requests per second
LPOP: 40142.91 requests per second
RPOP: 41303.54 requests per second
SADD: 45649.59 requests per second
HSET: 43563.49 requests per second
SPOP: 46189.38 requests per second
LPUSH (needed to benchmark LRANGE): 37259.21 requests per second
LRANGE_100 (first 100 elements): 21461.53 requests per second
LRANGE_300 (first 300 elements): 9010.79 requests per second
LRANGE_500 (first 450 elements): 6620.81 requests per second
LRANGE_600 (first 600 elements): 5215.29 requests per second
MSET (10 keys): 37780.04 requests per second


# requires different py client
pip install redis-py-cluster
