FROM rucio/rucio-clients:latest

LABEL maintainer Ilija Vukotic <ivukotic@cern.ch>

# Create app directory
WORKDIR /usr/src/app

RUN mkdir -p /opt/rucio/etc
COPY rucio.cfg /opt/rucio/etc/


# for CA certificates

RUN mkdir -p /etc/grid-security/certificates /etc/grid-security/vomsdir /etc/grid-security/xrd

RUN yum -y update
RUN yum localinstall https://repo.opensciencegrid.org/osg/3.4/osg-3.4-el7-release-latest.rpm -y
RUN yum install -y fetch-crl 

COPY run_x509_updater.sh /.

# build  
RUN echo "Timestamp:" `date --utc` | tee /image-build-info.txt

CMD [ "/runme.sh" ]

