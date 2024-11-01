# Copyright (c) 2024, IRIS-HEP
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
import logging
import os

from rucio.client.didclient import DIDClient
from rucio.client.replicaclient import ReplicaClient

from rucio_did_finder.lookup_request import LookupRequest
from rucio_did_finder.rucio_adapter import RucioAdapter
from servicex_did_finder_lib import DIDFinderApp
from servicex_did_finder_lib.replica_distance_service import ReplicaSorter

__log = logging.getLogger(__name__)

cache_prefix = os.environ.get('CACHE_PREFIX', '')

location = None
if 'RUCIO_LATITUDE' in os.environ and 'RUCIO_LONGITUDE' in os.environ:
    location = {'latitude': float(os.environ['RUCIO_LATITUDE']),
                'longitude': float(os.environ['RUCIO_LONGITUDE'])
                }

# Initialize the finder
did_client = DIDClient()
replica_client = ReplicaClient()
rucio_adapter = RucioAdapter(did_client, replica_client, False)
if 'USE_REPLICA_SORTER' in os.environ:
    # will pick up configuration from environment
    replica_sorter = ReplicaSorter()
else:
    replica_sorter = None

app = DIDFinderApp('rucio', did_finder_args={"rucio_adapter": rucio_adapter})


def find_files(did_name, info, did_finder_args):
    lookup_request = LookupRequest(
        did=did_name,
        rucio_adapter=did_finder_args['rucio_adapter'],
        dataset_id=info['dataset-id']
    )
    for file_list in lookup_request.lookup_files():
        retval = []
        for file in file_list:
            r_file = file.copy()
            print('path before', r_file['paths'])
            if replica_sorter is not None and location is not None:
                r_file['paths'] = replica_sorter.sort_replicas(r_file['paths'], location)
            print('path after', r_file['paths'])
            retval.append(r_file)
        yield retval


@app.did_lookup_task(name="did_finder_rucio.lookup_dataset")
def lookup_dataset(self, did: str, dataset_id: int, endpoint: str) -> None:
    self.do_lookup(did=did, dataset_id=dataset_id,
                   endpoint=endpoint, user_did_finder=find_files)
