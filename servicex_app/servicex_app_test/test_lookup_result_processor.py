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
from servicex_app.lookup_result_processor import LookupResultProcessor
from servicex_app_test.resource_test_base import ResourceTestBase
from servicex_app.celery.server_tasks import add_files_to_processing_queue


class TestLookupResultProcessor(ResourceTestBase):

    def test_add_files_to_processing_queue(self, mocker, celery_worker):
        processor = LookupResultProcessor()

        request = self._generate_transform_request()
        request.result_destination = "object-store"

        client = self._test_client()
        with client.application.app_context():
            call = mocker.patch(
                "servicex_app.celery.server_tasks.add_files_to_processing_queue.delay"
            )
            processor.add_files_to_processing_queue(
                request, [self._generate_datafile()]
            )
            call.assert_called_once()

    def test_add_files_to_processing_queue_low_level(self, mocker, celery_worker):
        mocker.patch.dict("os.environ", {"INSTANCE_NAME": "servicex"})
        request = self._generate_transform_request()
        request.result_destination = "object-store"

        client = self._test_client()
        with client.application.app_context():
            task = mocker.patch("celery.Signature.apply_async")
            add_files_to_processing_queue(
                request.to_json(), [self._generate_datafile().to_json()]
            )
            task.assert_called_once()
