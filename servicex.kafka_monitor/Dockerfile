FROM python:3

LABEL maintainer Ilija Vukotic <ivukotic@cern.ch>

# Create app directory
WORKDIR /usr/src/app

COPY . .

RUN pip install confluent-kafka requests

CMD [ "python", "monitor.py" ]