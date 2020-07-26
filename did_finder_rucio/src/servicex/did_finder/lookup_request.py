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
import math
import threading
import traceback
from asyncio import Queue

from servicex.did_finder.rucio_adapter import RucioAdapter
from .did_summary import DIDSummary
from datetime import datetime


class LookupRequest:
    def __init__(self, request_id, did, rucio_adapter, servicex_adapter, site=None,
                 prefix='', chunk_size=1000, threads=1):
        self.request_id = request_id
        self.servicex_adapter = servicex_adapter
        self.did = did
        self.site = site
        self.prefix = prefix
        self.rucio_adapter = rucio_adapter

        self.summary = DIDSummary(did)
        self.summary_lock = threading.Lock()

        self.file_list = []
        self.lookup_threads = []
        self.chunk_size = chunk_size
        self.num_threads = threads
        self.replica_lookup_queue = None

        self.sample_submitted = False
        self.sample_submitted_lock = threading.Lock()

        self.submited_time = datetime.now()
        self.lookup_time = None
        self.replica_lookup_complete = None

    # Yield successive n-sized
    # chunks from file list.
    def chunks(self):
        # looping till length of file list
        for i in range(0, len(self.file_list), self.chunk_size):
            yield self.file_list[i:i + self.chunk_size]

    def report_lookup_complete(self):
        elapsed_time = self.replica_lookup_complete - self.submited_time
        self.servicex_adapter.put_fileset_complete(
            {
                "files": self.summary.files,
                "files-skipped": self.summary.files_skipped,
                "total-events": self.summary.total_events,
                "total-bytes": self.summary.total_bytes,
                "elapsed-time": int(elapsed_time.total_seconds())
            }
        )

        self.servicex_adapter.post_status_update("Fileset load complete in " + str(
            self.replica_lookup_complete - self.submited_time))

        print(self.summary)
        print("Complete time = ", self.replica_lookup_complete - self.submited_time)

    def replica_lookup(self):
        while not self.replica_lookup_queue.empty():
            try:
                chunk = self.replica_lookup_queue.get_nowait()
                tick = datetime.now()
                replicas = list(self.rucio_adapter.find_replicas(chunk, self.site))
                tock = datetime.now()
                print("Read %d replicas in %s" % (len(replicas), str(tock-tick)))

                # Opportunistically prepare a sample file to submit to serviceX. At the end of
                # this loop we will do a single thread-safe check to see if the sample has been
                # sent.
                sample_replica = None
                for r in replicas:
                    sel_path = RucioAdapter.get_sel_path(r, self.prefix, self.site)
                    if sel_path:
                        data = {
                            'req_id': self.request_id,
                            'adler32': r['adler32'],
                            'file_size': r['bytes'],
                            'file_events': 0,
                            'file_path': sel_path
                        }

                        self.servicex_adapter.put_file_add(data)

                        if not sample_replica:
                            sample_replica = data

                        with self.summary_lock:
                            self.summary.accumulate(data)
                            self.summary.add_file(data)

                            if len(self.file_list) - self.summary.files == 0:
                                self.replica_lookup_complete = datetime.now()
                                self.report_lookup_complete()

                tock2 = datetime.now()
                print("Files submitted to serviceX in ", tock2 - tock)

                with self.sample_submitted_lock:
                    if not self.sample_submitted:
                        self.servicex_adapter.post_preflight_check(sample_replica)
                        print("Submitted Sample file ", sample_replica)
                        self.sample_submitted = True

            except Exception:
                traceback.print_exc()

    def lookup_files(self):
        file_iterator = self.rucio_adapter.list_files_for_did(self.did)
        if not file_iterator:
            self.servicex_adapter.post_status_update(
                "DID Not found "+self.did,
                severity='fatal')
            return

        self.file_list = list(file_iterator)
        self.lookup_time = datetime.now()

        print("Dataset contains %d files. Lookup took %s" % (
            len(self.file_list),
            str(self.lookup_time-self.submited_time)
        ))

        if len(self.file_list) == 0:
            self.servicex_adapter.post_status_update(
                "DID Finder found zero files for dataset "+self.did,
                severity='fatal')
            return

        for file in self.file_list:
            self.summary.accumulate(file)
        print(self.summary)

        self.replica_lookup_queue = Queue(math.ceil(len(self.file_list) / self.chunk_size))

        for chunk in self.chunks():
            file_list = [{'scope': file['scope'], 'name': file['name']} for file in chunk]
            self.replica_lookup_queue.put_nowait(file_list)

        self.lookup_threads = [
            threading.Thread(target=self.replica_lookup)
            for i in range(self.num_threads)]

        for thread in self.lookup_threads:
            thread.start()
