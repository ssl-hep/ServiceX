FROM rucio/rucio-clients:latest

USER root

# Create app directory
WORKDIR /usr/src/app

# for CA certificates

RUN mkdir -p /etc/grid-security/certificates /etc/grid-security/vomsdir

RUN yum -y update

RUN yum install -y https://repo.opensciencegrid.org/osg/3.5/osg-3.5-el7-release-latest.rpm

RUN yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm; \
    curl -s -o /etc/pki/rpm-gpg/RPM-GPG-KEY-wlcg http://linuxsoft.cern.ch/wlcg/RPM-GPG-KEY-wlcg; \
    curl -s -o /etc/yum.repos.d/wlcg-centos7.repo http://linuxsoft.cern.ch/wlcg/wlcg-centos7.repo;

RUN yum install osg-ca-certs voms voms-clients wlcg-voms-atlas wlcg-voms-cms fetch-crl -y

ENV POETRY_VERSION=1.2.2
RUN python3 -m pip install --upgrade pip

RUN pip install poetry==$POETRY_VERSION
COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

RUN poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

COPY . .

# build
RUN echo "Timestamp:" `date --utc` | tee /image-build-info.txt

ENV X509_USER_PROXY /tmp/x509up

CMD sh -c "python3 x509_updater.py --voms $VOMS"
