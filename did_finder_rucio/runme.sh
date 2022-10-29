#!/usr/bin/env bash

/usr/src/app/proxy-exporter.sh &

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

if [ -z $CACHE_PREFIX ]; then export PREFIX_ARG=""; else export PREFIX_ARG="--prefix $CACHE_PREFIX"; fi
export PYTHONPATH=.

# Assume $REPORT_LOGICAL_FILES is set to --report-logical-files to activate
echo "----------->$PYTHONPATH"
ls -lht $PYTHONPATH
python3.9 scripts/did_finder.py --rabbit-uri $RMQ_URI $PREFIX_ARG $REPORT_LOGICAL_FILES

