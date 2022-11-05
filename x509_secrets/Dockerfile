FROM sslhep/rucio-client:main

USER root

# Create app directory
WORKDIR /usr/src/app

# for CA certificates

RUN mkdir -p /etc/grid-security/certificates /etc/grid-security/vomsdir

RUN yum -y update

ENV POETRY_VERSION=1.2.2
RUN python3 -m pip install --upgrade pip

RUN pip install poetry==$POETRY_VERSION
COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

RUN poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

COPY . .

# build
RUN echo "Timestamp:" `date --utc` | tee /image-build-info.txt

ENV X509_USER_PROXY /tmp/x509up

CMD sh -c "python3 x509_updater.py --voms $VOMS"
