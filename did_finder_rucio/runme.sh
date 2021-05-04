#!/usr/bin/env bash

/usr/src/app/proxy-exporter.sh &


while true; do 
    date
    ls /etc/grid-security/x509up
    RESULT=$?
    if [ $RESULT -eq 0 ]; then
        break
    fi
    echo "INFO $INSTANCE_NAME did-finder none Waiting for the proxy."
    sleep 5
done

export PYTHONPATH=./src
python3 scripts/did_finder.py --rabbit-uri $RMQ_URI $SITE --threads $DID_THREADS

