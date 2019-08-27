kubectl create ns servicex

# echo "Adding redis conf"
kubectl delete secret -n servicex redis-master-conf
kubectl create secret -n servicex generic redis-master-conf --from-file=conf=../config/redis.conf

kubectl delete -f redis.yaml
kubectl create -f redis.yaml

kubectl delete secret -n servicex redis-slave-conf
kubectl create secret -n servicex generic redis-slave-conf --from-file=conf=../config/redis-slave.conf

kubectl delete -f redis-slave.yaml
kubectl create -f redis-slave.yaml

kubectl get pods -n servicex

# create loadbalancer
kubectl create -f redis-loadbalancer.yaml

kubectl get services -n servicex

# test
kubectl run -it redis-cli --image=redis --restart=Never /bin/bash
redis-benchmark -q -h redis.slateci.net -p 6379 -c 100 -n 1000000
