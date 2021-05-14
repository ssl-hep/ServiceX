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

import json
import sys
import traceback
import time
import argparse

from rucio.client.didclient import DIDClient
from rucio.client.replicaclient import ReplicaClient
import pika

from servicex.did_finder.lookup_request import LookupRequest
from servicex.did_finder.rucio_adapter import RucioAdapter
from servicex.did_finder.servicex_adapter import ServiceXAdapter

QUEUE_NAME = 'rucio_did_requests'

parser = argparse.ArgumentParser()
parser.add_argument('--site', dest='site', action='store',
                    default=None,
                    help='XCache Site)')

parser.add_argument('--prefix', dest='prefix', action='store',
                    default='',
                    help='Prefix to add to Xrootd URLs')

parser.add_argument('--rabbit-uri', dest="rabbit_uri", action='store',
                    default='host.docker.internal')

parser.add_argument('--threads', dest='threads', action='store',
                    default=10, type=int, help="Number of threads to spawn")

# Gobble up the rest of the args as a list of DIDs
parser.add_argument('did_list', nargs='*')


# RabbitMQ Queue Callback Method
def callback(channel, method, properties, body):
    try:
        did_request = json.loads(body)
        print("----> ", did_request)
        servicex = ServiceXAdapter(did_request['service-endpoint'])
        did = did_request['did']
        request_id = did_request['request_id']

        servicex.post_status_update("DID Request received")
        lookup_request = LookupRequest(
            request_id=request_id,
            did=did,
            rucio_adapter=rucio_adapter,
            servicex_adapter=servicex,
            site=site,
            prefix=prefix,
            chunk_size=1000,
            threads=threads
        )

        lookup_request.lookup_files()

    except Exception:
        traceback.print_exc()
        exc_type, exc_value, exc_traceback = sys.exc_info()
        servicex.post_status_update("DID Request failed " + str(exc_value))
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def init_rabbit_mq(rabbitmq_url, retries, retry_interval):
    rabbitmq = None
    retry_count = 0

    while not rabbitmq:
        try:
            rabbitmq = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
            _channel = rabbitmq.channel()
            _channel.queue_declare(queue=QUEUE_NAME)

            print("Connected to RabbitMQ. Ready to start consuming requests")

            _channel.basic_consume(queue=QUEUE_NAME,
                                   auto_ack=False,
                                   on_message_callback=callback)
            _channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as eek:
            rabbitmq = None
            retry_count += 1
            if retry_count < retries:
                print("Failed to connect to RabbitMQ. Waiting before trying again")
                time.sleep(retry_interval)
            else:
                print("Failed to connect to RabbitMQ. Giving Up")
                raise eek


# Main Script
args = parser.parse_args()

site = args.site
prefix = args.prefix
threads = args.threads
print("--------- ServiceX DID Finder ----------------")
print("Threads: " + str(threads))
print("Site: " + str(site))
print("Prefix: " + str(prefix))

did_client = DIDClient()
replica_client = ReplicaClient()
rucio_adapter = RucioAdapter(did_client, replica_client)

init_rabbit_mq(args.rabbit_uri, retries=12, retry_interval=10)
