# Build a docker image to run against ATLAS code that has been pre-built and is ready to go.

FROM atlas/analysisbase:21.2.102

# We need a messy bunch of stuff to make sure we can properly access GRID resources using
# x509 certs
RUN sudo mkdir -p /etc/grid-security/certificates /etc/grid-security/vomsdir
RUN sudo yum -y update
# WARNING: This below is for centos - but if you go back far enough in time with analysis base, you'll end
# up in SLC6, and you'll need a different set of commands there.
RUN sudo yum localinstall https://repo.opensciencegrid.org/osg/3.4/osg-3.4-el7-release-latest.rpm -y
# RUN sudo yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm
RUN sudo curl -s -o /etc/pki/rpm-gpg/RPM-GPG-KEY-wlcg http://linuxsoft.cern.ch/wlcg/RPM-GPG-KEY-wlcg
RUN sudo curl -s -o /etc/yum.repos.d/wlcg-centos7.repo http://linuxsoft.cern.ch/wlcg/wlcg-centos7.repo

RUN sudo yum install -y xrootd-voms-plugin voms-clients wlcg-voms-atlas fetch-crl osg-ca-certs xrootd xrootd-client
# RUN sudo /usr/sbin/fetch-crl

# Ok - set everything up to run ATLAS stuff.
WORKDIR /home/atlas
COPY requirements.txt .
RUN source /home/atlas/release_setup.sh; \
    python2 -m pip install --user -r requirements.txt && \
    python2 -m pip install --user --index-url https://test.pypi.org/simple/ --no-deps servicex==0.2rc2

# Turn this on so that stdout isn't buffered - otherwise logs in kubectl don't
# show up until much later!
ENV PYTHONUNBUFFERED=1

# Copy over the source
COPY transformer.py .
COPY validate_requests.py .
COPY proxy-exporter.sh .
