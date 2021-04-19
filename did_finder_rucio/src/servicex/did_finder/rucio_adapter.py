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
from rucio.common.exception import DataIdentifierNotFound


class RucioAdapter:
    def __init__(self, did_client, replica_client):
        self.did_client = did_client
        self.replica_client = replica_client

        # set logging to a null handler
        import logging
        self.__logger = logging.getLogger(__name__)
        self.__logger.addHandler(logging.NullHandler())

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

        try:
            g_files = self.did_client.list_files(parsed_did['scope'], parsed_did['name'])
            return g_files
        except DataIdentifierNotFound:
            self.__logger.warning(f"-----> {did} not found")
            return None

    def find_replicas(self, files, site):
        g_replicas = None
        while not g_replicas:
            try:
                if type(files) == list:
                    file_list = files
                else:
                    file_list = [{'scope': files['scope'], 'name': files['name']}]

                g_replicas = self.replica_client.list_replicas(
                    dids=file_list,
                    schemes=['root'],
                    client_location=None)

            except Exception as e:
                self.__logger.exception(f"ERROR READING REPLICA {e}")
        return g_replicas

    @staticmethod
    def get_sel_path(replica, prefix, site):
        sel_path = None

        if 'pfns' not in replica:
            return None

        sitename = ''
        if site:
            sitename = site

        for fpath, meta in replica['pfns'].items():
            # if meta['type'] == 'DISK' and any(stnm in fpath for stnm in sitenames):
            if meta['type'] == 'DISK' and sitename in fpath:
                sel_path = fpath
                break

        if not sel_path:
            sel_path = sorted(replica['pfns'].keys())[-1]

        return prefix+sel_path
