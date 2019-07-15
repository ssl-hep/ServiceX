kubectl create -f configmaps/

# Deploy Redis pods.
kubectl create -f redis-cache.yaml

# Prepare a list of Redis cache nodes.
kubectl get pods -l app=redis,redis-type=cache -o wide | tail -n +2 | awk '{printf "%s:%s ",$6,"6379"}' > redis-nodes.txt
kubectl create configmap redis-nodes --from-file=redis-nodes.txt

# Submits a job to configure cluster
kubectl create -f redis-create-cluster.yaml