kubectl create ns redis

# echo "Adding redis conf"
kubectl delete secret -n redis redis-master-conf
kubectl create secret -n redis generic redis-master-conf --from-file=conf=../config/redis.conf

kubectl delete -f redis.yaml
kubectl create -f redis.yaml

kubectl delete secret -n redis redis-slave-conf
kubectl create secret -n redis generic redis-slave-conf --from-file=conf=../config/redis-slave.conf

kubectl delete -f redis-slave.yaml
kubectl create -f redis-slave.yaml

kubectl get pods -n redis

# Deploy Redis.
kubectl create -f redis.yaml
kubectl create -f redis-slave.yaml

# create loadbalancer
kubectl create -f redis-loadbalancer.yaml

# test
kubectl run -it redis-cli --image=redis --restart=Never /bin/bash
redis-benchmark -q -h redis.slateci.net -p 6379 -c 100 -n 1000000
