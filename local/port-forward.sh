#!/usr/bin/env bash

set -euo pipefail

# Constants
readonly NAMESPACE="${NAMESPACE:-default}"
readonly PING_INTERVAL=5
readonly MAX_RETRIES=10

# Parse service configuration
case "${1:-}" in
    app)
        SERVICE_NAME="servicex-servicex-app"
        CONTAINER_PORT="8000"
        LOCAL_PORT="5000"
        ;;
    minio)
        SERVICE_NAME="servicex-minio"
        CONTAINER_PORT="9000"
        LOCAL_PORT="9000"
        ;;
    db)
        SERVICE_NAME="servicex-postgresql"
        CONTAINER_PORT="5432"
        LOCAL_PORT="5432"
        ;;
    *)
        echo "Usage: $0 [app|minio|db]"
        echo "  app   - Port forward to ServiceX app (5000 -> 8000)"
        echo "  minio - Port forward to Minio (9000 -> 9000)"
        echo "  db    - Port forward to PostgreSQL (5432 -> 5432)"
        exit 1
        ;;
esac

readonly SERVICE_TYPE="$1"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

# Function to check if service exists
check_service_exists() {
    kubectl get service "$SERVICE_NAME" --namespace="$NAMESPACE" >/dev/null 2>&1
}

# Function to wait for pod to be ready
wait_for_pod_ready() {
    log "Waiting for pods of service $SERVICE_NAME to be ready..."
    local retries=0

    while [[ $retries -lt $MAX_RETRIES ]]; do
        # Get pods for the service using selector
        local selector=$(kubectl get service "$SERVICE_NAME" --namespace="$NAMESPACE" -o jsonpath='{.spec.selector}' 2>/dev/null || echo "")

        if [[ -n "$selector" ]]; then
            # Convert JSON selector to kubectl selector format
            local kubectl_selector=$(echo "$selector" | sed 's/[{}"]//g' | sed 's/:/=/g' | sed 's/,/,/g')

            # Check if any pods are ready
            local ready_pods=$(kubectl get pods --namespace="$NAMESPACE" --selector="$kubectl_selector" --field-selector=status.phase=Running -o name 2>/dev/null | wc -l)

            if [[ $ready_pods -gt 0 ]]; then
                log "Found $ready_pods ready pod(s) for service $SERVICE_NAME"
                return 0
            fi
        fi

        ((retries++))
        log "No ready pods found, retrying... ($retries/$MAX_RETRIES)"
        sleep 5
    done

    log "No ready pods found for service $SERVICE_NAME after $MAX_RETRIES attempts"
    return 1
}

# Function to wait for service availability
wait_for_service() {
    log "Waiting for service $SERVICE_NAME to be available..."
    local retries=0

    while ! check_service_exists && [[ $retries -lt $MAX_RETRIES ]]; do
        ((retries++))
        log "Service not found, retrying... ($retries/$MAX_RETRIES)"
        sleep 3
    done

    if [[ $retries -ge $MAX_RETRIES ]]; then
        log "Service $SERVICE_NAME not found after $MAX_RETRIES attempts"
        return 1
    fi

    log "Service $SERVICE_NAME is available"
    return 0
}

# Function to start port forwarding using service
start_port_forward() {
    log "Starting port forwarding: localhost:${LOCAL_PORT} -> ${SERVICE_NAME}:${CONTAINER_PORT}"

    # Check if pods are still ready before attempting port forward
    if ! wait_for_pod_ready; then
        log "Pods not ready, cannot start port forwarding"
        return 1
    fi

    kubectl port-forward --namespace="$NAMESPACE" "service/$SERVICE_NAME" "${LOCAL_PORT}:${CONTAINER_PORT}" &
    PORT_FORWARD_PID=$!

    # Give it a moment to establish connection
    sleep 2

    # Check if port forward process is still running
    if ! kill -0 "$PORT_FORWARD_PID" 2>/dev/null; then
        log "Port forwarding failed to start"
        return 1
    fi

    log "Port forwarding established (PID: $PORT_FORWARD_PID)"
    return 0
}

# Function to check if port forwarding is working
check_port_forward() {
    # Simply check if the port forward process is still running
    if ! kill -0 "$PORT_FORWARD_PID" 2>/dev/null; then
        log "Port forward process is not running"
        return 1
    fi

    # Additional check: verify port is actually listening
    if command -v nc >/dev/null 2>&1; then
        if ! nc -z localhost "$LOCAL_PORT" 2>/dev/null; then
            log "Port $LOCAL_PORT is not accessible"
            return 1
        fi
    fi

    return 0
}

# Function to clean up resources
cleanup() {
    log "Cleaning up..."
    if [[ -n "${PORT_FORWARD_PID:-}" ]]; then
        log "Terminating port forwarding process (PID: $PORT_FORWARD_PID)"
        kill "$PORT_FORWARD_PID" 2>/dev/null || true
        wait "$PORT_FORWARD_PID" 2>/dev/null || true
    fi
    log "Cleanup complete"
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM EXIT

# Main execution
main() {
    log "Starting port forwarding for $SERVICE_TYPE: $SERVICE_NAME"

    # Wait for service to be available
    if ! wait_for_service; then
        log "Service $SERVICE_NAME is not available"
        exit 1
    fi

    # Wait for pods to be ready
    if ! wait_for_pod_ready; then
        log "No ready pods found for service $SERVICE_NAME"
        exit 1
    fi

    # Main monitoring loop
    while true; do
        # Start port forwarding if not already running
        if [[ -z "${PORT_FORWARD_PID:-}" ]] || ! kill -0 "$PORT_FORWARD_PID" 2>/dev/null; then
            log "Starting port forwarding..."
            if ! start_port_forward; then
                log "Failed to start port forwarding, retrying in $PING_INTERVAL seconds..."
                # Reset PID if it exists but failed
                if [[ -n "${PORT_FORWARD_PID:-}" ]]; then
                    unset PORT_FORWARD_PID
                fi
                sleep "$PING_INTERVAL"
                continue
            fi
        fi

        # Check if port forwarding is working
        if ! check_port_forward; then
            log "Port forwarding failed, restarting..."
            if [[ -n "${PORT_FORWARD_PID:-}" ]]; then
                kill "$PORT_FORWARD_PID" 2>/dev/null || true
                wait "$PORT_FORWARD_PID" 2>/dev/null || true
                unset PORT_FORWARD_PID
            fi
            sleep 2
            continue
        fi

        # Wait before next check
        sleep "$PING_INTERVAL"
    done
}

# Run main function
main
