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
import logging
from typing import Optional
from aiostream import stream, pipe

from servicex.did_finder.rucio_adapter import RucioAdapter
from datetime import datetime


class LookupRequest:
    def __init__(self, did: str,
                 rucio_adapter: RucioAdapter,
                 site: Optional[str] = None,
                 prefix: str = '',
                 chunk_size: int = 1000,
                 threads: int = 1,
                 request_id: str = 'bogus-id'):
        '''Create the `LookupRequest` object that is responsible for returning
        lists of files. Processes things in chunks.

        Args:
            did (str): [description]
            rucio_adapter (RucioAdapter): [description]
            site (Optional[str], optional): [description]. Defaults to None.
            prefix (str, optional): [description]. Defaults to ''.
            chunk_size (int, optional): [description]. Defaults to 1000.
            threads (int, optional): [description]. Defaults to 1.
            request_id (str, optional): [description]. Defaults to 'bogus-id'.
        '''
        self.did = did
        self.site = site
        self.prefix = prefix
        self.rucio_adapter = rucio_adapter
        self.chunk_size = chunk_size
        self.num_threads = threads
        self.request_id = request_id

        # set logging to a null handler
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())

    def replica_lookup(self, chunk):

        # Do the lookup
        file_list = [{'scope': file['scope'], 'name': file['name']} for file in chunk]

        tick = datetime.now()
        replicas = list(self.rucio_adapter.find_replicas(file_list, self.site))
        tock = datetime.now()
        self.logger.info(f"Read {len(replicas)} replicas in {str(tock - tick)}",
                         extra={'requestId': self.request_id})

        # Translate all the replicas into a form that the did finder library
        # likes from the rucio returned metadata.
        did_replicas = [
                {
                    'adler32': r['adler32'],
                    'file_size': r['bytes'],
                    'file_events': 0,
                    'file_path': RucioAdapter.get_sel_path(r, self.prefix, self.site)
                }
                for r in replicas
        ]
        return did_replicas

    async def lookup_files(self):
        '''
        Run the file look up end-to-end.
        '''

        # Get the list of contents from rucio.
        lookup_start = datetime.now()
        file_iterator = self.rucio_adapter.list_files_for_did(self.did)
        lookup_finish = datetime.now()
        if not file_iterator:
            raise Exception(f'DID not found {self.did}')
        all_files = list(file_iterator)

        self.logger.info(f"Dataset contains {len(all_files)} files. " +
                         f"Lookup took {str(lookup_finish-lookup_start)}",
                         extra={'requestId': self.request_id})

        # Now we build a pipe-line to resolve into nearby replicas. The nearby replicas
        # should give us data locality and speed things up. To optimize the throughput,
        # we do the replica lookups in large chunks of files
        replicia_files = (stream.iterate(all_files)
                          | pipe.chunks(self.chunk_size)  # type:ignore
                          | pipe.map(self.replica_lookup, )  # type:ignore
                          )

        # Feed the info back as the chunk information is returned:
        async with replicia_files.stream() as streamer:
            async for chunk in streamer:
                for f in chunk:
                    yield f
