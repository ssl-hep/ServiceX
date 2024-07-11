FROM sslhep/rucio-client:main

LABEL maintainer Ilija Vukotic <ivukotic@uchicago.edu>

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

ENV X509_USER_PROXY /tmp/grid-security/x509up
ENV X509_CERT_DIR /etc/grid-security/certificates
ENV PYTHONPATH /usr/src/app/src

ENV BROKER_URL="amqp://guest:guest@localhost:5672//"
ENTRYPOINT [ "scripts/start_celery_worker.sh"]

