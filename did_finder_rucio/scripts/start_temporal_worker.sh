#!/usr/bin/env bash
# Run the Rucio DID finder as a Temporal worker; the image's entrypoint.
/opt/servicex/proxy-exporter.sh &

while true; do
    date
    ls ${X509_USER_PROXY}
    RESULT=$?
    if [ $RESULT -eq 0 ]; then
        break
    fi
    echo "INFO $INSTANCE_NAME did-finder none Waiting for the proxy."
    sleep 5
done

# exec so the worker gets SIGTERM directly and drains in-flight lookups
exec /opt/servicex/.venv/bin/python -m rucio_did_finder.temporal_worker
