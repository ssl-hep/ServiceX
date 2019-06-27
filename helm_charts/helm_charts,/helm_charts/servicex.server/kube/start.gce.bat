echo "Creating namespace"
kubectl create -f namespace.yaml

echo "Adding x509 cert needed for data access"
kubectl delete secret -n servicex x509-secret
kubectl create secret -n servicex generic x509-secret --from-file=userkey=secrets/xcache/xcache.key.pem --from-file=usercert=secrets/xcache/xcache.crt.pem

echo "Adding site certs"
kubectl delete secret -n servicex cert-secret
kubectl create secret -n servicex generic cert-secret --from-file=tls.key=secrets/https-certs/servicex.key.pem --from-file=tls.crt=secrets/https-certs/servicex.cert.crt

echo "Adding site conf"
kubectl delete secret -n servicex config
kubectl create secret -n servicex generic config --from-file=conf=../config/config.json

echo "Adding elasticsearch conf"
kubectl delete secret -n servicex es-secret
kubectl create secret -n servicex generic es-secret --from-file=es_conf=secrets/elasticsearch/elasticsearch.json

echo "Adding globus secret"
kubectl delete secret -n servicex globus-secret
kubectl create secret -n servicex generic globus-secret --from-file=gconf=secrets/globus-conf/globus-config.json

echo "Create service account"
kubectl create -f service_account.yaml

echo "Deploying frontend service"
kubectl create -f gce-service.yaml

echo "Deploying server"
kubectl create -f gce-frontend.yaml

echo "Deploying did-finder"
kubectl create -f did-finder.yaml

echo "Deploying validator"
kubectl create -f validator.yaml

echo "Deploying transformer"
kubectl create -f transformer.yaml

echo "================"
echo "1. get servicex IP and in amazon route53 change A record for servicex.slateci.net"
echo "2. get kafka server IPs and in amazon route53 change A records for servicex-kafka-0/1/2.slateci.net "
echo "   and kafka-manager.slateci.net "
echo "3. open ES ports for servicex GCE nodes. (search for GCP-SERVICEX-K8S in uc2-puppet)"
echo "================"