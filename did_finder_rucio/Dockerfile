ARG BASE_IMAGE=sslhep/sx-rucio-voms:latest
FROM ${BASE_IMAGE}

LABEL maintainer Ilija Vukotic <ivukotic@cern.ch>

# Create app directory
WORKDIR /usr/src/app

# for CA certificates
USER root
RUN mkdir -p /etc/grid-security/certificates /etc/grid-security/vomsdir 

RUN yum clean all
RUN yum -y update

COPY requirements.txt requirements.txt

RUN python3 -m pip install -r requirements.txt

COPY . .

ENV X509_USER_PROXY /tmp/grid-security/x509up
ENV X509_CERT_DIR /etc/grid-security/certificates
