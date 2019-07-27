echo "Creating namespace"
kubectl create -f namespace.yaml

echo "Adding x509 cert needed for data access"
kubectl delete secret -n servicex x509-secret
kubectl create secret -n servicex generic x509-secret --from-file=userkey=secrets/xcache/xcache.key.pem --from-file=usercert=secrets/xcache/xcache.crt.pem

echo "Adding elasticsearch conf"
kubectl delete secret -n servicex es-secret
kubectl create secret -n servicex generic es-secret --from-file=es_conf=secrets/elasticsearch/elasticsearch.json

echo "Deploying transformer"
kubectl create -f transformer.yaml

REM echo "Adding site certs"
REM kubectl delete secret -n servicex cert-secret
REM kubectl create secret -n servicex generic cert-secret --from-file=tls.key=secrets/https-certs/servicex.key.pem --from-file=tls.crt=secrets/https-certs/servicex.cert.crt

REM echo "Adding site conf"
REM kubectl delete secret -n servicex config
REM kubectl create secret -n servicex generic config --from-file=conf=../config/config.json

REM echo "Adding globus secret"
REM kubectl delete secret -n servicex globus-secret
REM kubectl create secret -n servicex generic globus-secret --from-file=gconf=secrets/globus-conf/globus-config.json

REM echo "Create service account"
REM kubectl create -f service_account.yaml

REM echo "Deploying frontend service"
REM kubectl create -f gce-service.yaml

REM echo "Deploying server"
REM kubectl create -f gce-frontend.yaml

REM echo "Deploying did-finder"
REM kubectl create -f did-finder.yaml

REM echo "Deploying validator"
REM kubectl create -f validator.yaml

