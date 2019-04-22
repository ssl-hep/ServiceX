FROM rucio:rucio-clients

LABEL maintainer Ilija Vukotic <ivukotic@cern.ch>

# Create app directory
WORKDIR /usr/src/app

RUN mkdir -p /opt/rucio/etc
COPY rucio.cfg /opt/rucio/etc/

# build  
RUN echo "Timestamp:" `date --utc` | tee /image-build-info.txt

CMD [ "/runme.sh" ]

