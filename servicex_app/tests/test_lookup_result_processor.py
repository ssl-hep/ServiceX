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
import json

from servicex.lookup_result_processor import LookupResultProcessor
from servicex.models import DatasetFile
from tests.resource_test_base import ResourceTestBase


class TestLookupResultProcessor(ResourceTestBase):

    def test_add_file_to_dataset(self, mocker, mock_rabbit_adaptor):
        processor = LookupResultProcessor(mock_rabbit_adaptor,
                                          "http://cern.analysis.ch:5000/")
        dataset_file = DatasetFile(request_id="BR549",
                                   paths=["/foo/bar1.root", "/foo/bar2.root"],
                                   adler32='12345',
                                   file_size=1024,
                                   file_events=500)

        request = self._generate_transform_request()
        request.result_destination = 'object-store'
        dataset_file.id = 42
        dataset_file.save_to_db = mocker.Mock()
        processor.add_file_to_dataset(request, dataset_file)

        dataset_file.save_to_db.assert_called()
        mock_rabbit_adaptor.basic_publish.assert_called_with(
            exchange='transformation_requests',
            routing_key='BR549',
            body=json.dumps(
                {"request-id": 'BR549',
                 "file-id": 42,
                 "columns": 'electron.eta(), muon.pt()',
                 "paths": ["/foo/bar1.root", "/foo/bar2.root"],
                 "tree-name": "Events",
                 "service-endpoint":
                     "http://cern.analysis.ch:5000/servicex/internal/transformation/BR549",
                 "chunk-size": "1000",
                 'result-destination': 'object-store'
                 }))

    def test_report_fileset_complete(self, mocker, mock_rabbit_adaptor):
        processor = LookupResultProcessor(mock_rabbit_adaptor, "http://cern.analysis.ch:5000/")

        transform_request = self._generate_transform_request()

        processor.report_fileset_complete(transform_request,
                                          num_files=1, num_skipped=2,
                                          total_events=3, total_bytes=4,
                                          did_lookup_time=5)

        assert transform_request.files == 1
        assert transform_request.files_skipped == 2
        assert transform_request.total_events == 3
        assert transform_request.total_bytes == 4
        assert transform_request.did_lookup_time == 5
