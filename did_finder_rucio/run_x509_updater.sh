#!/bin/sh

# Assume that the passphrase the secures the grid cert is found in a file
# called /servicex/secrets.txt
# This should be mounted into the docker container


CERTPATH=/etc/grid-certs

while true; do 

  # update proxy
  voms-proxy-init --pwstdin -key $CERTPATH/userkey.pem \
                  -cert $CERTPATH/usercert.pem \
                  --voms=atlas \
                  <  /servicex/secrets.txt

  sleep 21600

  # update crls
  /usr/sbin/fetch-crl

done