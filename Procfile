minikube-mount: minikube mount $LOCAL_DIR/servicex_app:/mnt/servicex & echo "Mount active on $LOCAL_DIR/servicex_app:/mnt/servicex" && (while true; do sleep 86400; done)
servicex-install: until kubectl get nodes &>/dev/null; do echo "Waiting for Kubernetes to be available..."; sleep 2; done && echo "Kubernetes is ready!" && cd $CHART_DIR && helm install -f $VALUES_FILE servicex . && echo "Helm installation complete, keeping process alive..." && while true; do sleep 86400; done
port-forward-app: cd $LOCAL_DIR && bash local/port-forward.sh app
port-forward-minio: cd $LOCAL_DIR && bash local/port-forward.sh minio
port-forward-db: cd $LOCAL_DIR && bash local/port-forward.sh db