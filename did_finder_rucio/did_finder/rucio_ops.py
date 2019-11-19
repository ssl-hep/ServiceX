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


def parse_did(did):
    """
    Parse a DID string into the scope and name
    :param did:
    :return: Dictionary with keys "scope" and "name"
    """
    d = dict()
    print("--->",did)
    d['scope'], d['name'] = did.split(":")
    return d


def list_files_for_did(did, did_client):
    g_files = None
    while not g_files:
        try:
            g_files = did_client.list_files(did['scope'], did['name'])
        except Exception as eek:
            print("\n\n\n\n\nERROR LISTING FILES ", eek)
    return g_files


def find_replicas(file, site, replica_client):
    g_replicas = None
    while not g_replicas:
        try:
            g_replicas = replica_client.list_replicas(
                dids=[{'scope': file['scope'], 'name': file['name']}],
                schemes=['root'],
                client_location={'site': site})

        except Exception as eek:
            print("\n\n\n\n\nERROR READING REPLICA ", eek)
    return g_replicas


def get_sel_path(replica):
    sel_path = None

    if 'pfns' not in replica:
        return None

    for fpath, meta in replica['pfns'].items():
        if not meta['type'] == 'DISK':
            continue
        sel_path = fpath
        if meta['domain'] == 'lan':
            break

    return sel_path

class DIDSummary:
    def __init__(self, did):
        self.did = did
        self.total_bytes = 0
        self.total_events = 0
        self.files = 0
        self.files_skipped = 0
        self.file_results = []

    def __str__(self):
        return ("DID {} - {:.0f} Mb {} Events in {} files ({} skipped)".format(
            self.did,
            self.total_bytes / 1e6,
            self.total_events,
            self.files,
            self.files_skipped))

    def accumulate(self, file_record):
        file_size_key = 'file_size' if 'file_size' in file_record else 'bytes'
        file_events_key = 'file_events' if 'file_events' in file_record else 'events'

        self.total_bytes += int(file_record[file_size_key] or 0)
        self.total_events += int(file_record[file_events_key] or 0)

    def add_file(self, file_record):
        self.files += 1
        self.file_results.append(file_record)
