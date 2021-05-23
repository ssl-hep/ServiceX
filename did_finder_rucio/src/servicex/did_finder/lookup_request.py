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
from typing import Any, AsyncGenerator, Dict, List, Optional
from aiostream import stream, pipe

from servicex.did_finder.rucio_adapter import RucioAdapter
from datetime import datetime
import functools
import asyncio


async def to_thread(func, *args, **kwargs):
    """Asynchronously run function *func* in a separate thread.
    Any *args and **kwargs supplied for this function are directly passed
    to *func*. Also, the current :class:`contextvars.Context` is propogated,
    allowing context variables from the main thread to be accessed in the
    separate thread.
    Return a coroutine that can be awaited to get the eventual result of *func*.
    """
    loop = asyncio.get_event_loop()
    func_call = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, func_call)


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
            did (str): The DID we are going to lookup
            rucio_adapter (RucioAdapter): Thread safe rucio lookup object
            site (Optional[str], optional): Our site to improve locaity of rucio lookup.
                Defaults to None.
            prefix (str, optional): Prefix for xcache use. Defaults to ''.
            chunk_size (int, optional): How to chunk rucio replica lookup. Defaults to 1000.
            threads (int, optional): How many simultanious rucio lookups can run. Defaults to 1.
            request_id (str, optional): ServiceX Request ID that requested this DID.
                Defaults to 'bogus-id'.
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

    async def replica_lookup(self, chunk: List[Dict[str, str]]) \
            -> AsyncGenerator[Dict[str, Any], None]:
        '''Find the replicas for a chunk of files.

        Note that the file list comes in as a chunk, but we explode the results
        out to single files and pass them on as a sequence.

        Args:
            chunk (List[Dict[str, str]]): List file objects to lookup

        Yields:
            [AsyncGenerator(Dict[str, Any])]: List of files we've found
        '''

        # Do the lookup
        file_list = [{'scope': file['scope'], 'name': file['name']} for file in chunk]

        tick = datetime.now()
        found_replicants = to_thread(self.rucio_adapter.find_replicas,
                                     file_list, self.site)
        replicas = list(await found_replicants)
        tock = datetime.now()
        self.logger.info(f"Read {len(replicas)} replicas in {str(tock - tick)}",
                         extra={'requestId': self.request_id})

        # Translate all the replicas into a form that the did finder library
        # likes from the rucio returned metadata.
        for r in replicas:
            yield {
                'adler32': r['adler32'],
                'file_size': r['bytes'],
                'file_events': 0,
                'file_path': RucioAdapter.get_sel_path(r, self.prefix, self.site)
            }

    async def lookup_files(self):
        '''
        Run the file look up end-to-end.
        '''

        # Get the list of contents from rucio.
        lookup_start = datetime.now()
        file_iterator = await to_thread(self.rucio_adapter.list_files_for_did, self.did)
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
                          | pipe.map(self.replica_lookup,  # type:ignore
                                     task_limit=self.num_threads)
                          | pipe.flatten(task_limit=1)  # type:ignore
                          )

        # Feed the info back as the chunk information is returned:
        async with replicia_files.stream() as streamer:
            async for f in streamer:
                yield f
