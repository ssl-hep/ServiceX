FROM python:3

LABEL maintainer Ilija Vukotic <ivukotic@cern.ch>

RUN apt-get -y update && apt-get -y upgrade &&  apt-get -y dist-upgrade && apt-get autoremove
RUN apt-get -y install python3 python3-pip

RUN pip3 install redis requests

# Create app directory
WORKDIR /usr/src/app

COPY . .

CMD [ "python", "monitor.py" ]