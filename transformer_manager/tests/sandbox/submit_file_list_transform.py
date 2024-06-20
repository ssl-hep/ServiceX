# Copyright (c) 2022, IRIS-HEP
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
from datetime import datetime, timezone

import uuid

from celery import Celery

app = Celery()
app.config_from_object("transformer_manager.celeryconfig")
request_id = str(uuid.uuid4())  # make sure we have a request id for all messages
file_list = ["root://eospublic.cern.ch//eos/opendata/atlas/OutreachDatasets/2020-01-22/4lep/MC/mc_345060.ggH125_ZZ4lep.4lep.root"]  # NOQA 501
request = "(call Where (call Select (call EventDataset) (lambda (list e) (dict (list 'lep_pt') (list (subscript e 'lep_pt'))))) (lambda (list e) (> (subscript e 'lep_pt') 1000)))"  # NOQA 501
result = app.send_task('transformer_manager.submit_transform',
                       args=[{'request': {
                          "request_id": request_id,
                          "title": "myTitle",
                          "did": None,
                          "file-list": file_list,
                          "user_codegen_name": "uproot",
                          "submit_time": datetime.now(tz=timezone.utc),
                          "submitted_by": None,
                          "selection": request,
                          "tree_name": None,
                          "image": None,
                          "result_destination": "object-store",
                          "result_format": "root-file",
                          "app_version": "2.0",
                          "code_gen_image": None
                       }}])

print(result)
