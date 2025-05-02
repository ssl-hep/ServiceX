#!/bin/bash

# Constants
NAMESPACE="default"
PING_INTERVAL=2  # seconds
MAX_HELM_RETRIES=12  # Maximum number of times to check for helm installation

# Configuration based on service type
if [ "$1" = "app" ]; then
    APP_LABEL="servicex-servicex-app"
    LOCAL_PORT=5000
    CONTAINER_PORT=5000
    PING_URL="http://localhost:${LOCAL_PORT}/servicex"
elif [ "$1" = "minio" ]; then
    APP_LABEL="minio"
    LOCAL_PORT=9000
    CONTAINER_PORT=9000
    # Don't use direct HTTP check for Minio as it might require auth
    PING_URL=""
elif [ "$1" = "db" ]; then
    APP_LABEL="postgresql"
    LOCAL_PORT=5432
    CONTAINER_PORT=5432
    PING_URL=""  # No HTTP endpoint to check for DB
    POD_NAME="servicex-postgresql-0"  # Fixed pod name for DB
else
    echo "Usage: $0 [app|minio|db]"
    echo "  app   - Port forward to ServiceX app (5000:5000)"
    echo "  minio - Port forward to Minio (9000:9000)"
    echo "  db    - Port forward to PostgreSQL (5432:5432)"
    exit 1
fi

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to check if servicex helm installation exists
check_helm_installation() {
    log "Checking if 'servicex' helm installation exists"
    if helm list | grep -q servicex; then
        log "Found 'servicex' helm installation"
        return 0
    else
        log "No 'servicex' helm installation found"
        return 1
    fi
}

# Function to wait for helm installation
wait_for_helm_installation() {
    log "Waiting for 'servicex' helm installation"
    local retries=0

    while ! check_helm_installation && [ $retries -lt $MAX_HELM_RETRIES ]; do
        retries=$((retries+1))
        log "Waiting for 'servicex' helm installation... ($retries/$MAX_HELM_RETRIES)"
        sleep 5
    done

    if [ $retries -ge $MAX_HELM_RETRIES ]; then
        log "Timed out waiting for 'servicex' helm installation"
        return 1
    fi

    return 0
}

# Function to get pod name
get_pod_name() {
    # Skip for DB since we already know the pod name
    if [ "$1" = "db" ]; then
        return 0
    fi

    log "Getting pod name for $APP_LABEL"

    if [ "$1" = "app" ]; then
        POD_NAME=$(kubectl get pods --namespace $NAMESPACE -l "app=servicex-servicex-app" -o jsonpath="{.items[0].metadata.name}" 2>/dev/null)
    elif [ "$1" = "minio" ]; then
        # Try multiple approaches to find the minio pod without detailed logging
        POD_NAME=$(kubectl get pods --namespace $NAMESPACE -l "app=minio,release=servicex" -o jsonpath="{.items[0].metadata.name}" 2>/dev/null)

        if [ -z "$POD_NAME" ]; then
            POD_NAME=$(kubectl get pods --namespace $NAMESPACE -l "app=minio" -o jsonpath="{.items[0].metadata.name}" 2>/dev/null)
        fi

        if [ -z "$POD_NAME" ]; then
            POD_NAME=$(kubectl get pods --namespace $NAMESPACE | grep -i "servicex-minio" | awk '{print $1}' | head -1)
        fi

        if [ -z "$POD_NAME" ]; then
            POD_NAME=$(kubectl get pods --namespace $NAMESPACE | grep -i "minio" | awk '{print $1}' | head -1)
        fi

        if [ -z "$POD_NAME" ]; then
            log "Error: Could not find any minio pods."
            return 1
        fi
    fi

    if [ -z "$POD_NAME" ]; then
        log "Error: Could not find pod for $APP_LABEL"
        return 1
    fi

    log "Found pod: ${POD_NAME}"
    return 0
}

# Function to start port forwarding
start_port_forward() {
    if [ "$1" = "db" ]; then
        log "Starting port forwarding from localhost:${LOCAL_PORT} to servicex-postgresql-0:${CONTAINER_PORT}"
        kubectl port-forward --namespace $NAMESPACE servicex-postgresql-0 ${LOCAL_PORT}:${CONTAINER_PORT} &
    else
        log "Starting port forwarding from localhost:${LOCAL_PORT} to ${POD_NAME}:${CONTAINER_PORT}"
        kubectl port-forward --namespace $NAMESPACE $POD_NAME ${LOCAL_PORT}:${CONTAINER_PORT} &
    fi

    PORT_FORWARD_PID=$!

    # Give it a moment to establish connection
    sleep 2

    # Check if port forward is successful
    if ! ps -p $PORT_FORWARD_PID > /dev/null; then
        log "Error: Port forwarding failed to start"
        return 1
    fi

    log "Port forwarding established with PID: ${PORT_FORWARD_PID}"
    return 0
}

# Function to check if the port forwarding is working
check_port_forward() {
    # For services without HTTP endpoints or with auth requirements like Minio
    if [ -z "$PING_URL" ]; then
        # Check if the port is listening
        if command -v nc >/dev/null 2>&1; then
            if nc -z localhost ${LOCAL_PORT} >/dev/null 2>&1; then
                log "Port forward is working - port ${LOCAL_PORT} is open"
                return 0
            else
                log "Connection failed - port ${LOCAL_PORT} is not open"
                return 1
            fi
        else
            # If nc is not available, try lsof
            if command -v lsof >/dev/null 2>&1; then
                if lsof -i:${LOCAL_PORT} >/dev/null 2>&1; then
                    log "Port forward is working - port ${LOCAL_PORT} is open"
                    return 0
                else
                    log "Connection failed - port ${LOCAL_PORT} is not open"
                    return 1
                fi
            else
                # If neither nc nor lsof is available, just check if the process is running
                if ps -p $PORT_FORWARD_PID > /dev/null; then
                    log "Port forward process is still running"
                    return 0
                else
                    log "Port forward process is not running"
                    return 1
                fi
            fi
        fi
    else
        # For services with HTTP endpoints
        local response_code
        # Use curl with a short timeout to prevent long waits
        response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "${PING_URL}" || echo "failed")

        if [[ "$response_code" =~ ^(200|302|301|303|307|308|403|0|failed)$ ]]; then
            if [[ "$response_code" == "failed" ]]; then
                log "Connection failed - no response"
                return 1
            elif [[ "$response_code" == "0" ]]; then
                log "Connection failed - empty response"
                return 1
            elif [[ "$response_code" == "403" ]]; then
                # For 403 responses, this means the server is up but authentication failed
                # This is actually a successful connection for our purposes
                log "Port forward is working - received HTTP ${response_code} (authentication required)"
                return 0
            else
                # Any HTTP response code indicates the port forward is working
                log "Port forward is working - received HTTP ${response_code}"
                return 0
            fi
        else
            log "Unexpected status code: ${response_code}"
            # Consider this a success anyway if we got any response
            log "But got a response, so port forward is working"
            return 0
        fi
    fi
}

# Function to clean up resources
cleanup() {
    log "Cleaning up resources..."
    if [ ! -z "$PORT_FORWARD_PID" ]; then
        log "Killing port forwarding process (PID: ${PORT_FORWARD_PID})"
        kill $PORT_FORWARD_PID 2>/dev/null || true
    fi
    log "Cleanup complete, exiting"
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM

# Main loop
log "Starting port forwarding monitor script for $1"

# First, wait for the helm installation
if ! wait_for_helm_installation; then
    log "Failed to find servicex helm installation after multiple attempts"
    log "Please check if the servicex helm chart is properly installed"
    exit 1
fi

while true; do
    # Get pod name
    if ! get_pod_name "$1"; then
        log "Retrying in 5 seconds..."
        sleep 5
        continue
    fi

    # Start port forwarding
    if ! start_port_forward "$1"; then
        log "Retrying in 5 seconds..."
        sleep 5
        continue
    fi

    # Monitor port forwarding
    while true; do
        if ! check_port_forward "$1"; then
            log "Port forward appears to be down, restarting..."

            # Kill existing port forward process if it exists
            if [ ! -z "$PORT_FORWARD_PID" ]; then
                kill $PORT_FORWARD_PID 2>/dev/null || true
                unset PORT_FORWARD_PID
            fi

            break
        fi

        # Wait before checking again
        sleep $PING_INTERVAL
    done
done