#!/usr/bin/env bash

set -euo pipefail

# Default values
K8S_NAMESPACE="default"
HELM_NAME="${HELM_INSTALLATION_NAME:-servicex}"
SERVICE_TYPE=""
TIMEOUT="300"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --namespace)
            K8S_NAMESPACE="$2"
            shift 2
            ;;
        --helm-name)
            HELM_NAME="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        app|minio|db|prometheus|grafana|tempo)
            SERVICE_TYPE="$1"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [app|minio|db|prometheus|grafana|tempo] [OPTIONS]"
            echo ""
            echo "Services:"
            echo "  app        - Port forward to ServiceX app (8000)"
            echo "  minio      - Port forward to Minio (9000)"
            echo "  db         - Port forward to PostgreSQL (5432)"
            echo "  prometheus - Port forward to Prometheus (9090)"
            echo "  grafana    - Port forward to Grafana (3000)"
            echo "  tempo      - Port forward to Tempo (3200)"
            echo ""
            echo "Options:"
            echo "  --namespace NAMESPACE    Kubernetes namespace (default: default)"
            echo "  --helm-name NAME         Helm installation name (default: servicex)"
            echo "  --timeout SECONDS        How long to wait for the service (default: 300)"
            echo "  -h, --help              Show this help message"
            exit 0
            ;;
        *)
            echo "Error: Unknown argument '$1'"
            echo "Run '$0 --help' for usage information"
            exit 1
            ;;
    esac
done

# Validate service type is provided
if [ -z "$SERVICE_TYPE" ]; then
    echo "Error: Service type is required"
    echo "Usage: $0 [app|minio|db|prometheus|grafana|tempo] [OPTIONS]"
    echo "Run '$0 --help' for more information"
    exit 1
fi

# Service configuration
case "$SERVICE_TYPE" in
    app)
        SERVICE="${HELM_NAME}-servicex-app"
        PORT="8000"
        ;;
    minio)
        SERVICE="${HELM_NAME}-minio"
        PORT="9000"
        ;;
    db)
        SERVICE="${HELM_NAME}-postgresql"
        PORT="5432"
        ;;
    # The prometheus chart names the server <release>-prometheus-server; the
    # grafana and tempo charts collapse to <release>-<chart>.
    prometheus)
        SERVICE="${HELM_NAME}-prometheus-server"
        PORT="9090"
        ;;
    grafana)
        SERVICE="${HELM_NAME}-grafana"
        PORT="3000"
        ;;
    tempo)
        SERVICE="${HELM_NAME}-tempo"
        PORT="3200"
        ;;
esac

DEADLINE=$(( $(date +%s) + TIMEOUT ))

give_up() {
    echo "Error: $1 after ${TIMEOUT}s"
    exit 1
}

# Check if service is available
echo "Checking if service $SERVICE is available in namespace $K8S_NAMESPACE..."
while ! kubectl get service "$SERVICE" --namespace="$K8S_NAMESPACE" >/dev/null 2>&1; do
    [ "$(date +%s)" -lt "$DEADLINE" ] || give_up "service $SERVICE never appeared in namespace $K8S_NAMESPACE"
    echo "Service not found, waiting..."
    sleep 2
done

# Check if pods are running
echo "Checking if pods are running..."
while true; do
    # Try to find running pods by looking for endpoints
    ENDPOINTS=$(kubectl get endpoints "$SERVICE" --namespace="$K8S_NAMESPACE" -o jsonpath='{.subsets[0].addresses}' 2>/dev/null || echo "")
    if [ -n "$ENDPOINTS" ] && [ "$ENDPOINTS" != "null" ]; then
        echo "Service has ready endpoints"
        break
    fi
    [ "$(date +%s)" -lt "$DEADLINE" ] || give_up "service $SERVICE never got a ready endpoint"
    echo "No ready endpoints found, waiting..."
    sleep 2
done

echo "Starting port forwarding: localhost:${PORT} -> svc/${SERVICE}:${PORT}"

# Cleanup function
cleanup() {
    echo "Stopping port forwarding..."
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start port forwarding
kubectl port-forward --namespace="$K8S_NAMESPACE" "svc/$SERVICE" "${PORT}:${PORT}"
