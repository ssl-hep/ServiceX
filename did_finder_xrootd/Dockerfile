FROM python:3.10

LABEL maintainer Peter Onyisi <ponyisi@utexas.edu>

# Create app directory
WORKDIR /usr/src/app

# for CA certificates
USER root

ENV  POETRY_VERSION=1.5.1

# There is a bug in poetry with no virtual env where it can delete this package
# during install. If we delete it before installing poetry it will
# recognize it as its own and handle it correctly
# See: https://github.com/python-poetry/poetry/issues/5977
#RUN pip uninstall -y certifi

RUN apt-get update && \
    apt-get install cmake --no-install-recommends --assume-yes

RUN pip install poetry==$POETRY_VERSION

COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

RUN poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

# Bring over the main scripts
COPY . .

# build stamp
RUN echo "Timestamp:" `date --utc` | tee /image-build-info.txt

# Make sure python isn't buffered
ENV PYTHONUNBUFFERED=1

# Needed for running as non-root
ENV POETRY_CACHE_DIR=/root/.cache/pypoetry
ENV PYTHONPATH /usr/src/app/src

ENV BROKER_URL="amqp://guest:guest@localhost:5672//"
ENTRYPOINT [ "scripts/start_celery_worker.sh"]
