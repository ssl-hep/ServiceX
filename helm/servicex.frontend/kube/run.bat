
REM __create secret with configuration__  
kubectl create secret -n servicex generic config --from-file=conf=../config/config.json

REM __create secret for Elasticsearch access__  
kubectl create secret -n servicex generic es-secret --from-file=es_conf=secrets/elasticsearch/elasticsearch.json

REM __deploy service and ingress__  
kubectl create -f service.yaml

REM __deploy the frontend__  
kubectl create -f frontend.yaml