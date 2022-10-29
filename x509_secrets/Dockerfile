FROM ivukotic/rimage:latest

USER root

# Create app directory
WORKDIR /usr/src/app

# for CA certificates

RUN mkdir -p /etc/grid-security/certificates /etc/grid-security/vomsdir 

RUN yum -y update

COPY requirements.txt requirements.txt

RUN python3.9 -m pip install -r requirements.txt

COPY . .

# build  
RUN echo "Timestamp:" `date --utc` | tee /image-build-info.txt

ENV X509_USER_PROXY /tmp/x509up

CMD sh -c "python3.9 x509_updater.py --voms $VOMS"

