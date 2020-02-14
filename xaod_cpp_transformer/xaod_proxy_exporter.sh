#!/usr/bin/env bash
sudo mkdir -p /etc/grid-security
sudo chown atlas /etc/grid-security


while true; do
    sudo cp /etc/grid-security-ro/x509up /etc/grid-security
    sudo chown atlas /etc/grid-security/x509up
    chmod 600 /etc/grid-security/x509up

    # Refresh every hour
    sleep 3600

done