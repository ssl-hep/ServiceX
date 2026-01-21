#!/usr/bin/env bash

set -euo pipefail

# Parse namespace argument (defaults to 'servicex')
NAMESPACE="${2:-servicex}"

# Service configuration
case "${1:-}" in
    app)
        SERVICE="${NAMESPACE}-servicex-app"
        PORT="8000"
        ;;
    minio)
        SERVICE="${NAMESPACE}-minio"
        PORT="9000"
        ;;
    db)
        SERVICE="${NAMESPACE}-postgresql"
        PORT="5432"
        ;;
    *)
        echo "Usage: $0 [app|minio|db] [namespace]"
        echo "  app   - Port forward to ServiceX app (8000)"
        echo "  minio - Port forward to Minio (9000)"
        echo "  db    - Port forward to PostgreSQL (5432)"
        echo ""
        echo "Optional arguments:"
        echo "  namespace - Kubernetes namespace (default: servicex)"
        exit 1
        ;;
esac

# Check if service is available
echo "Checking if service $SERVICE is available..."
while ! kubectl get service "$SERVICE" --namespace="${NAMESPACE}" >/dev/null 2>&1; do
    echo "Service not found, waiting..."
    sleep 2
done

# Check if pods are running
echo "Checking if pods are running..."
while true; do
    # Try to find running pods by looking for endpoints
    ENDPOINTS=$(kubectl get endpoints "$SERVICE" --namespace="${NAMESPACE}" -o jsonpath='{.subsets[0].addresses}' 2>/dev/null || echo "")
    if [ -n "$ENDPOINTS" ] && [ "$ENDPOINTS" != "null" ]; then
        echo "Service has ready endpoints"
        break
    fi
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
kubectl port-forward --namespace="${NAMESPACE}" "svc/$SERVICE" "${PORT}:${PORT}"
