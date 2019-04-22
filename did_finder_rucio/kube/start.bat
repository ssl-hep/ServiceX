kubectl delete secret -n servicex cert-secret
kubectl create secret generic cert-secret \
--from-file=userkey=certificates/xcache.key.pem \
--from-file=usercert=certificates/xcache.crt.pem

kubectl create -y did-finder.yaml

