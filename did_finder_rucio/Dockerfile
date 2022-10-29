FROM ivukotic/rimage:latest

LABEL maintainer Ilija Vukotic <ivukotic@cern.ch>

# Create app directory
WORKDIR /usr/src/app

# for CA certificates
USER root
RUN mkdir -p /etc/grid-security/certificates /etc/grid-security/vomsdir 

RUN yum clean all
RUN yum -y update

# Okay, change our shell to specifically use our software collections.
# (default was SHELL [ "/bin/sh", "-c" ])
# https://docs.docker.com/engine/reference/builder/#shell

COPY requirements.txt requirements.txt

RUN python3.9 -m pip install -r requirements.txt

COPY . .

# build  
RUN echo "Timestamp:" `date --utc` | tee /image-build-info.txt

ENV X509_USER_PROXY /tmp/grid-security/x509up
ENV X509_CERT_DIR /etc/grid-security/certificates
