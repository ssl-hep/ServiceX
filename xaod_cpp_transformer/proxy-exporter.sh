#!/usr/bin/env bash
mkdir -p /etc/grid-security


while true; do

    date

    while true; do 
        cp /etc/grid-security-ro/x509up /etc/grid-security
        RESULT=$?
        if [ $RESULT -eq 0 ]; then
            echo "Got proxy."
            chmod 600 /etc/grid-security/x509up
            break 
        else
            echo "Warning: An issue encountered when getting proxy."
            sleep 5
        fi
    done

    # Refresh every 10 hours.
    sleep 36000

done