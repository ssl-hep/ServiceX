minikube-mount: minikube start; minikube mount $LOCAL_DIR/servicex_app:/mnt/servicex & sleep 5 && cd $CHART_DIR && helm install -f $VALUES_FILE servicex . && sleep infinity
port-forward-app: cd $LOCAL_DIR && bash local/port-forward.sh app
port-forward-minio: cd $LOCAL_DIR && bash local/port-forward.sh minio
port-forward-db: cd $LOCAL_DIR && bash local/port-forward.sh db