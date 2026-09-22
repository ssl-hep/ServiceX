FROM sslhep/rucio-client:main

LABEL maintainer="Ilija Vukotic <ivukotic@uchicago.edu>"

# Create app directory
WORKDIR /opt/servicex

# Create celery user. Assign them to group zero since that is the group OpenShift will run the container as
RUN useradd -g 0 -ms /bin/bash celery

# for CA certificates
RUN mkdir -p /etc/grid-security/certificates /etc/grid-security/vomsdir

RUN yum clean all
RUN yum -y update

# Okay, change our shell to specifically use our software collections.
# (default was SHELL [ "/bin/sh", "-c" ])
# https://docs.docker.com/engine/reference/builder/#shell

ENV POETRY_VERSION=2.1.1

# Use python3.11 by name, not `python3`. The base image points /usr/bin/python3 at
# python3.11, but that path belongs to AlmaLinux's python3 (3.9) rpm, so the `yum -y
# update` above hands it back to 3.9 -- which has no pip. pyproject requires ^3.11
# anyway, so name the interpreter we actually want.
RUN python3.11 -m pip install --upgrade pip

RUN python3.11 -m pip install poetry==$POETRY_VERSION
RUN mkdir -p /opt/servicex/pypoetry
COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

ENV XDG_CONFIG_HOME=/opt/servicex
RUN poetry config virtualenvs.in-project true
RUN poetry install --no-root --no-interaction --no-ansi

COPY . .

# Change ownership of the app directory to celery user. Also set the group to zero since
# that is the group OpenShift will run the container as
RUN chown -R celery:0 /opt/servicex
RUN chmod -R g=u /opt/servicex

ENV X509_USER_PROXY=/tmp/grid-security/x509up
ENV X509_CERT_DIR=/etc/grid-security/certificates
ENV PYTHONPATH=/opt/servicex/src

ENV BROKER_URL="amqp://guest:guest@localhost:5672//"

# Switch to celery user
USER celery

ENTRYPOINT [ "scripts/start_celery_worker.sh"]
