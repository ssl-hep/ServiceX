echo "Creating namespace"
kubectl create -f namespace.yaml

echo "Adding site certs"
kubectl delete secret -n servicex cert-secret
kubectl create secret -n servicex generic cert-secret --from-file=key=secrets/servicex.key.pem --from-file=cert=secrets/servicex.cert.crt

echo "Adding site conf"
kubectl delete secret -n servicex config
kubectl create secret -n servicex generic config --from-file=conf=config.json

echo "Adding globus secret"
kubectl delete secret -n servicex globus-secret
kubectl create secret -n servicex generic globus-secret --from-file=gconf=secrets/globus-config.json

REM echo "Adding MailGun secret"
REM kubectl create secret -n servicex generic mg-config --from-file=mgconf=secrets/mg-config.json

echo "Create service account"
kubectl create -f service_account.yaml

echo "Deploying server"
kubectl create -f frontend.yaml