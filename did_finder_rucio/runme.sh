#!/usr/bin/env bash

/usr/src/app/proxy-exporter.sh &


while true; do 
    date
    ls ${X509_USER_PROXY}
    RESULT=$?
    if [ $RESULT -eq 0 ]; then
        echo "Got proxy."
        break
    fi
    sleep 5
done

export PYTHONPATH=./src
python3 scripts/did_finder.py --rabbit-uri $RMQ_URI $SITE --threads $DID_THREADS

