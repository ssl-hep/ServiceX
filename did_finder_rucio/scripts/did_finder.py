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
import threading
from concurrent.futures import ThreadPoolExecutor

import time

from rucio_ops import parse_did, list_files_for_did, \
    DIDSummary, find_replicas, get_sel_path
from rucio.client import DIDClient, ReplicaClient
import argparse
import pika
import requests
import datetime
import queue
global did_client, replica_client


def _replica_lookup_worker(input_queue, output_queue, request_id,  _replica_client):
    while not input_queue.empty():
        file = input_queue.get()
        replicas = find_replicas(file, site, _replica_client)

        for r in replicas:
            sel_path = get_sel_path(r)

            if sel_path:
                data = {
                    'req_id': request_id,
                    'adler32': file['adler32'],
                    'file_size': file['bytes'],
                    'file_events': file['events'],
                    'file_path': sel_path
                }
                output_queue.put(data)


def file_replicas(request_id, did, _did_client, _replica_client, max_workers = 10):
    replica_lookup_queue = queue.Queue()
    replica_output_queue = queue.Queue()
    files = list_files_for_did(parse_did(did), _did_client)

    num_files = 0
    for file in files:
        replica_lookup_queue.put(file)
        num_files = num_files + 1
    print("Rucio Request returned {} Files".format(num_files))

    executor = ThreadPoolExecutor(max_workers=max_workers)
    x = executor.submit(_replica_lookup_worker, replica_lookup_queue, replica_output_queue, request_id, _replica_client)

    while x.running() or not replica_output_queue.empty():
        yield replica_output_queue.get()


def process_did_list(dids, site, did_client, replica_client):

    for did in dids:
        print("---->", did)
        files = list_files_for_did(parse_did(did), did_client)
        result = DIDSummary(did)

        for file in files:
            print(file)
            result.accumulate(file)

            replicas = find_replicas(file, site, replica_client)

            for r in replicas:
                sel_path = get_sel_path(r)

                if sel_path:
                    data = {
                        'req_id': request_id,
                        'adler32': file['adler32'],
                        'file_size': file['bytes'],
                        'file_events': file['events'],
                        'file_path': sel_path
                    }

                    result.add_file(data)
                else:
                    result.files_skipped += 1
        return result


def process_static_file(file_path, request_id):
    """
    For testing and demo purposes, bypass rucio and generate a fake entry for
    a local file
    :param file_path:
    :param request_id:
    :return: A Summary object with the local file as the single entry
    """
    summary = DIDSummary("demo")
    summary.add_file(
        {
            'req_id': request_id,
            'adler32': 123456,
            'file_size': 100,
            'file_events': 1000,
            'file_path': file_path
        }
    )
    return summary


def post_status_update(endpoint, status_msg):
    requests.post(endpoint+"/status", data={
        "timestamp": datetime.datetime.now().isoformat(),
        "status": status_msg
    })


def put_file_add(endpoint, file_info):
    requests.put(endpoint + "/files", json={
        "timestamp": datetime.datetime.now().isoformat(),
        "file_path": file_info['file_path'],
        'adler32': file_info['adler32'],
        'file_size': file_info['file_size'],
        'file_events': file_info['file_events']
    })


def post_preflight_check(endpoint, file_entry):
    requests.post(endpoint + "/preflight", json={
        'file_path': file_entry['file_path']
    })


def put_fileset_complete(endpoint, summary):
    print("-------->Complete------> "+str(summary))
    requests.put(endpoint+"/complete", json=summary)


def submit_static_file(service_endpoint, request_id):
    root_file = {
        "file_path": args.static_file,
        'adler32': '123456',
        'file_size': 102444,
        'file_events': 10000
    }
    post_preflight_check(service_endpoint, root_file)

    put_file_add(service_endpoint, root_file)

    put_fileset_complete(service_endpoint, {
                           "files": 1,
                           "files-skipped": 0,
                           "total-events": 1000,
                           "total-bytes": 5000,
                           "elapsed-time": 1
                       })


def process_did_request(request_id, did, max_workers, service_endpoint):
    start_time = time.time()
    sample_file_submitted = False

    did_summary = DIDSummary(did)
    for root_file in file_replicas(request_id, did, did_client,
                                   replica_client, max_workers=max_workers):
        print(root_file)
        did_summary.accumulate(root_file)
        did_summary.add_file(root_file)

        if not sample_file_submitted:
            post_preflight_check(service_endpoint, root_file)
            sample_file_submitted = True

        put_file_add(service_endpoint, root_file)

    end_time = time.time()
    put_fileset_complete(service_endpoint, {
        "files": did_summary.files,
        "files-skipped": did_summary.files_skipped,
        "total-events": did_summary.total_events,
        "total-bytes": did_summary.total_bytes,
        "elapsed-time": end_time - start_time
    })

    post_status_update(service_endpoint,
                       "Fileset load complete in " + str(end_time - start_time) +
                       " seconds")


def callback(channel, method, properties, body):
    try:
        did_request = json.loads(body)
        print("----> ", did_request)
        service_endpoint = did_request['service-endpoint']
        did = did_request['did']
        request_id = did_request['request_id']

        post_status_update(service_endpoint, "DID Request received")

        if args.static_file:
            submit_static_file(service_endpoint, request_id)
        else:
            t = threading.Thread(target=process_did_request, args=(request_id, did,
                              args.max_workers, service_endpoint))
            t.start()
    except Exception as eek:
        print("\n\nShutting down due to error ", eek)
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


parser = argparse.ArgumentParser()
parser.add_argument('--site', dest='site', action='store',
                    default="MWT2",
                    help='XCache Site)')

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

args = parser.parse_args()

site = args.site

sample_request_id = 'cli'

# Is this a test run where we serve up a particular file instead of hitting the
# real Rucio service?
if args.static_file:
    did_client = None
    replica_client = None
else:
    did_client = DIDClient()
    replica_client = ReplicaClient()

# If no DIDs on the command line then start up as server and await requests
if not args.did_list:
    rabbitmq = pika.BlockingConnection(
        pika.URLParameters(args.rabbit_uri)
    )
    _channel = rabbitmq.channel()
    _channel.exchange_declare('transformation_requests')

    _channel.basic_consume(queue='did_requests',
                           auto_ack=False,
                           on_message_callback=callback)
    _channel.start_consuming()

summary = process_did_list(args.did_list, site, did_client, replica_client)

print(summary)

if args.output_file:
    with open(args.output_file, 'w') as f:
        json.dump(summary.file_results, f)
else:
    print(summary.file_results)


