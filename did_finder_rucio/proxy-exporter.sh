#!/usr/bin/env bash
mkdir -p /etc/grid-security

while true; do
    cp /etc/grid-security-ro/x509up /etc/grid-security
    chmod 600 /etc/grid-security/x509up

    # Refresh every hour
    sleep 3600

done