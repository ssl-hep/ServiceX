#!/bin/bash


# Function to start port forwarding
start_port_forward() {
    local service=$1
    local ports=$2
    echo "Starting port forward for $service on ports $ports"
    kubectl port-forward service/$service $ports &
}

# Function to stop port forwarding
stop_port_forward() {
    echo "Stopping all port forwards"
    pkill -f "kubectl port-forward"
}

# Start port forwarding for all services
start_all() {
  start_port_forward "servicex-ben-postgresql" "5432:5432"
  start_port_forward "servicex-ben-code-gen-uproot" "5001:8000"
  start_port_forward "servicex-ben-minio" "9001:9001"
  start_port_forward "servicex-ben-rabbitmq" "5672:5672"
  start_port_forward "servicex-ben-servicex-app" "8000:8000"

  echo "All port forwards started. Press Ctrl+C to stop."
}

# Main script
case "$1" in
    start)
        start_all
        # Wait for user interrupt
        trap stop_port_forward EXIT
        while true; do sleep 1; done
        ;;
    stop)
        stop_port_forward
        ;;
    *)
        echo "Usage: $0 {start|stop}"
        exit 1
        ;;
esac