kubectl create namespace servicex

echo "Adding conf"
kubectl delete secret -n servicex config
kubectl create secret -n servicex generic config --from-file=conf=../config/config.json

echo "Adding x509 cert needed for data access"
kubectl delete secret -n servicex x509-secret
kubectl create secret -n servicex generic x509-secret --from-file=userkey=secrets/xcache.key.pem --from-file=usercert=secrets/xcache.crt.pem

kubectl create -f did-finder.yaml

