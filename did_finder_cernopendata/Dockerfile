FROM cernopendata/cernopendata-client:0.3.0

LABEL maintainer="Gordon Watts <gwatts@uw.edu>"

USER root

# Create app directory
WORKDIR /usr/src/app

# Create celery user
RUN useradd -ms /bin/bash celery

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
# Change ownership of the app directory to celery user
RUN chown -R celery:celery /usr/src/app

# Switch to celery user
USER celery

RUN  poetry install --no-root --no-interaction --no-ansi

# Make sure python isn't buffered
ENV PYTHONUNBUFFERED=1

ENV PYTHONPATH=/usr/src/app/src

ENV BROKER_URL="amqp://guest:guest@localhost:5672//"

ENTRYPOINT [ "scripts/start_celery_worker.sh"]
