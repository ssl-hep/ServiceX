FROM debian:trixie

LABEL maintainer="Peter Onyisi <ponyisi@utexas.edu>"

# Create app directory
WORKDIR /opt/servicex

# Create celery user. Assign them to group zero since that is the group OpenShift will run the container as
RUN useradd -g 0 -ms /bin/bash celery

ENV  POETRY_VERSION=2.1.1

RUN apt-get update && \
    apt-get install cmake osg-ca-certs python3-poetry python3-dev build-essential uuid-dev libssl-dev --no-install-recommends --assume-yes

RUN mkdir -p /opt/servicex/pypoetry
COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

ENV XDG_CONFIG_HOME=/opt/servicex
RUN poetry config virtualenvs.in-project true
RUN poetry install --no-root --no-interaction --no-ansi

# Bring over the main scripts
COPY . .

# Change ownership of the app directory to celery user. Also set the group to zero since
# that is the group OpenShift will run the container as
RUN chown -R celery:0 /opt/servicex
RUN chmod -R g=u /opt/servicex

# Switch to celery user
USER celery

# Make sure python isn't buffered
ENV PYTHONUNBUFFERED=1

ENV PYTHONPATH=/opt/servicex/src

ENV BROKER_URL="amqp://guest:guest@localhost:5672//"


ENTRYPOINT [ "scripts/start_celery_worker.sh"]
