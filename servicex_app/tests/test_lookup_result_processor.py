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

from servicex.lookup_result_processor import LookupResultProcessor
from tests.resource_test_base import ResourceTestBase


class TestLookupResultProcessor(ResourceTestBase):

    def test_add_files_to_processing_queue(self, mocker, mock_rabbit_adaptor):
        import servicex

        processor = mocker.MagicMock(LookupResultProcessor(mock_rabbit_adaptor,
                                                           "http://cern.analysis.ch:5000/"))
        mocker.patch.object(
            servicex.models.TransformRequest,
            'all_files',
            [self._generate_datafile()])

        request = self._generate_transform_request()
        request.result_destination = 'object-store'

        processor.add_files_to_processing_queue(request)

        # mock_rabbit_adaptor.basic_publish.assert_called_with(
        #     exchange='transformation_requests',
        #     routing_key='BR549',
        #     body=json.dumps(
        #         {"request-id": 'BR549',
        #          "file-id": 42,
        #          "columns": 'electron.eta(), muon.pt()',
        #          "paths": ["/foo/bar1.root", "/foo/bar2.root"],
        #          "tree-name": "Events",
        #          "service-endpoint":
        #              "http://cern.analysis.ch:5000/servicex/internal/transformation/BR549",
        #          "chunk-size": "1000",
        #          'result-destination': 'object-store',
        #          "result-format": "arrow"
        #          }))
