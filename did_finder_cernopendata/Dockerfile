FROM cernopendata/cernopendata-client:0.3.0

LABEL maintainer Gordon Watts <gwatts@uw.edu>

# Create app directory
WORKDIR /usr/src/app

# for CA certificates
USER root
# RUN yum -y update
ENV  POETRY_VERSION=1.2.2
RUN python3 -m pip install --upgrade pip

# There is a bug in poetry with no virtual env where it can delete this package
# during install. If we delete it before installing poetry it will
# recognize it as its own and handle it correctly
# See: https://github.com/python-poetry/poetry/issues/5977
RUN pip uninstall -y certifi

RUN pip install poetry==$POETRY_VERSION
COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

RUN poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

# Bring over the main scripts
COPY src/servicex_did_finder_cernopendata .

# build stamp
RUN echo "Timestamp:" `date --utc` | tee /image-build-info.txt

# Make sure python isn't buffered
ENV PYTHONUNBUFFERED=1

ENTRYPOINT [ "python3", "/usr/src/app/did_finder.py" ]
