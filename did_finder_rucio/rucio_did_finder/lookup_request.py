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
import os
import logging
import json
import zlib
import base64
from datetime import datetime
from rucio_did_finder.rucio_adapter import RucioAdapter
from pymemcache.client.base import Client


class JsonSerde(object):
    def serialize(self, key, value):
        cv = base64.b64encode(
            zlib.compress(
                json.dumps(value).encode('utf-8')
            )
        ).decode('ascii')
        return cv, 1

    def deserialize(self, key, value, flags):
        return json.loads(zlib.decompress(base64.b64decode(value)))


class LookupRequest:
    def __init__(self, did: str,
                 rucio_adapter: RucioAdapter,
                 request_id: str = 'bogus-id'):
        '''Create the `LookupRequest` object that is responsible for returning
        lists of files. Processes things in chunks.

        Args:
            did (str): The DID we are going to lookup
            rucio_adapter (RucioAdapter): Rucio lookup object
            request_id (str, optional): ServiceX Request ID that requested this DID.
                Defaults to 'bogus-id'.
        '''
        self.did = did
        self.rucio_adapter = rucio_adapter
        self.request_id = request_id

        # set logging to a null handler
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())
        if os.getenv("MEMCACHE") == 'True':
            self.mcclient = Client('localhost', serde=JsonSerde())
        self.ttl = int(os.getenv("MEMCACHE_TTL", '3600'))

    def getCachedResults(self):
        res = self.mcclient.get(self.did)
        return res

    def setCachedResults(self, result):
        self.mcclient.set(self.did, result, self.ttl, True)

    def lookup_files(self):
        """
        lookup files.
        """
        n_files = 0
        ds_size = 0
        total_paths = 0
        avg_replicas = 0
        lookup_start = datetime.now()

        if self.mcclient:
            cachedResults = self.getCachedResults()

        if cachedResults:
            self.logger.info('Cache hit. Found {} files'.format(len(cachedResults)))
            for af in cachedResults:
                n_files += 1
                ds_size += af['file_size']
                total_paths += len(af['paths'])
            yield cachedResults
        else:
            self.logger.info('Cache miss. Doing Rucio lookup.')
            full_file_list = []
            for ds_files in self.rucio_adapter.list_files_for_did(self.did):
                for af in ds_files:
                    n_files += 1
                    ds_size += af['file_size']
                    total_paths += len(af['paths'])
                    full_file_list.append(af)
            if self.mcclient:
                self.setCachedResults(full_file_list)
            yield full_file_list

        lookup_finish = datetime.now()

        if n_files:
            avg_replicas = float(total_paths)/n_files

        metric = {
            'requestId': self.request_id,
            'n_files': n_files,
            'size': ds_size,
            'avg_replicas': avg_replicas,
            'lookup_duration': (lookup_finish-lookup_start).total_seconds()
        }
        self.logger.info(
            "Lookup finished. " +
            f"Metric: {json.dumps(metric)}"
        )
