#!/bin/sh

# Need to install this - it will create and populate directory /etc/grid-security/certificates
yum install osg-ca-certs voms-clients wlcg-voms-atlas fetch-crl -y

CERTPATH=/etc/grid-certs

while true; do 

  # update proxy
  voms-proxy-init -key $CERTPATH/userkey.pem -cert $CERTPATH/usercert.pem --voms=atlas
  mv /tmp/x509up_u0 /etc/grid-security/x509up
  # chown ivukotic /etc/grid-security/x509up

  sleep 21600

  # update crls
  /usr/sbin/fetch-crl

done