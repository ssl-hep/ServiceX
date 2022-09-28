FROM cernopendata/cernopendata-client:0.2.0

LABEL maintainer Gordon Watts <gwatts@uw.edu>

# Create app directory
WORKDIR /usr/src/app

# for CA certificates
USER root
# RUN yum -y update

COPY requirements.txt requirements.txt
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install -r requirements.txt

RUN python3 -m pip list > /python_installed_packages.txt

# Bring over the main scripts
COPY src/servicex_did_finder_cernopendata .

# build stamp
RUN echo "Timestamp:" `date --utc` | tee /image-build-info.txt

# Make sure python isn't buffered
ENV PYTHONUNBUFFERED=1

ENTRYPOINT [ "python3", "/usr/src/app/did_finder.py" ]
