echo "Creating namespace"
kubectl create -f namespace.yaml

echo "Adding site certs"
kubectl create secret -n servicex generic cert-secret --from-file=key=secrets/certificates/servicex.key.pem --from-file=cert=secrets/certificates/servicex.cert.cer
kubectl delete secret -n servicex config
kubectl create secret -n servicex generic config --from-file=conf=config.json

echo "Adding globus secret"
REM kubectl create secret -n servicex generic globus-secret --from-file=gconf=secrets/globus-config.json

echo "Adding MailGun secret"
REM kubectl create secret -n servicex generic mg-config --from-file=mgconf=secrets/mg-config.json

echo "Create service account"
REM kubectl create -f service_account.yaml

echo "Deploying server"
kubectl create -f frontend.yaml