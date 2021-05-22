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
from aiostream import stream, pipe

from servicex.did_finder.rucio_adapter import RucioAdapter
from .did_summary import DIDSummary
from datetime import datetime


class LookupRequest:
    def __init__(self, did, rucio_adapter, site=None,
                 prefix='', chunk_size=1000, threads=1):
        self.did = did
        self.site = site
        self.prefix = prefix
        self.rucio_adapter = rucio_adapter
        self.chunk_size = chunk_size
        self.num_threads = threads

        self.summary = DIDSummary(did)

        # set logging to a null handler
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())

    # def report_lookup_complete(self):
    #     elapsed_time = self.replica_lookup_complete - self.submited_time
    #     lookup_info = {"files": self.summary.files,
    #                    "files-skipped": self.summary.files_skipped,
    #                    "total-events": self.summary.total_events,
    #                    "total-bytes": self.summary.total_bytes,
    #                    "elapsed-time": int(elapsed_time.total_seconds())}
    #     self.servicex_adapter.put_fileset_complete(lookup_info)

    #     self.servicex_adapter.post_status_update(f"Fileset load complete in {elapsed_time}")

    #     self.logger.info(self.summary, extra={'requestId': self.request_id})
    #     lookup_info['elapsed-time'] = elapsed_time.total_seconds()
    #     self.logger.info(f"Metric: {json.dumps(lookup_info)}",
    #                      extra={'requestId': self.request_id})

    def replica_lookup(self, chunk):

        # Do the lookup
        file_list = [{'scope': file['scope'], 'name': file['name']} for file in chunk]

        tick = datetime.now()
        replicas = list(self.rucio_adapter.find_replicas(file_list, self.site))
        tock = datetime.now()
        self.logger.info(f"Read {len(replicas)} replicas in {str(tock - tick)}")

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

        # tock2 = datetime.now()
        # self.logger.info(f"Files submitted to serviceX in {tock2 - tock}",
        #                     extra={'requestId': self.request_id})

        # This is weird because it seems to say - if we get a replica error, just keep going.
        # except Exception as e:
        #     self.logger.exception(f"Received exception while doing replica lookup: {e}",
        #                           extra={'requestId': self.request_id})

    async def lookup_files(self):
        '''
        Run the file look up end-to-end.
        '''

        # Get the list of contents from rucio
        file_iterator = self.rucio_adapter.list_files_for_did(self.did)
        if not file_iterator:
            raise Exception(f'DID not found {self.did}')

        # Now we build a pipe-line to resolve into nearby replicas. The nearby replicas
        # should give us data locality and speed things up. To optimize the throughput,
        # we do the replica lookups in large chunks of files
        all_files = stream.iterate(file_iterator)
        replicia_files = (all_files
                          | pipe.chunks(self.chunk_size)
                          | pipe.map(self.replica_lookup)
                          )

        # Feed the info back as the chunk information is returned:
        async with replicia_files.stream() as streamer:
            async for chunk in streamer:
                for f in chunk:
                    yield f

        # self.logger.info(f"Dataset contains {len(self.file_list)} files. " +
        #                  f"Lookup took {str(self.lookup_time-self.submited_time)}",
        #                  extra={'requestId': self.request_id})

        # for chunk in self.chunks():
        #     file_list = [{'scope': file['scope'], 'name': file['name']} for file in chunk]
        #     self.replica_lookup_queue.put_nowait(file_list)

        # self.lookup_threads = [
        #     threading.Thread(target=self.replica_lookup)
        #     for i in range(self.num_threads)]
