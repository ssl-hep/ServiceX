FROM rucio/rucio-clients:latest

LABEL maintainer Ilija Vukotic <ivukotic@cern.ch>

# Create app directory
WORKDIR /usr/src/app

# for CA certificates

RUN mkdir -p /etc/grid-security/certificates /etc/grid-security/vomsdir 

RUN yum -y update
RUN yum localinstall https://repo.opensciencegrid.org/osg/3.4/osg-3.4-el7-release-latest.rpm -y

RUN yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm; \
    curl -s -o /etc/pki/rpm-gpg/RPM-GPG-KEY-wlcg http://linuxsoft.cern.ch/wlcg/RPM-GPG-KEY-wlcg; \
    curl -s -o /etc/yum.repos.d/wlcg-centos7.repo http://linuxsoft.cern.ch/wlcg/wlcg-centos7.repo;

RUN yum install osg-ca-certs voms voms-clients wlcg-voms-atlas fetch-crl -y

# We need python3 which is not part of the Rucio docker image
RUN yum install -y centos-release-scl && \
     yum install -y rh-python36

COPY . .

# Install rucio client in the python3 packages
RUN cat configure_python3.sh | scl enable rh-python36 --

# build  
RUN echo "Timestamp:" `date --utc` | tee /image-build-info.txt

ENV X509_USER_PROXY /etc/grid-security/x509up

CMD sh -c "/usr/src/app/run_x509_updater.sh & python /usr/src/app/request_lookup.py"

