FROM python:3

# Create app directory
WORKDIR /usr/src/app

# for CA certificates
USER root
RUN mkdir -p /etc/grid-security/certificates /etc/grid-security/vomsdir

ENV POETRY_VERSION=1.2.2
RUN python3 -m pip install --upgrade pip

RUN pip install poetry==$POETRY_VERSION
COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

RUN poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

COPY . .

ENV X509_USER_PROXY /tmp/grid-security/x509up
ENV X509_CERT_DIR /etc/grid-security/certificates

