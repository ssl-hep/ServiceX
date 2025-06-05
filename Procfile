minikube-mount: minikube mount $LOCAL_DIR:/mnt/servicex & sleep 5 && cd $CHART_DIR && helm install -f $VALUES_FILE servicex . && while true; do sleep 86400; done
port-forward-app: cd $LOCAL_DIR && bash local/port-forward.sh app
port-forward-minio: cd $LOCAL_DIR && bash local/port-forward.sh minio
port-forward-db: cd $LOCAL_DIR && bash local/port-forward.sh db