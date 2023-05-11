FROM python:3.10

WORKDIR /servicex

RUN apt-get update && apt-get install -y jq

RUN python3 -m pip install --upgrade pip

ENV  POETRY_VERSION=1.2.2
RUN pip install poetry==$POETRY_VERSION

COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

RUN poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

# Turn this on so that stdout isn't buffered - otherwise logs in kubectl don't
# show up until much later!
ENV PYTHONUNBUFFERED=1

# Copy over the source
COPY src/ \
    scripts/proxy-exporter.sh \
    scripts/watch.sh \
    ./

ENV X509_USER_PROXY=/tmp/grid-security/x509up
ENV X509_CERT_DIR /etc/grid-security/certificates

RUN useradd -ms /bin/bash output -G sudo && passwd -d output
RUN chgrp -R 0 /home/output && chmod -R g+rwX /home/output
