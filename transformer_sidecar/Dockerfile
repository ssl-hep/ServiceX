FROM ubuntu:18.04

WORKDIR /servicex

RUN apt-get update && \
    apt-get install --reinstall -y build-essential \
    -y python3-pip && \
    ln -s /usr/bin/python3 /usr/bin/python

COPY requirements.txt .
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install -r requirements.txt

# Turn this on so that stdout isn't buffered - otherwise logs in kubectl don't
# show up until much later!
ENV PYTHONUNBUFFERED=1

# Copy over the source
COPY transformer.py \
     validate_requests.py \
     scripts/proxy-exporter.sh \
     scripts/watch.sh \
     ./

ENV X509_USER_PROXY=/tmp/grid-security/x509up
ENV X509_CERT_DIR /etc/grid-security/certificates

RUN useradd -ms /bin/bash output -G sudo && passwd -d output
RUN chgrp -R 0 /home/output && chmod -R g+rwX /home/output
