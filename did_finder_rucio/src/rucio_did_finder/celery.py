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

__log = logging.getLogger(__name__)

cache_prefix = os.environ.get('CACHE_PREFIX', '')
# Initialize the finder
did_client = DIDClient()
replica_client = ReplicaClient()
rucio_adapter = RucioAdapter(did_client, replica_client, False)

app = DIDFinderApp('rucio', did_finder_args={"rucio_adapter": rucio_adapter})


def find_files(did_name, info, did_finder_args):
    lookup_request = LookupRequest(
        did=did_name,
        rucio_adapter=did_finder_args['rucio_adapter'],
        dataset_id=info['dataset-id']
    )
    for file in lookup_request.lookup_files():
        yield file


@app.did_lookup_task(name="did_finder_rucio.lookup_dataset")
def lookup_dataset(self, did: str, dataset_id: int, endpoint: str) -> None:
    self.do_lookup(did=did, dataset_id=dataset_id,
                   endpoint=endpoint, user_did_finder=find_files)
