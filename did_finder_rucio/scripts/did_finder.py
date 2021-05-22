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
from typing import Any, AsyncGenerator, Dict

from rucio.client.didclient import DIDClient
from rucio.client.replicaclient import ReplicaClient
from servicex.did_finder.rucio_adapter import RucioAdapter
from servicex_did_finder_lib import default_command_line_args, start_did_finder
from servicex.did_finder.lookup_request import LookupRequest


async def find_files(rucio_adaptor: RucioAdapter, site: str, prefix: str, threads: int,
                     did_name: str) -> AsyncGenerator[Dict[str, Any], None]:
    '''For each incoming did name, generate a list of files that ServiceX can process
    from the rucio catalog

    Args:
        did_name (str): Rucio Dataset name

    Returns:
        AsyncGenerator[Dict[str, any], None]: yield each file
    '''

    lookup_request = LookupRequest(
        did=did_name,
        rucio_adapter=rucio_adaptor,
        site=site,
        prefix=prefix,
        chunk_size=1000,
        threads=threads
    )

    async for f in lookup_request.lookup_files():
        yield f


def run_rucio_finder():
    '''Run the rucio finder
    '''
    logger = logging.getLogger(__name__)

    # Parse the command line arguemnts
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', dest='site', action='store',
                        default=None,
                        help='XCache Site)')
    parser.add_argument('--prefix', dest='prefix', action='store',
                        default='',
                        help='Prefix to add to Xrootd URLs')
    parser.add_argument('--threads', dest='threads', action='store',
                        default=10, type=int, help="Number of threads to spawn")
    default_command_line_args(parser)

    args = parser.parse_args()

    site = args.site
    prefix = args.prefix
    threads = args.threads
    logger.info("ServiceX DID Finder starting up: "
                f"Threads: {threads} Site: {site} Prefix: {prefix}")

    # Initialize the finder
    did_client = DIDClient()
    replica_client = ReplicaClient()
    rucio_adapter = RucioAdapter(did_client, replica_client)

    # Run the DID Finder
    try:
        logger.info('Starting rucio DID finder')

        async def callback(did_name):
            async for f in find_files(rucio_adapter, site, prefix, threads, did_name):
                yield f

        start_did_finder('rucio',
                         callback,
                         parsed_args=args)

    finally:
        logger.info('Done running rucio DID finder')


if __name__ == "__main__":
    run_rucio_finder()
