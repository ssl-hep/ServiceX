echo "Creating namespace"
kubectl create -f namespace.yaml

echo "Adding site certs"
kubectl create secret -n gates generic cert-secret --from-file=key=secrets/certificates/gates.key.pem --from-file=cert=secrets/certificates/gates.cert.cer
kubectl delete secret -n gates config
kubectl create secret -n gates generic config --from-file=conf=config.json

echo "Adding globus secret"
kubectl create secret -n gates generic globus-secret --from-file=gconf=secrets/globus-config.json

echo "Adding MailGun secret"
kubectl create secret -n gates generic mg-config --from-file=mgconf=secrets/mg-config.json

echo "Create service account"
kubectl create -f service_account.yaml

echo "Deploying server"
kubectl create -f frontend.yaml