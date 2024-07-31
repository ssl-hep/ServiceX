FROM python:3.10

LABEL maintainer="Peter Onyisi <ponyisi@utexas.edu>"

# Create app directory
WORKDIR /usr/src/app

# Create celery user
RUN useradd -ms /bin/bash celery

ENV  POETRY_VERSION=1.5.1

RUN apt-get update && \
    apt-get install cmake --no-install-recommends --assume-yes

RUN pip install poetry==$POETRY_VERSION

COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

# Change ownership of the app directory to celery user
RUN chown -R celery:celery /usr/src/app

# Switch to celery user
USER celery

RUN  poetry install --no-root --no-interaction --no-ansi

# Bring over the main scripts
COPY . .


# Make sure python isn't buffered
ENV PYTHONUNBUFFERED=1

ENV PYTHONPATH=/usr/src/app/src

ENV BROKER_URL="amqp://guest:guest@localhost:5672//"


ENTRYPOINT [ "scripts/start_celery_worker.sh"]
