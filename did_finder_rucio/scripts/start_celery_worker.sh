#!/usr/bin/env bash
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

poetry run celery --broker="$BROKER_URL" -A rucio_did_finder worker \
                  --loglevel=info -Q did_finder_rucio \
                  --concurrency=1 --hostname=did_finder_rucio@%h
