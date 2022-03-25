FROM rucio/rucio-clients:latest

LABEL maintainer Ilija Vukotic <ivukotic@cern.ch>

# Create app directory
WORKDIR /usr/src/app

# for CA certificates
USER root
RUN mkdir -p /etc/grid-security/certificates /etc/grid-security/vomsdir 

RUN yum clean all
RUN yum -y update

RUN yum install -y https://repo.opensciencegrid.org/osg/3.5/osg-3.5-el7-release-latest.rpm

RUN yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm; \
    curl -s -o /etc/pki/rpm-gpg/RPM-GPG-KEY-wlcg http://linuxsoft.cern.ch/wlcg/RPM-GPG-KEY-wlcg; \
    curl -s -o /etc/yum.repos.d/wlcg-centos7.repo http://linuxsoft.cern.ch/wlcg/wlcg-centos7.repo;

RUN yum install osg-ca-certs voms voms-clients wlcg-voms-atlas fetch-crl -y

# Okay, change our shell to specifically use our software collections.
# (default was SHELL [ "/bin/sh", "-c" ])
# https://docs.docker.com/engine/reference/builder/#shell

COPY requirements.txt requirements.txt

RUN python3 -m pip install -r requirements.txt

COPY . .

# build  
RUN echo "Timestamp:" `date --utc` | tee /image-build-info.txt

ENV X509_USER_PROXY /tmp/grid-security/x509up
ENV X509_CERT_DIR /etc/grid-security/certificates
