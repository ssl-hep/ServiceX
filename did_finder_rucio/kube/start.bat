kubectl delete secret -n servicex cert-secret
kubectl create secret -n servicex generic cert-secret --from-file=userkey=secrets/xcache.key.pem --from-file=usercert=secrets/xcache.crt.pem

kubectl create -f did-finder.yaml

