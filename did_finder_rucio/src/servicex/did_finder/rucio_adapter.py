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


class RucioAdapter:
    def __init__(self, did_client, replica_client):
        self.did_client = did_client
        self.replica_client = replica_client

    @staticmethod
    def parse_did(did):
        """
        Parse a DID string into the scope and name
        Allow for no scope to be included
        :param did:
        :return: Dictionary with keys "scope" and "name"
        """
        d = dict()
        if ':' in did:
            d['scope'], d['name'] = did.split(":")
        else:
            d['scope'], d['name'] = '', did
        return d

    def list_files_for_did(self, did):
        parsed_did = self.parse_did(did)
        g_files = self.did_client.list_files(parsed_did['scope'], parsed_did['name'])
        return g_files

    def find_replicas(self, files, site):
        g_replicas = None
        while not g_replicas:
            try:
                if type(files) == list:
                    file_list = files
                else:
                    file_list = [{'scope': files['scope'], 'name': files['name']}]

                location = {'site': site} if site else None

                g_replicas = self.replica_client.list_replicas(
                    dids=file_list,
                    schemes=['root'],
                    client_location=location)

            except Exception as eek:
                print("\n\n\n\n\nERROR READING REPLICA ", eek)
        return g_replicas

    @staticmethod
    def get_sel_path(replica, prefix):
        sel_path = None

        if 'pfns' not in replica:
            return None

        for fpath, meta in replica['pfns'].items():
            if not meta['type'] == 'DISK':
                continue
            sel_path = fpath
            if meta['domain'] == 'lan':
                break

        return prefix+sel_path
