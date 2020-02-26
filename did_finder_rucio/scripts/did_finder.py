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
import traceback

import time
from rucio.client import DIDClient, ReplicaClient
import argparse
import pika

from servicex.did_finder.lookup_request import LookupRequest
from servicex.did_finder.rucio_adapter import RucioAdapter
from servicex.did_finder.servicex_adapter import ServiceXAdapter


parser = argparse.ArgumentParser()
parser.add_argument('--site', dest='site', action='store',
                    default=None,
                    help='XCache Site)')

parser.add_argument('--prefix', dest='prefix', action='store',
                    default='',
                    help='Prefix to add to Xrootd URLs')

parser.add_argument('--staticfile', dest='static_file', action='store',
                    default=None,
                    help='Static Root file to serve up)')

parser.add_argument('--outfile', dest='output_file', action='store',
                    default=None,
                    help='Filename to output list of Root files to')

parser.add_argument('--rabbit-uri', dest="rabbit_uri", action='store',
                    default='host.docker.internal')

parser.add_argument('--max-workers', dest='max_workers', action='store',
                    default=10, type=int)

# Gobble up the rest of the args as a list of DIDs
parser.add_argument('did_list', nargs='*')


def process_did_list(did_list, site, did_client, replica_client):
    pass


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
            threads=5
        )

        lookup_request.lookup_files()

    except Exception:
        traceback.print_exc()
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def init_rabbit_mq(rabbitmq_url, retries, retry_interval):
    rabbitmq = None
    retry_count = 0

    while not rabbitmq:
        try:
            rabbitmq = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
            _channel = rabbitmq.channel()
            _channel.queue_declare(queue='did_requests')

            print("Connected to RabbitMQ. Ready to start consuming requests")

            _channel.basic_consume(queue='did_requests',
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


args = parser.parse_args()

site = args.site
prefix = args.prefix

sample_request_id = 'cli'

# Is this a test run where we serve up a particular file instead of hitting the
# real Rucio service?
if args.static_file:
    rucio_adapter = None
else:
    did_client = DIDClient()
    replica_client = ReplicaClient()
    rucio_adapter = RucioAdapter(did_client, replica_client)

# If no DIDs on the command line then start up as server and await requests
if not args.did_list:
    init_rabbit_mq(args.rabbit_uri, retries=12, retry_interval=10)


summary = process_did_list(args.did_list, site, did_client, replica_client)

print(summary)

if args.output_file:
    with open(args.output_file, 'w') as f:
        json.dump(summary.file_results, f)
else:
    print(summary.file_results)
