minikube-mount-app: minikube mount $LOCAL_DIR:/mnt/servicex
minikube-mount-topcp: minikube mount $LOCAL_DIR/code_generator_TopCPToolkit:/mnt/topcp
helm-install: sleep 5; cd $CHART_DIR && helm install -f "$VALUES_FILE" "${HELM_INSTALLATION_NAME:-servicex}" . && tail -f /dev/null
port-forward-app: sleep 30 && cd $LOCAL_DIR && bash local/port-forward.sh app
port-forward-minio: sleep 20 && cd $LOCAL_DIR && bash local/port-forward.sh minio
port-forward-db: sleep 20 && cd $LOCAL_DIR && bash local/port-forward.sh db
port-forward-prometheus: sleep 20 && cd $LOCAL_DIR && bash local/port-forward.sh prometheus
port-forward-grafana: sleep 20 && cd $LOCAL_DIR && bash local/port-forward.sh grafana
