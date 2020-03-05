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
from datetime import datetime

import requests


class ServiceXAdapter:
    def __init__(self, endpoint):
        self.endpoint = endpoint

    def post_status_update(self, status_msg):
        success = False
        attempts = 0
        while not success and attempts < 3:
            try:
                requests.post(self.endpoint + "/status", data={
                    "timestamp": datetime.now().isoformat(),
                    "status": status_msg
                })
                success = True
            except requests.exceptions.ConnectionError:
                print("Connection err. Retry")
                attempts += 1
        if not success:
            print("******** Failed to write status message")
            print("******** Continuing")

    def put_file_add(self, file_info):
        requests.put(self.endpoint + "/files", json={
            "timestamp": datetime.now().isoformat(),
            "file_path": file_info['file_path'],
            'adler32': file_info['adler32'],
            'file_size': file_info['file_size'],
            'file_events': file_info['file_events']
        })

    def post_preflight_check(self, file_entry):
        requests.post(self.endpoint + "/preflight", json={
            'file_path': file_entry['file_path']
        })

    def put_fileset_complete(self, summary):
        requests.put(self.endpoint + "/complete", json=summary)
