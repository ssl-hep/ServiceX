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

from rucio_ops import parse_did, list_files_for_did, \
    DIDSummary, find_replicas, get_sel_path
from rucio.client import DIDClient, ReplicaClient
import argparse


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


def process_static_file(file_path):
    """
    For testing and demo purposes, bypass rucio and generate a fake entry for
    a local file
    :param file_path:
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

# Gobble up the rest of the args as a list of DIDs
parser.add_argument('did_list', nargs='*')

args = parser.parse_args()


site = args.site

request_id = 'cli'


# Is this a test run where we serve up a particular file instead of hitting the
# real rucio service?
if args.static_file:
    summary = process_static_file(args.static_file)
else:
    dc = DIDClient()
    rc = ReplicaClient()

    summary = process_did_list(args.did_list, site, dc, rc)

print(summary)

if args.output_file:
    with open(args.output_file, 'w') as f:
        json.dump(summary.file_results, f)
else:
    print(summary.file_results)


