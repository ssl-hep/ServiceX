# Copyright (c) 2019, IRIS-HEP
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
import xmltodict
from rucio.common.exception import DataIdentifierNotFound
from rucio.client.scopeclient import ScopeClient


class RucioAdapter:
    def __init__(self, did_client, replica_client, report_logical_files=False):
        self.did_client = did_client
        self.replica_client = replica_client
        self.report_logical_files = report_logical_files
        self.all_scopes = []
        # set logging to a null handler
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())

    def parse_did(self, did):
        """
        Parse a DID string into the scope and name
        Allow for no scope to be included
        :param did:
        :return: Dictionary with keys "scope" and "name"
        """
        d = dict()
        if ':' in did:
            d['scope'], d['name'] = did.split(":")
            return d

        if not self.all_scopes:
            uns_scopes = ScopeClient().list_scopes()
            self.all_scopes = sorted(uns_scopes, key=len, reverse=True)

        for sc in self.all_scopes:
            if did.startswith(sc):
                d['scope'], d['name'] = sc, did
                return d

        self.logger.error(f"Scope of the dataset {did} could not be determined.")
        return None

    def list_datasets_for_did(self, did):
        parsed_did = self.parse_did(did)
        if not parsed_did:
            return []
        try:
            datasets = []
            did_info = self.did_client.get_did(parsed_did['scope'], parsed_did['name'])
            if did_info['type'] == 'CONTAINER':
                self.logger.info(f"{did} is a container of {did_info['length']} datasets.")
                content = self.did_client.list_content(parsed_did['scope'], parsed_did['name'])
                for c in content:
                    datasets.append([c['scope'], c['name']])
            elif did_info['type'] == 'DATASET':
                datasets.append([parsed_did['scope'], parsed_did['name']])
                self.logger.info(f"{did} is a dataset with {did_info['length']} files.")
            else:
                self.logger.info(f"{did} is a file: {did_info}.")
                datasets.append([parsed_did['scope'], parsed_did['name']])
            return datasets
        except DataIdentifierNotFound:
            self.logger.warning(f"{did} not found")
            return None

    @staticmethod
    def get_paths(replicas):
        """
        extracts all the replica paths in a list sorted according
        to their priorities.
        """
        if isinstance(replicas, dict):
            replicas = [replicas]
        paths = [None] * len(replicas)
        for replica in replicas:
            paths[int(replica['@priority'], 10)-1] = replica['#text']
        return paths

    @staticmethod
    def get_adler(data):
        if '#text' in data:
            return data['#text']
        for cks in data:
            if 'adler32' in cks['@type']:
                return cks['#text']
        return None

    def list_files_for_did(self, did):
        """
        from rucio, gets list of file replicas in metalink xml,
        parses it, and returns a sorted list of all possible paths,
        together with checksum and filesize.
        """
        datasets = self.list_datasets_for_did(did)
        if not datasets:
            return
        no_replica_files = 0
        for ds in datasets:
            reps = self.replica_client.list_replicas(
                [{'scope': ds[0], 'name': ds[1]}],
                schemes=['root'],
                metalink=True,
                sort='geoip'
            )
            d = xmltodict.parse(reps)

            g_files = []
            if 'file' in d['metalink']:
                # if only one file, xml returns a dict and not a list.
                if isinstance(d['metalink']['file'], dict):
                    mfile = [d['metalink']['file']]
                else:
                    mfile = d['metalink']['file']
                for f in mfile:
                    # Path is either a list of replicas or a single logical name
                    if 'url' not in f:
                        self.logger.error(f"File {f['identity']} has no replicas.")
                        no_replica_files += 1
                        continue
                    path = self.get_paths(f['url']) \
                        if not self.report_logical_files else \
                        [f['identity'].strip('cms:')]

                    g_files.append(
                        {
                            'adler32': self.get_adler(f['hash']),
                            'file_size': int(f['size'], 10),
                            'file_events': 0,
                            'paths': path
                        }
                    )
            yield g_files

        if no_replica_files > 0:
            raise ValueError(f'Dataset {did} is missing replicas for {no_replica_files} '
                             'of its files.')
