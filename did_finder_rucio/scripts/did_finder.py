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
from servicex.did_finder.rucio_adapter import RucioAdapter
from servicex_did_finder_lib import add_did_finder_cnd_arguments, start_did_finder
from servicex.did_finder.lookup_request import LookupRequest


def run_rucio_finder():
    '''Run the rucio finder
    '''
    logger = logging.getLogger()

    # Parse the command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-logical-files", action="store_true")
    add_did_finder_cnd_arguments(parser)

    args = parser.parse_args()

    prefix = args.prefix

    logger.info("ServiceX DID Finder starting up. "
                f"Prefix: {prefix}")

    if args.report_logical_files:
        logger.info("---- DID Finder Only Returning Logical Names, not replicas -----")

    # Initialize the finder
    did_client = DIDClient()
    replica_client = ReplicaClient()
    rucio_adapter = RucioAdapter(did_client, replica_client, args.report_logical_files)

    # Run the DID Finder
    try:
        logger.info('Starting rucio DID finder')

        async def callback(did_name, info):
            lookup_request = LookupRequest(
                did=did_name,
                rucio_adapter=rucio_adapter,
                prefix=prefix,
                request_id=info['request-id']
            )
            for file in lookup_request.lookup_files():
                yield file

        start_did_finder('rucio',
                         callback,
                         parsed_args=args)

    finally:
        logger.info('Done running rucio DID finder')


if __name__ == "__main__":
    run_rucio_finder()
