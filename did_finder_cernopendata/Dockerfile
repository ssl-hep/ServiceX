FROM cernopendata/cernopendata-client:0.3.0

LABEL maintainer Gordon Watts <gwatts@uw.edu>

# Create app directory
WORKDIR /usr/src/app

# for CA certificates
USER root

ENV  POETRY_VERSION=1.5.1
#ENV POETRY_HOME=/opt/poetry
#RUN python3 -m venv $POETRY_HOME && \
#    $POETRY_HOME/bin/pip install poetry==$POETRY_VERSION


# There is a bug in poetry with no virtual env where it can delete this package
# during install. If we delete it before installing poetry it will
# recognize it as its own and handle it correctly
# See: https://github.com/python-poetry/poetry/issues/5977
#RUN pip uninstall -y certifi

RUN pip install poetry==$POETRY_VERSION

COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

#RUN poetry config virtualenvs.create false
RUN poetry install --no-root --no-interaction --no-ansi

# Bring over the main scripts
COPY src/did_finder_cernopendata .

# build stamp
RUN echo "Timestamp:" `date --utc` | tee /image-build-info.txt

# Make sure python isn't buffered
ENV PYTHONUNBUFFERED=1

# Needed for running as non-root
ENV POETRY_CACHE_DIR=/root/.cache/pypoetry

ENTRYPOINT [ "poetry", "run", "python", "/usr/src/app/did_finder.py" ]
