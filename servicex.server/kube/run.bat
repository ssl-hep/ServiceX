
REM __create secret with configuration__  
kubectl create secret -n servicex generic config-web --from-file=conf=../config/config.json

REM __create secret for globus__  
kubectl create secret -n servicex generic globus-secret --from-file=gconf=../../kube/secrets/globus-conf/globus-config.json

REM __deploy service and ingress__  
kubectl create -f service.yaml

REM __deploy the frontend__  
kubectl create -f deployment.yaml