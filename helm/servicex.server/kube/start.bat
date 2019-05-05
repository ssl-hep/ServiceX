echo "Creating namespace"
kubectl create -f namespace.yaml

REM echo "Adding x509 cert needed for data access"
REM kubectl delete secret -n servicex x509-secret
REM kubectl create secret -n servicex generic x509-secret --from-file=userkey=secrets/xcache.key.pem --from-file=usercert=secrets/xcache.crt.pem

echo "Adding site certs"
kubectl delete secret -n servicex cert-secret
kubectl create secret -n servicex generic cert-secret --from-file=key=secrets/https-certs/servicex.key.pem --from-file=cert=secrets/https-certs/servicex.cert.crt

echo "Adding site conf"
kubectl delete secret -n servicex config
kubectl create secret -n servicex generic config --from-file=conf=config.json

echo "Adding globus secret"
kubectl delete secret -n servicex globus-secret
kubectl create secret -n servicex generic globus-secret --from-file=gconf=secrets/globus-conf/globus-config.json

REM echo "Adding MailGun secret"
REM kubectl create secret -n servicex generic mg-config --from-file=mgconf=secrets/mg-config.json

echo "Create service account"
kubectl create -f service_account.yaml

echo "Deploying server"
kubectl create -f frontend.yaml

echo "Deploying did-finder"
kubectl create -f did-finder.yaml