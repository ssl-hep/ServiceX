minikube-mount: minikube mount $LOCAL_DIR:/mnt/servicex
helm-install: sleep 5; cd $CHART_DIR && helm install -f $VALUES_FILE servicex . && tail -f /dev/null
port-forward-app: sleep 20 && cd $LOCAL_DIR && bash local/port-forward.sh app
port-forward-minio: sleep 20 && cd $LOCAL_DIR && bash local/port-forward.sh minio
port-forward-db: sleep 20 && cd $LOCAL_DIR && bash local/port-forward.sh db
