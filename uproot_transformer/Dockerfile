# Build a docker image to run against ATLAS code that has been pre-built and is ready to go.

FROM atlas/analysisbase:21.2.102

# We need a messy bunch of stuff to make sure we can properly access GRID resources using
# x509 certs.
# WARNING: THis is for CentOS (modern versions of analysisbase)
# TODO: Ask about a better way to deal with this.
RUN sudo yum -y update

RUN sudo yum install -y https://repo.opensciencegrid.org/osg/3.5/osg-3.5-el7-release-latest.rpm
# RUN sudo yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm
RUN sudo curl -s -o /etc/pki/rpm-gpg/RPM-GPG-KEY-wlcg http://linuxsoft.cern.ch/wlcg/RPM-GPG-KEY-wlcg
RUN sudo curl -s -o /etc/yum.repos.d/wlcg-centos7.repo http://linuxsoft.cern.ch/wlcg/wlcg-centos7.repo; 
RUN sudo yum install -y xrootd-server xrootd-client xrootd \
    vomsxrd voms-clients wlcg-voms-atlas fetch-crl osg-ca-certs \
    xrootd-rucioN2N-for-Xcache

# Install everything needed to host/run the analysis jobs
RUN sudo mkdir -p /etc/grid-security/certificates /etc/grid-security/vomsdir
WORKDIR /home/atlas
COPY requirements.txt .
RUN source /home/atlas/release_setup.sh; \
    python2 -m pip install --user -r requirements.txt

# Turn this on so that stdout isn't buffered - otherwise logs in kubectl don't
# show up until much later!
ENV PYTHONUNBUFFERED=1
ENV X509_USER_PROXY=/etc/grid-security/x509up

# Copy over the source
COPY \
    transformer.py \
    validate_requests.py \
    proxy-exporter.sh \
    ./
