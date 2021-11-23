# Copyright (c) 2019, IRIS-HEP
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# this code gets requests in state: Created, Validates request on one file
# if request valid (all branches exist) it sets request state to Defined
# if not it sets state to Failed, deletes all the paths belonging to that request.

import datetime
import json
import logging
import os
import sys
import time

import requests
import argparse
import pika

# What is the largest message we want to send (in megabytes).
# Note this must be less than the kafka broker setting if we are using kafka
default_max_message_size = 14.5

parser = argparse.ArgumentParser(
    description='Validate a request and create kafka topic.')

parser.add_argument('--rabbit-uri', dest="rabbit_uri", action='store',
                    default='host.docker.internal')

parser.add_argument('--avg-bytes', dest="avg_bytes_per_column", action='store',
                    help='Average number of bytes per column per event',
                    default='40')

parser.add_argument("--path", dest='path', action='store',
                    default=None,
                    help='Path to single Root file to transform')

parser.add_argument("--tree", dest='tree', action='store',
                    default="Events",
                    help='Tree from which columns will be inspected')


# function to initialize logging
def initialize_logging(request=None):
    """
    Get a logger and initialize it so that it outputs the correct format

    :param request: Request id to insert into log messages
    :return: logger with correct formatting that outputs to console
    """

    log = logging.getLogger()
    if 'INSTANCE_NAME' in os.environ:
        instance = os.environ['INSTANCE_NAME']
    else:
        instance = 'Unknown'
    formatter = logging.Formatter('%(levelname)s ' +
                                  "{} uproot_transformer {} ".format(instance, request) +
                                  '%(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    return log


def validate_request(file_name):
    print("Validating file: " + file_name)

    try:
        return(True, {
            "max-event-size": 0
        })
    except Exception as eek:
        logger.exception("Could not compile generated code: {}".format(eek))
        return False, "Could not compile generated code "+str(eek)


def post_status_update(endpoint, status_msg):
    requests.post(endpoint + "/status", data={
        "timestamp": datetime.datetime.now().isoformat(),
        "status": status_msg
    })


def post_transform_start(endpoint, info):
    requests.post(endpoint+"/start", json={
        "timestamp": datetime.datetime.now().isoformat(),
        "info": info
    })


def callback(channel, method, properties, body):
    validation_request = json.loads(body)

    service_endpoint = validation_request[u'service-endpoint']
    logger.info("Validation request received")
    post_status_update(service_endpoint,
                       "Validation Request received")

    # checks the file
    (valid, info) = validate_request(validation_request[u'file-path'])

    if valid:
        logger.info("Request validated")
        post_status_update(service_endpoint,  "Request validated")
        post_transform_start(service_endpoint, info)
    else:
        logger.error("Validation Request failed " + info)
        post_status_update(service_endpoint, "Validation Request failed "+info)

    print(valid, info)
    channel.basic_ack(delivery_tag=method.delivery_tag)


def init_rabbit_mq(rabbitmq_url, retries, retry_interval):
    rabbitmq = None
    retry_count = 0

    while not rabbitmq:
        try:
            rabbitmq = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
            _channel = rabbitmq.channel()
            _channel.queue_declare(queue='validation_requests')

            logger.info("Connected to RabbitMQ. Ready to start consuming requests")

            _channel.basic_consume(queue='validation_requests',
                                   auto_ack=False,
                                   on_message_callback=callback)
            _channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as eek:
            rabbitmq = None
            retry_count += 1
            if retry_count < retries:
                logger.error("Failed to connect to RabbitMQ (attempt {}). ".format(retry_count) +
                             "Waiting before trying again.")
                time.sleep(retry_interval)
            else:
                logger.error("Failed to connect to RabbitMQ. Giving Up")
                raise eek


if __name__ == "__main__":
    args = parser.parse_args()
    logger  = initialize_logging()
    if args.path:
        # checks the file
        (valid, info) = validate_request(args.path)
        logger.info(valid, info)
        sys.exit(0)

    init_rabbit_mq(args.rabbit_uri, retries=12, retry_interval=10)
