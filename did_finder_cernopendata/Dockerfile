FROM cernopendata/cernopendata-client:0.3.0

LABEL maintainer="Gordon Watts <gwatts@uw.edu>"

USER root

# Create app directory
WORKDIR /opt/servicex

# Create celery user. Assign them to group zero since that is the group OpenShift will run the container as
RUN useradd -g 0 -ms /bin/bash celery

ENV  POETRY_VERSION=1.5.1

# There is a bug in poetry with no virtual env where it can delete this package
# during install. If we delete it before installing poetry it will
# recognize it as its own and handle it correctly
# See: https://github.com/python-poetry/poetry/issues/5977
RUN pip uninstall -y certifi

RUN pip install poetry==$POETRY_VERSION

COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

# Bring over the main scripts
COPY . .

ENV XDG_CONFIG_HOME=/opt/servicex
RUN poetry config virtualenvs.in-project true
RUN poetry install --no-root --no-interaction --no-ansi

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
