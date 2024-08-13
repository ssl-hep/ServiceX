# Copyright (c) 2024, IRIS-HEP
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
from celery import Celery
import re

pattern = r'transformer-([0-9a-f-]+)-[a-z0-9]+\.transform_file'
did_finder_pattern = r'(.+)\.lookup_dataset'


def route_task(name, args, kwargs, options, task=None, **kw):
    print(f"Routing task {name} with args {args} and kwargs {kwargs} to {task}")
    match = re.search(pattern, name)
    if match:
        return {'queue': match.group(1)}
    else:
        return {
            'did_finder_cernopendata.lookup_dataset': {'queue': 'did_finder_cernopendata'},
            'did_finder_rucio.lookup_dataset': {'queue': 'did_finder_rucio'},
            'did_finder_xrootd.lookup_dataset': {'queue': 'did_finder_xrootd'}
        }[name]


app = Celery(broker="amqp://user:leftfoot1@localhost:5672")

app.conf.task_routes = (route_task,)

app.send_task('did_finder_rucio.lookup_dataset',
              kwargs={'dataset': 'mc15_13TeV:mc15_13TeV.361106.PowhegPythia8EvtGen_AZNLOCTEQ6L1_Zmumu.merge.DAOD_STDM3.e3601_s2576_s2132_r6630_r6264_p2363_tid05630000_00'})  # NOQA E501


app.send_task('transformer-2f748056-9db3-47f0-b51e-3ec46b8a284a.transform_file',
              kwargs={
                  "request_id": "abc123",
                  "file_id": 1,
                  "paths": ["/path/to/file1.txt", "/path/to/file2.pdf",
                            "/path/to/file3.docx"],
                  "file_path": "/path/to/file.txt",
                  "tree_name": "my_tree",
                  "service_endpoint": "https://example.com/api/v1",
                  "result_destination": "/path/to/output/directory",
                  "result_format": "root"
              })
