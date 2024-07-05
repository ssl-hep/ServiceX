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

import argparse
import logging

from rucio.client.didclient import DIDClient
from rucio.client.replicaclient import ReplicaClient
from rucio_did_finder.rucio_adapter import RucioAdapter
from servicex_did_finder_lib import DIDFinderApp
from rucio_did_finder.lookup_request import LookupRequest


def find_files(did_name, info, did_finder_args):
    lookup_request = LookupRequest(
        did=did_name,
        rucio_adapter=did_finder_args['rucio_adapter'],
        dataset_id=info['dataset-id']
    )
    for file in lookup_request.lookup_files():
        yield file


def run_rucio_finder():
    logger = logging.getLogger()

    # Parse the command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-logical-files", action="store_true")
    DIDFinderApp.add_did_finder_cnd_arguments(parser)

    args = parser.parse_args()

    logger.info("ServiceX DID Finder starting up. ")

    if args.report_logical_files:
        logger.info("---- DID Finder Only Returning Logical Names, not replicas -----")

    # Initialize the finder
    did_client = DIDClient()
    replica_client = ReplicaClient()
    rucio_adapter = RucioAdapter(did_client, replica_client, args.report_logical_files)

    # Sneak the run_query method into the args. These values will be made available to the task
    args.rucio_adapter = rucio_adapter

    # Run the DID Finder
    app = DIDFinderApp('rucio', parsed_args=args)

    @app.did_lookup_task(name="did_finder_rucio.lookup_dataset")
    def lookup_dataset(self, did: str, dataset_id: int, endpoint: str) -> None:
        self.do_lookup(did=did, dataset_id=dataset_id,
                       endpoint=endpoint, user_did_finder=find_files)
    app.start()


if __name__ == "__main__":
    run_rucio_finder()
